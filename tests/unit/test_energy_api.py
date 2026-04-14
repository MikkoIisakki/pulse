"""Unit tests for /v1/energy endpoints.

Uses FastAPI's test client with the pool dependency overridden so no real
database is needed.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_pool
from app.api.routers.energy import router


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


# ─── GET /v1/energy/prices ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_prices_returns_hourly_data() -> None:
    price_rows = [
        {
            "hour": h,
            "spot_c_kwh": Decimal("8.55"),
            "total_c_kwh": Decimal("13.48"),
            "price_eur_mwh": Decimal("85.50"),
        }
        for h in range(24)
    ]
    app = _make_app(_pool_mock(_region_row(), price_rows))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/prices?region=FI&date=2025-01-15")

    assert resp.status_code == 200
    body = resp.json()
    assert body["region"] == "FI"
    assert body["date"] == "2025-01-15"
    assert len(body["prices"]) == 24
    assert body["prices"][0]["hour"] == 0
    assert body["prices"][0]["spot_c_kwh"] == 8.55


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
    _fired_at = datetime(2025, 1, 16, 12, 0, 0, tzinfo=UTC)
    alert_rows = [
        {
            "id": 1,
            "price_date": date(2025, 1, 16),
            "peak_c_kwh": Decimal("35.50"),
            "peak_hour": 16,
            "threshold_c_kwh": Decimal("30.00"),
            "fired_at": _fired_at,
        }
    ]
    app = _make_app(_pool_mock(_region_row(), alert_rows))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/energy/alerts?region=FI")

    assert resp.status_code == 200
    body = resp.json()
    assert body["region"] == "FI"
    assert len(body["alerts"]) == 1
    assert body["alerts"][0]["peak_hour"] == 16
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
