"""Tests for the US ingest pipeline.

All external dependencies (yfinance, DB) are mocked so no live database
or network is needed. These tests verify orchestration logic only.
"""

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ingestion.us_ingest import run_us_ingest


def _fake_fetch(symbol: str, *, lookback_days: int = 5) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "rows": [
            {
                "price_date": date(2024, 1, 2),
                "open": 150.0,
                "high": 155.0,
                "low": 148.0,
                "close": 152.0,
                "adj_close": 151.5,
                "volume": 1_000_000,
            }
        ],
    }


def _mock_pool() -> MagicMock:
    """Pool mock whose acquire() yields a dummy connection."""
    conn = MagicMock()
    pool = MagicMock()

    class _AcquireCtx:
        async def __aenter__(self) -> MagicMock:
            return conn

        async def __aexit__(self, *_: Any) -> None:
            pass

    pool.acquire.return_value = _AcquireCtx()
    return pool


@pytest.mark.asyncio
async def test_successful_ingest_creates_run_and_prices() -> None:
    fake_assets = [{"id": 999, "symbol": "AAPL", "exchange": "NASDAQ"}]

    with (
        patch("app.ingestion.us_ingest.repo.get_active_assets", return_value=fake_assets),
        patch("app.ingestion.us_ingest.fetch_eod", new=AsyncMock(side_effect=_fake_fetch)),
        patch("app.ingestion.us_ingest.repo.save_raw_snapshot", new=AsyncMock()),
        patch("app.ingestion.us_ingest.repo.upsert_daily_prices", new=AsyncMock(return_value=1)),
        patch("app.ingestion.us_ingest.repo.create_ingest_run", new=AsyncMock(return_value=42)),
        patch("app.ingestion.us_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_us_ingest(_mock_pool())

    mock_finish.assert_called_once()
    _, call_kwargs = mock_finish.call_args
    assert call_kwargs["status"] == "success"
    assert call_kwargs["assets_attempted"] == 1
    assert call_kwargs["assets_succeeded"] == 1


@pytest.mark.asyncio
async def test_empty_asset_list_marks_run_failed() -> None:
    with (
        patch("app.ingestion.us_ingest.repo.get_active_assets", return_value=[]),
        patch("app.ingestion.us_ingest.repo.create_ingest_run", new=AsyncMock(return_value=43)),
        patch("app.ingestion.us_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_us_ingest(_mock_pool())

    _, call_kwargs = mock_finish.call_args
    assert call_kwargs["status"] == "failed"
    assert "No active assets" in (call_kwargs["error_message"] or "")


@pytest.mark.asyncio
async def test_fetch_exception_counts_as_failure() -> None:
    fake_assets = [{"id": 999, "symbol": "BADFEED", "exchange": "NYSE"}]

    async def boom(symbol: str, **_: Any) -> dict[str, Any]:
        raise RuntimeError("network error")

    with (
        patch("app.ingestion.us_ingest.repo.get_active_assets", return_value=fake_assets),
        patch("app.ingestion.us_ingest.fetch_eod", new=AsyncMock(side_effect=boom)),
        patch("app.ingestion.us_ingest.repo.create_ingest_run", new=AsyncMock(return_value=44)),
        patch("app.ingestion.us_ingest.repo.finish_ingest_run", new=AsyncMock()) as mock_finish,
    ):
        await run_us_ingest(_mock_pool())

    _, call_kwargs = mock_finish.call_args
    assert call_kwargs["status"] == "failed"
    assert call_kwargs["assets_succeeded"] == 0
