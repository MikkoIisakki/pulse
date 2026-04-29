"""Unit tests for /v1/energy endpoints (interval-based, ADR-005).

Uses FastAPI's test client with the pool dependency overridden so no real
database is needed.
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_pool
from app.api.routers.energy import router

_DAY = date(2025, 1, 15)
_DAY_START = datetime(2025, 1, 15, 0, 0, tzinfo=UTC)


def _make_app(pool_mock: Any) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def override_pool() -> Any:
        yield pool_mock

    app.dependency_overrides[get_pool] = override_pool
    return app


class _AsyncCtx:
    def __init__(self, value: Any) -> None:
        self._value = value

    async def __aenter__(self) -> Any:
        return self._value

    async def __aexit__(self, *_: Any) -> None:
        pass


def _pool_mock(region_row: Any, data_rows: list[dict[str, Any]]) -> MagicMock:
    """Pool whose connection returns region_row from fetchrow and data_rows from fetch."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=region_row)
    conn.fetch = AsyncMock(return_value=data_rows)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    return pool


def _region_row() -> MagicMock:
    row = MagicMock()
    row.__getitem__ = MagicMock(side_effect=lambda k: "FI" if k == "code" else None)
    return row


def _hourly_row(hour: int, *, total: str = "13.48") -> dict[str, Any]:
    start = _DAY_START + timedelta(hours=hour)
    return {
        "interval_start": start,
        "interval_end": start + timedelta(hours=1),
        "interval_minutes": 60,
        "spot_c_kwh": Decimal("8.55"),
        "total_c_kwh": Decimal(total),
        "price_eur_mwh": Decimal("85.50"),
    }


# ─── GET /v1/energy/prices ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_prices_returns_interval_data() -> None:
    rows = [_hourly_row(h) for h in range(24)]
    app = _make_app(_pool_mock(_region_row(), rows))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/prices?region=FI&date=2025-01-15")

    assert resp.status_code == 200
    body = resp.json()
    assert body["region"] == "FI"
    assert body["date"] == "2025-01-15"
    assert body["interval_minutes"] == 60
    assert len(body["prices"]) == 24
    first = body["prices"][0]
    assert first["interval_start"] == "2025-01-15T00:00:00Z"
    assert first["interval_end"] == "2025-01-15T01:00:00Z"
    assert first["interval_minutes"] == 60
    assert first["spot_c_kwh"] == 8.55


@pytest.mark.asyncio
async def test_prices_pt15m_resolution_reported() -> None:
    """When the upstream cadence is 15 minutes, the response top level says so."""
    rows = []
    for i in range(96):
        start = _DAY_START + timedelta(minutes=15 * i)
        rows.append(
            {
                "interval_start": start,
                "interval_end": start + timedelta(minutes=15),
                "interval_minutes": 15,
                "spot_c_kwh": Decimal("4.50"),
                "total_c_kwh": Decimal("8.42"),
                "price_eur_mwh": Decimal("45.00"),
            }
        )
    app = _make_app(_pool_mock(_region_row(), rows))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/prices?region=FI&date=2025-01-15")

    body = resp.json()
    assert body["interval_minutes"] == 15
    assert len(body["prices"]) == 96


@pytest.mark.asyncio
async def test_prices_today_shortcut_accepted() -> None:
    app = _make_app(_pool_mock(_region_row(), []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/prices?region=FI&date=today")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_prices_tomorrow_shortcut_accepted() -> None:
    app = _make_app(_pool_mock(_region_row(), []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/prices?region=FI&date=tomorrow")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_prices_unknown_region_returns_404() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    app = _make_app(pool)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/prices?region=XX&date=2025-01-15")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_prices_invalid_date_returns_422() -> None:
    app = _make_app(_pool_mock(_region_row(), []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/prices?region=FI&date=not-a-date")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_prices_missing_date_returns_422() -> None:
    app = _make_app(_pool_mock(_region_row(), []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/prices?region=FI")
    assert resp.status_code == 422


# ─── GET /v1/energy/alerts ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_alerts_returns_list() -> None:
    fired_at = datetime(2025, 1, 16, 12, 0, 0, tzinfo=UTC)
    peak_start = datetime(2025, 1, 16, 16, 0, 0, tzinfo=UTC)
    alert_rows = [
        {
            "id": 1,
            "price_date": date(2025, 1, 16),
            "peak_c_kwh": Decimal("35.50"),
            "peak_interval_start": peak_start,
            "threshold_c_kwh": Decimal("30.00"),
            "fired_at": fired_at,
        }
    ]
    app = _make_app(_pool_mock(_region_row(), alert_rows))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/alerts?region=FI")

    assert resp.status_code == 200
    body = resp.json()
    assert body["region"] == "FI"
    assert len(body["alerts"]) == 1
    assert body["alerts"][0]["peak_interval_start"] == "2025-01-16T16:00:00Z"
    assert body["alerts"][0]["peak_c_kwh"] == 35.5


@pytest.mark.asyncio
async def test_alerts_empty_region_returns_empty_list() -> None:
    app = _make_app(_pool_mock(_region_row(), []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/alerts?region=FI")
    assert resp.status_code == 200
    assert resp.json()["alerts"] == []


@pytest.mark.asyncio
async def test_alerts_unknown_region_returns_404() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    app = _make_app(pool)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/alerts?region=XX")

    assert resp.status_code == 404


# ─── GET /v1/energy/cheap-intervals ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_cheap_intervals_sorted_ascending_with_rank() -> None:
    sorted_rows = [
        _hourly_row(3, total="2.50"),
        _hourly_row(4, total="3.75"),
        _hourly_row(14, total="5.84"),
    ]
    app = _make_app(_pool_mock(_region_row(), sorted_rows))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/cheap-intervals?region=FI&date=2025-01-15")

    assert resp.status_code == 200
    body = resp.json()
    assert body["region"] == "FI"
    assert body["date"] == "2025-01-15"
    assert body["interval_minutes"] == 60
    intervals = body["intervals"]
    assert len(intervals) == 3
    totals = [iv["total_c_kwh"] for iv in intervals]
    assert totals == sorted(totals)
    assert [iv["rank"] for iv in intervals] == [1, 2, 3]
    assert intervals[0]["interval_start"] == "2025-01-15T03:00:00Z"
    assert intervals[0]["total_c_kwh"] == 2.5


@pytest.mark.asyncio
async def test_cheap_intervals_respects_limit_parameter() -> None:
    sorted_rows = [_hourly_row(h, total=f"{2 + h}.00") for h in range(5)]
    pool = _pool_mock(_region_row(), sorted_rows)
    app = _make_app(pool)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/cheap-intervals?region=FI&date=2025-01-15&limit=5")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["intervals"]) == 5
    conn_mock = pool.acquire.return_value._value
    args, _ = conn_mock.fetch.call_args
    assert 5 in args


@pytest.mark.asyncio
async def test_cheap_intervals_today_shortcut_accepted() -> None:
    app = _make_app(_pool_mock(_region_row(), []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/cheap-intervals?region=FI&date=today")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cheap_intervals_tomorrow_shortcut_accepted() -> None:
    app = _make_app(_pool_mock(_region_row(), []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/cheap-intervals?region=FI&date=tomorrow")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_cheap_intervals_unknown_region_returns_404() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_AsyncCtx(conn))
    app = _make_app(pool)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/cheap-intervals?region=XX&date=2025-01-15")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cheap_intervals_invalid_date_returns_422() -> None:
    app = _make_app(_pool_mock(_region_row(), []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/cheap-intervals?region=FI&date=not-a-date")
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_cheap_intervals_empty_when_no_data() -> None:
    app = _make_app(_pool_mock(_region_row(), []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/cheap-intervals?region=FI&date=2099-01-01")

    assert resp.status_code == 200
    body = resp.json()
    assert body["region"] == "FI"
    assert body["date"] == "2099-01-01"
    assert body["interval_minutes"] is None
    assert body["intervals"] == []


@pytest.mark.asyncio
async def test_cheap_hours_route_no_longer_exists() -> None:
    """Old /cheap-hours route deleted per ADR-005 clean-break instruction."""
    _ = _DAY  # silence unused-import-style noise
    app = _make_app(_pool_mock(_region_row(), []))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/cheap-hours?region=FI&date=2025-01-15")
    assert resp.status_code == 404
