"""Thin async HTTP client for the Nordpool day-ahead price API.

Nordpool publishes day-ahead hourly prices at ~13:00 CET each day.
The public dataportal API requires no authentication.

Endpoint: GET https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices
"""

import asyncio
import logging
from datetime import date
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://dataportal-api.nordpoolgroup.com/api/DayAheadPrices"
_TIMEOUT = 30.0  # seconds


def _fetch_sync(target_date: date, region: str) -> dict[str, Any]:
    """Synchronous HTTP call — runs in a thread executor."""
    params = {
        "date": target_date.strftime("%Y-%m-%d"),
        "market": "DayAhead",
        "deliveryArea": region,
        "currency": "EUR",
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        response = client.get(_BASE_URL, params=params)
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


async def fetch_day_ahead(target_date: date, region: str = "FI") -> dict[str, Any]:
    """Fetch Nordpool day-ahead prices for *region* on *target_date*.

    Returns the raw JSON response dict. The caller (normalisation layer)
    is responsible for interpreting the structure.

    Raises:
        httpx.HTTPStatusError: on non-2xx responses.
        httpx.TimeoutException: if the request times out.
    """
    loop = asyncio.get_running_loop()
    result: dict[str, Any] = await loop.run_in_executor(None, _fetch_sync, target_date, region)
    logger.debug("Nordpool %s %s: %d hourly rows", region, target_date, len(result.get("rows", [])))
    return result
