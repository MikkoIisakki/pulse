"""Finnish EOD price ingest — Helsinki Stock Exchange (.HE tickers).

Entry point: ``run_fi_ingest(pool)``

Identical pipeline to us_ingest but targets market='FI'. Symbols in the asset
table use the yfinance convention for Helsinki: TICKER.HE (e.g. NOKIA.HE).
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date
from typing import Any

import asyncpg

from app.ingestion.yfinance_client import fetch_eod
from app.normalization.price import normalize_price_rows
from app.storage import repository as repo
from app.storage.repository import AnyConn

logger = logging.getLogger(__name__)

_MARKET = "FI"
_CONCURRENCY = 3  # Helsinki universe is smaller; lower concurrency is fine


async def _ingest_asset(
    conn: AnyConn,
    *,
    asset_id: int,
    symbol: str,
    run_id: int,
    snapshot_date: date,
) -> bool:
    """Ingest one Finnish asset. Returns True on success, False on any error."""
    try:
        raw = await fetch_eod(symbol)
    except Exception:
        logger.exception("yfinance fetch failed for %s", symbol)
        return False

    try:
        await repo.save_raw_snapshot(
            conn,
            run_id=run_id,
            source="yfinance",
            symbol=symbol,
            snapshot_date=snapshot_date,
            payload={
                "rows": [{**r, "price_date": r["price_date"].isoformat()} for r in raw["rows"]]
            },
        )
    except Exception:
        logger.exception("Failed to save raw snapshot for %s", symbol)

    if not raw["rows"]:
        logger.warning("No price rows returned for %s", symbol)
        return False

    prices = normalize_price_rows(raw["rows"], asset_id=asset_id, ingest_run_id=run_id)
    if not prices:
        logger.warning("All rows filtered out for %s", symbol)
        return False

    try:
        await repo.upsert_daily_prices(conn, prices)
    except Exception:
        logger.exception("DB upsert failed for %s", symbol)
        return False

    logger.info("Ingested %d price rows for %s", len(prices), symbol)
    return True


async def run_fi_ingest(pool: asyncpg.Pool[asyncpg.Record]) -> None:
    """Run the full Finnish EOD ingest pipeline against *pool*."""
    snapshot_date = date.today()

    async with pool.acquire() as conn:
        run_id = await repo.create_ingest_run(conn, _MARKET)
        logger.info("Started FI ingest run id=%d", run_id)

        assets = await repo.get_active_assets(conn, _MARKET)
        if not assets:
            logger.warning("No active FI assets found — nothing to ingest")
            await repo.finish_ingest_run(
                conn,
                run_id,
                status="failed",
                assets_attempted=0,
                assets_succeeded=0,
                error_message="No active assets in DB",
            )
            return

        sem = asyncio.Semaphore(_CONCURRENCY)
        attempted = len(assets)

        async def guarded(asset: dict[str, Any]) -> bool:
            async with sem:
                return await _ingest_asset(
                    conn,
                    asset_id=asset["id"],
                    symbol=asset["symbol"],
                    run_id=run_id,
                    snapshot_date=snapshot_date,
                )

        results = await asyncio.gather(*[guarded(a) for a in assets])
        succeeded = sum(results)

        status = "success" if succeeded > 0 else "failed"
        error = None if succeeded > 0 else "All assets failed to ingest"

        await repo.finish_ingest_run(
            conn,
            run_id,
            status=status,
            assets_attempted=attempted,
            assets_succeeded=succeeded,
            error_message=error,
        )
        logger.info(
            "FI ingest run id=%d finished: %s (%d/%d assets succeeded)",
            run_id,
            status,
            succeeded,
            attempted,
        )
