"""Async HTTP client for the ENTSO-E Transparency Platform day-ahead price API.

ENTSO-E publishes hourly day-ahead spot prices for every EU bidding zone.
The Transparency Platform's RESTful interface returns XML
``Publication_MarketDocument`` payloads (``documentType=A44`` for prices).

Authentication is by query parameter ``securityToken`` — the token must be
obtained by registering at https://transparency.entsoe.eu (Settings → Web
API Security Token).

This module is a thin anti-corruption layer: it speaks ENTSO-E XML on the
wire and returns rows shaped exactly like the previous Nordpool client so
that ``app.normalization.energy_price.normalize_nordpool_response`` continues
to work without modification.

Endpoint: GET https://web-api.tp.entsoe.eu/api
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, date, datetime, timedelta
from typing import Any
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)

_BASE_URL = "https://web-api.tp.entsoe.eu/api"
_TIMEOUT = 30.0  # seconds
_DOCUMENT_TYPE = "A44"  # Day-ahead prices

# ENTSO-E XML uses default namespaces that change per document version.
# We match by local-name to stay compatible across schema revisions.
_PUBLICATION_LOCAL = "Publication_MarketDocument"
_ACK_LOCAL = "Acknowledgement_MarketDocument"


# Bidding zone code → ENTSO-E EIC (Energy Identification Code).
# Source: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
# Keep aligned with db/seeds/002_energy_regions.sql.
REGION_TO_EIC: dict[str, str] = {
    "FI": "10YFI-1--------U",
    "SE3": "10Y1001A1001A46L",
    "SE4": "10Y1001A1001A47J",
    "EE": "10Y1001A1001A39I",
    "LT": "10YLT-1001A0008Q",
    "LV": "10YLV-1001A00074",
}


class EntsoeAuthError(RuntimeError):
    """Raised when ENTSO-E returns 401 — token is missing, invalid, or revoked."""


class EntsoeNoDataError(RuntimeError):
    """Raised when ENTSO-E returns an Acknowledgement_MarketDocument (no data for window)."""


def _local(tag: str) -> str:
    """Return the local-name portion of a possibly-namespaced XML tag."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _fetch_sync(target_date: date, region: str, token: str) -> str:
    """Synchronous HTTP GET — runs in a thread executor.

    Returns the raw response text (XML). Raises ``EntsoeAuthError`` on 401.
    """
    eic = REGION_TO_EIC[region]
    period_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    period_end = period_start + timedelta(days=1)
    params = {
        "securityToken": token,
        "documentType": _DOCUMENT_TYPE,
        "in_Domain": eic,
        "out_Domain": eic,
        "periodStart": period_start.strftime("%Y%m%d%H%M"),
        "periodEnd": period_end.strftime("%Y%m%d%H%M"),
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        response = client.get(_BASE_URL, params=params)
        if response.status_code == 401:
            raise EntsoeAuthError("ENTSO-E returned 401 Unauthorized — check ENTSOE_API_TOKEN")
        response.raise_for_status()
        return response.text


def _parse_xml(xml_text: str, target_date: date) -> dict[str, Any]:
    """Parse an ENTSO-E A44 Publication_MarketDocument into the legacy row shape.

    Produces:
        {
            "deliveryDateCET": "YYYY-MM-DD",
            "currency": "EUR",
            "rows": [{"startTime": "...", "endTime": "...", "value": <float>}, ...]
        }

    Raises:
        EntsoeNoDataError: if the response is an Acknowledgement_MarketDocument
            (ENTSO-E's way of saying "no matching data found").
    """
    root = ET.fromstring(xml_text)
    root_local = _local(root.tag)

    if root_local == _ACK_LOCAL:
        reason_text = ""
        for elem in root.iter():
            if _local(elem.tag) == "text" and elem.text:
                reason_text = elem.text
                break
        raise EntsoeNoDataError(
            f"ENTSO-E returned no data for {target_date}: {reason_text or 'unknown reason'}"
        )

    if root_local != _PUBLICATION_LOCAL:
        raise RuntimeError(f"Unexpected ENTSO-E root element: {root_local}")

    rows: list[dict[str, Any]] = []
    for series in root.iter():
        if _local(series.tag) != "TimeSeries":
            continue
        for period in series.iter():
            if _local(period.tag) != "Period":
                continue
            period_start = _read_period_start(period, fallback=target_date)
            for point in period.iter():
                if _local(point.tag) != "Point":
                    continue
                position = _read_int_child(point, "position")
                price = _read_float_child(point, "price.amount")
                if position is None or price is None:
                    continue
                hour_start = period_start + timedelta(hours=position - 1)
                hour_end = hour_start + timedelta(hours=1)
                rows.append(
                    {
                        "startTime": _format_iso(hour_start),
                        "endTime": _format_iso(hour_end),
                        "value": price,
                    }
                )

    return {
        "deliveryDateCET": target_date.isoformat(),
        "currency": "EUR",
        "rows": rows,
    }


def _read_period_start(period: ET.Element, fallback: date) -> datetime:
    """Extract the period's UTC start datetime; fall back to midnight UTC of *fallback*."""
    for elem in period.iter():
        if _local(elem.tag) == "start" and elem.text:
            text = elem.text.strip()
            # ENTSO-E uses "2025-01-15T00:00Z" (no seconds). Normalise to ISO with offset.
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(text)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed
            except ValueError:
                break
    return datetime.combine(fallback, datetime.min.time(), tzinfo=UTC)


def _read_int_child(parent: ET.Element, local_name: str) -> int | None:
    for child in parent:
        if _local(child.tag) == local_name and child.text:
            try:
                return int(child.text)
            except ValueError:
                return None
    return None


def _read_float_child(parent: ET.Element, local_name: str) -> float | None:
    for child in parent:
        if _local(child.tag) == local_name and child.text:
            try:
                return float(child.text)
            except ValueError:
                return None
    return None


def _format_iso(dt: datetime) -> str:
    """Format a UTC datetime as ``YYYY-MM-DDTHH:MM:SS.000Z`` (matches old Nordpool shape)."""
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


async def fetch_day_ahead(target_date: date, region: str = "FI", *, token: str) -> dict[str, Any]:
    """Fetch ENTSO-E day-ahead prices for *region* on *target_date*.

    Args:
        target_date: Delivery date (UTC). Prices are returned for the 24-hour
            window ``[target_date 00:00Z, target_date+1 00:00Z)``.
        region: Bidding zone code (FI, SE3, SE4, EE, LT, LV).
        token: ENTSO-E Web API Security Token.

    Returns:
        Dict with the same shape the previous Nordpool client returned, so
        ``normalize_nordpool_response`` can consume it unchanged.

    Raises:
        KeyError: if *region* is not in ``REGION_TO_EIC``.
        EntsoeAuthError: if the API returns HTTP 401.
        EntsoeNoDataError: if the API returns an Acknowledgement document.
        httpx.HTTPStatusError: on other non-2xx responses.
        httpx.TimeoutException: if the request times out.
    """
    loop = asyncio.get_running_loop()
    xml_text = await loop.run_in_executor(None, _fetch_sync, target_date, region, token)
    parsed = _parse_xml(xml_text, target_date)
    logger.debug("ENTSO-E %s %s: %d hourly rows", region, target_date, len(parsed["rows"]))
    return parsed
