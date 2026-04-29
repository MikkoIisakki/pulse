"""Electricity domain endpoints.

GET /v1/energy/prices?region={code}&date={YYYY-MM-DD|today|tomorrow}
GET /v1/energy/cheap-intervals?region={code}&date={YYYY-MM-DD|today|tomorrow}&limit={int}
GET /v1/energy/alerts?region={code}

Per ADR-005, prices are interval-based (`interval_start`/`interval_end` UTC,
`interval_minutes` width). For ENTSO-E zones today this is typically PT15M
(96 slots/day) or PT60M (24 slots/day).
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.api.dependencies import Pool
from app.storage import repository as repo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/energy", tags=["energy"])


# ─────────────────────────────────────────────────────────────────────────────
# Response models
# ─────────────────────────────────────────────────────────────────────────────


class IntervalPriceOut(BaseModel):
    interval_start: datetime
    interval_end: datetime
    interval_minutes: int
    price_eur_mwh: float
    spot_c_kwh: float
    total_c_kwh: float


class PricesResponse(BaseModel):
    region: str
    date: str
    interval_minutes: int | None
    prices: list[IntervalPriceOut]


class RankedIntervalOut(BaseModel):
    rank: int
    interval_start: datetime
    interval_end: datetime
    interval_minutes: int
    price_eur_mwh: float
    spot_c_kwh: float
    total_c_kwh: float


class CheapIntervalsResponse(BaseModel):
    region: str
    date: str
    interval_minutes: int | None
    intervals: list[RankedIntervalOut]


class AlertOut(BaseModel):
    id: int
    price_date: date
    peak_c_kwh: float
    peak_interval_start: datetime
    threshold_c_kwh: float
    fired_at: datetime


class AlertsResponse(BaseModel):
    region: str
    alerts: list[AlertOut]


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _resolve_date(date_str: str) -> date:
    """Resolve 'today', 'tomorrow', or ISO date string to a date object.

    Raises HTTPException(422) on unrecognised input.
    """
    if date_str == "today":
        return date.today()
    if date_str == "tomorrow":
        return date.today() + timedelta(days=1)
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid date '{date_str}'. Use YYYY-MM-DD, 'today', or 'tomorrow'.",
        ) from None


def _interval_minutes_of(rows: list[dict[str, Any]]) -> int | None:
    """Return the cadence reported by the first row, or None for an empty result."""
    return rows[0]["interval_minutes"] if rows else None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/prices", response_model=PricesResponse)
async def get_energy_prices(
    pool: Pool,
    region: str = Query(description="Bidding zone code, e.g. FI, SE3"),
    date: str = Query(description="Delivery date: YYYY-MM-DD, 'today', or 'tomorrow'"),
) -> dict[str, Any]:
    """Return interval electricity prices for a region and date."""
    price_date = _resolve_date(date)
    region_upper = region.upper()

    async with pool.acquire() as conn:
        region_row = await conn.fetchrow(
            "SELECT code FROM energy_region WHERE code = $1 AND active = TRUE",
            region_upper,
        )
        if region_row is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_upper}' not found")

        rows = await repo.get_energy_prices(conn, region_upper, price_date)

    return {
        "region": region_upper,
        "date": price_date.isoformat(),
        "interval_minutes": _interval_minutes_of(rows),
        "prices": [dict(r) for r in rows],
    }


@router.get("/cheap-intervals", response_model=CheapIntervalsResponse)
async def get_cheap_intervals(
    pool: Pool,
    region: str = Query(description="Bidding zone code, e.g. FI, SE3"),
    date: str = Query(description="Delivery date: YYYY-MM-DD, 'today', or 'tomorrow'"),
    limit: int = Query(default=24, ge=1, le=192, description="Max intervals to return (1..192)"),
) -> dict[str, Any]:
    """Return the cheapest intervals for a region/date, ranked ascending by total_c_kwh."""
    price_date = _resolve_date(date)
    region_upper = region.upper()

    async with pool.acquire() as conn:
        region_row = await conn.fetchrow(
            "SELECT code FROM energy_region WHERE code = $1 AND active = TRUE",
            region_upper,
        )
        if region_row is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_upper}' not found")

        rows = await repo.get_cheap_intervals(conn, region_upper, price_date, limit)

    return {
        "region": region_upper,
        "date": price_date.isoformat(),
        "interval_minutes": _interval_minutes_of(rows),
        "intervals": [{"rank": i + 1, **dict(r)} for i, r in enumerate(rows)],
    }


@router.get("/alerts", response_model=AlertsResponse)
async def get_energy_alerts(
    pool: Pool,
    region: str = Query(description="Bidding zone code, e.g. FI, SE3"),
) -> dict[str, Any]:
    """Return fired threshold alerts for a region, newest first."""
    region_upper = region.upper()

    async with pool.acquire() as conn:
        region_row = await conn.fetchrow(
            "SELECT code FROM energy_region WHERE code = $1 AND active = TRUE",
            region_upper,
        )
        if region_row is None:
            raise HTTPException(status_code=404, detail=f"Region '{region_upper}' not found")

        rows = await repo.get_energy_alerts(conn, region_upper)

    return {
        "region": region_upper,
        "alerts": [dict(r) for r in rows],
    }
