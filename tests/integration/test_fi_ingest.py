"""Integration tests for Finnish ingest pipeline."""

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, patch

import asyncpg
import pytest

from app.ingestion.fi_ingest import run_fi_ingest


def _fake_fetch(symbol: str, *, lookback_days: int = 5) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "rows": [
            {
                "price_date": date(2024, 1, 2),
                "open": 4.20,
                "high": 4.35,
                "low": 4.15,
                "close": 4.28,
                "adj_close": 4.28,
                "volume": 500_000,
            }
        ],
    }


@pytest.mark.asyncio
async def test_successful_fi_ingest(db_pool: asyncpg.Pool) -> None:
    fake_assets = [{"id": 998, "symbol": "NOKIA.HE", "exchange": "HEL"}]

    with (
        patch("app.ingestion.fi_ingest.repo.get_active_assets", return_value=fake_assets),
        patch("app.ingestion.fi_ingest.fetch_eod", new=AsyncMock(side_effect=_fake_fetch)),
        patch("app.ingestion.fi_ingest.repo.save_raw_snapshot", new=AsyncMock()),
        patch("app.ingestion.fi_ingest.repo.upsert_daily_prices", new=AsyncMock(return_value=1)),
        patch("app.ingestion.fi_ingest.repo.create_ingest_run", new=AsyncMock(return_value=50)),
        patch("app.ingestion.fi_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_fi_ingest(db_pool)

    mock_finish.assert_called_once()
    _, call_kwargs = mock_finish.call_args
    assert call_kwargs["status"] == "success"
    assert call_kwargs["assets_attempted"] == 1
    assert call_kwargs["assets_succeeded"] == 1


@pytest.mark.asyncio
async def test_empty_fi_asset_list_marks_run_failed(db_pool: asyncpg.Pool) -> None:
    with (
        patch("app.ingestion.fi_ingest.repo.get_active_assets", return_value=[]),
        patch("app.ingestion.fi_ingest.repo.create_ingest_run", new=AsyncMock(return_value=51)),
        patch("app.ingestion.fi_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_fi_ingest(db_pool)

    _, call_kwargs = mock_finish.call_args
    assert call_kwargs["status"] == "failed"


@pytest.mark.asyncio
async def test_fi_fetch_exception_counts_as_failure(db_pool: asyncpg.Pool) -> None:
    fake_assets = [{"id": 998, "symbol": "NOKIA.HE", "exchange": "HEL"}]

    async def boom(symbol: str, **_: Any) -> dict[str, Any]:
        raise RuntimeError("timeout")

    with (
        patch("app.ingestion.fi_ingest.repo.get_active_assets", return_value=fake_assets),
        patch("app.ingestion.fi_ingest.fetch_eod", new=AsyncMock(side_effect=boom)),
        patch("app.ingestion.fi_ingest.repo.create_ingest_run", new=AsyncMock(return_value=52)),
        patch("app.ingestion.fi_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_fi_ingest(db_pool)

    _, call_kwargs = mock_finish.call_args
    assert call_kwargs["status"] == "failed"
    assert call_kwargs["assets_succeeded"] == 0
