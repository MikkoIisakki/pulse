"""Unit tests for GET /v1/health/ready.

All database interactions are mocked — no live DB or network needed.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_pool
from app.api.routers.health import get_settings, router
from app.common.config import Settings


def _make_app(pool_mock: Any, max_ingest_age_hours: int = 25) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def override_pool() -> Any:
        yield pool_mock

    def override_settings() -> Settings:
        return Settings(
            database_url="postgresql://x:x@localhost/x", max_ingest_age_hours=max_ingest_age_hours
        )

    app.dependency_overrides[get_pool] = override_pool
    app.dependency_overrides[get_settings] = override_settings
    return app


def _pool_returning(last_finished: datetime | None) -> MagicMock:
    """Build a pool mock whose fetchrow returns a row with last_finished."""
    row = {"last_finished": last_finished}
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)

    class _Ctx:
        async def __aenter__(self) -> MagicMock:
            return conn

        async def __aexit__(self, *_: Any) -> None:
            pass

    pool = MagicMock()
    pool.acquire.return_value = _Ctx()
    return pool


def _pool_raising(exc: Exception) -> MagicMock:
    """Build a pool mock whose acquire().__aenter__ raises exc."""

    class _Ctx:
        async def __aenter__(self) -> None:
            raise exc

        async def __aexit__(self, *_: Any) -> None:
            pass

    pool = MagicMock()
    pool.acquire.return_value = _Ctx()
    return pool


@pytest.mark.asyncio
async def test_ok_when_recent_ingest() -> None:
    last_finished = datetime.now(UTC) - timedelta(hours=1)
    app = _make_app(_pool_returning(last_finished))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_degraded_when_ingest_stale() -> None:
    last_finished = datetime.now(UTC) - timedelta(hours=30)
    app = _make_app(_pool_returning(last_finished))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert "reason" in body


@pytest.mark.asyncio
async def test_degraded_when_no_ingest_runs() -> None:
    app = _make_app(_pool_returning(None))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_degraded_exactly_at_threshold() -> None:
    """A run finished exactly max_ingest_age_hours ago should be degraded."""
    last_finished = datetime.now(UTC) - timedelta(hours=25, seconds=1)
    app = _make_app(_pool_returning(last_finished), max_ingest_age_hours=25)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    assert resp.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_503_when_db_unreachable() -> None:
    app = _make_app(_pool_raising(ConnectionRefusedError("db down")))

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/v1/health/ready")

    assert resp.status_code == 503
    assert resp.json()["status"] == "unavailable"
