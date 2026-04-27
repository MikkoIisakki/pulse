"""Unit tests for the ENTSO-E Transparency Platform day-ahead client.

The client returns rows shaped exactly like the previous Nordpool client so
that ``app.normalization.energy_price.normalize_nordpool_response`` continues
to work without modification:

    {
        "deliveryDateCET": "YYYY-MM-DD",
        "currency": "EUR",
        "rows": [
            {"startTime": "<ISO8601 UTC>", "endTime": "<ISO8601 UTC>", "value": <float>},
            ...
        ],
    }

All HTTP calls are mocked with respx — no real network traffic.
"""

from __future__ import annotations

from datetime import date

import httpx
import pytest
import respx

from app.ingestion.entsoe_client import (
    REGION_TO_EIC,
    EntsoeAuthError,
    EntsoeNoDataError,
    fetch_day_ahead,
)

ENTSOE_HOST = "web-api.tp.entsoe.eu"


def _build_xml(prices: list[float], position_count: int | None = None) -> str:
    """Build a minimal valid ENTSO-E A44 Publication_MarketDocument.

    One TimeSeries with one Period containing one Point per supplied price.
    """
    count = position_count if position_count is not None else len(prices)
    points = "\n".join(
        f"<Point><position>{i + 1}</position><price.amount>{p}</price.amount></Point>"
        for i, p in enumerate(prices[:count])
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">
  <TimeSeries>
    <Period>
      <timeInterval>
        <start>2025-01-15T00:00Z</start>
        <end>2025-01-16T00:00Z</end>
      </timeInterval>
      <resolution>PT60M</resolution>
      {points}
    </Period>
  </TimeSeries>
</Publication_MarketDocument>"""


def _empty_xml() -> str:
    """ENTSO-E returns an Acknowledgement_MarketDocument with reason 'No matching data found'."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<Acknowledgement_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-1:acknowledgementdocument:8:1">
  <Reason>
    <code>999</code>
    <text>No matching data found</text>
  </Reason>
</Acknowledgement_MarketDocument>"""


# ─── Region/EIC mapping ───────────────────────────────────────────────────────


def test_region_to_eic_covers_all_seeded_regions() -> None:
    """The hardcoded mapping must cover every region in db/seeds/002_energy_regions.sql."""
    assert REGION_TO_EIC["FI"] == "10YFI-1--------U"
    assert REGION_TO_EIC["SE3"] == "10Y1001A1001A46L"
    assert REGION_TO_EIC["SE4"] == "10Y1001A1001A47J"
    assert REGION_TO_EIC["EE"] == "10Y1001A1001A39I"
    assert REGION_TO_EIC["LT"] == "10YLT-1001A0008Q"
    assert REGION_TO_EIC["LV"] == "10YLV-1001A00074"


# ─── Query construction ──────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_builds_correct_query_params() -> None:
    """The request URL must use the right token, document type, EIC, and UTC period."""
    captured: dict[str, str] = {}

    def _capture(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.url.params))
        return httpx.Response(200, text=_build_xml([10.0] * 24))

    respx.route(host=ENTSOE_HOST).mock(side_effect=_capture)

    await fetch_day_ahead(date(2025, 1, 15), region="FI", token="abc-token")

    assert captured["securityToken"] == "abc-token"
    assert captured["documentType"] == "A44"
    assert captured["in_Domain"] == "10YFI-1--------U"
    assert captured["out_Domain"] == "10YFI-1--------U"
    assert captured["periodStart"] == "202501150000"
    assert captured["periodEnd"] == "202501160000"


@respx.mock
@pytest.mark.asyncio
async def test_unknown_region_raises_keyerror() -> None:
    """A region not in the EIC mapping is a programming error, not a runtime fallback."""
    with pytest.raises(KeyError):
        await fetch_day_ahead(date(2025, 1, 15), region="ZZ", token="t")


# ─── Response parsing ────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_returns_24_rows_for_normal_day() -> None:
    """A standard 24-hour day produces exactly 24 hourly rows."""
    prices = [50.0 + h for h in range(24)]
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(200, text=_build_xml(prices)))

    result = await fetch_day_ahead(date(2025, 1, 15), region="FI", token="t")

    assert result["currency"] == "EUR"
    assert result["deliveryDateCET"] == "2025-01-15"
    assert len(result["rows"]) == 24


@respx.mock
@pytest.mark.asyncio
async def test_row_shape_matches_normaliser_contract() -> None:
    """Each row carries startTime, endTime, value — the keys the normaliser reads."""
    respx.route(host=ENTSOE_HOST).mock(
        return_value=httpx.Response(200, text=_build_xml([42.5] * 24))
    )

    result = await fetch_day_ahead(date(2025, 1, 15), region="FI", token="t")

    first = result["rows"][0]
    assert first["startTime"] == "2025-01-15T00:00:00.000Z"
    assert first["endTime"] == "2025-01-15T01:00:00.000Z"
    assert first["value"] == 42.5
    last = result["rows"][23]
    assert last["startTime"] == "2025-01-15T23:00:00.000Z"
    assert last["endTime"] == "2025-01-16T00:00:00.000Z"


@respx.mock
@pytest.mark.asyncio
async def test_negative_prices_preserved() -> None:
    """ENTSO-E publishes negative prices during surplus; they must survive parsing."""
    prices = [-15.0] + [10.0] * 23
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(200, text=_build_xml(prices)))

    result = await fetch_day_ahead(date(2025, 1, 15), region="FI", token="t")

    assert result["rows"][0]["value"] == -15.0


# ─── Error handling ──────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_http_401_raises_auth_error() -> None:
    """Bad/missing token surfaces as a typed EntsoeAuthError, not a generic HTTPStatusError."""
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(401, text="Unauthorized"))

    with pytest.raises(EntsoeAuthError):
        await fetch_day_ahead(date(2025, 1, 15), region="FI", token="bad")


@respx.mock
@pytest.mark.asyncio
async def test_empty_acknowledgement_raises_no_data_error() -> None:
    """A 200 with Acknowledgement_MarketDocument means no data for the requested window."""
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(200, text=_empty_xml()))

    with pytest.raises(EntsoeNoDataError):
        await fetch_day_ahead(date(2025, 1, 15), region="FI", token="t")


# ─── DST behaviour (documents the chosen contract) ───────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_dst_spring_forward_returns_23_rows() -> None:
    """On EU spring-forward day, ENTSO-E publishes 23 hourly points; client returns 23 rows.

    The normaliser already accepts variable-length inputs, so the client's job is
    to faithfully report what ENTSO-E sends — not to pad to 24.
    """
    prices = [40.0] * 23
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(200, text=_build_xml(prices)))

    result = await fetch_day_ahead(date(2025, 3, 30), region="FI", token="t")

    assert len(result["rows"]) == 23


@respx.mock
@pytest.mark.asyncio
async def test_dst_fall_back_returns_25_rows() -> None:
    """On EU autumn fall-back day, ENTSO-E publishes 25 hourly points; client returns 25."""
    prices = [40.0] * 25
    respx.route(host=ENTSOE_HOST).mock(return_value=httpx.Response(200, text=_build_xml(prices)))

    result = await fetch_day_ahead(date(2025, 10, 26), region="FI", token="t")

    assert len(result["rows"]) == 25
