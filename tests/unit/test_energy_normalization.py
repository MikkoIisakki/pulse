"""Unit tests for energy price normalisation.

Tests pure functions only — no DB, no HTTP.
"""

from datetime import date
from decimal import Decimal

from app.normalization.energy_price import normalize_nordpool_response

# ─── Fixtures ─────────────────────────────────────────────────────────────────

_REGION_FI = {
    "code": "FI",
    "vat_rate": Decimal("0.255"),
    "electricity_tax_c_kwh": Decimal("2.24"),
}

_VALID_NORDPOOL_RESPONSE = {
    "deliveryDateCET": "2025-01-15",
    "currency": "EUR",
    "rows": [
        {
            "startTime": f"2025-01-15T{h:02d}:00:00.000Z",
            "endTime": f"2025-01-15T{h+1:02d}:00:00.000Z",
            "value": 80.00 + h,  # EUR/MWh — one distinct value per hour
        }
        for h in range(24)
    ],
}


# ─── Tests ────────────────────────────────────────────────────────────────────


def test_returns_24_rows_for_full_day() -> None:
    """A complete day-ahead response produces exactly 24 EnergyPrice objects."""
    prices = normalize_nordpool_response(
        _VALID_NORDPOOL_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    assert len(prices) == 24


def test_price_date_parsed_correctly() -> None:
    """All rows carry the delivery date extracted from the response."""
    prices = normalize_nordpool_response(
        _VALID_NORDPOOL_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    assert all(p["price_date"] == date(2025, 1, 15) for p in prices)


def test_hours_are_zero_to_23() -> None:
    """Hour values cover 0-23 inclusive."""
    prices = normalize_nordpool_response(
        _VALID_NORDPOOL_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    assert sorted(p["hour"] for p in prices) == list(range(24))


def test_spot_c_kwh_is_eur_mwh_divided_by_10() -> None:
    """spot_c_kwh = price_eur_mwh / 10 (no tax, no VAT)."""
    prices = normalize_nordpool_response(
        _VALID_NORDPOOL_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    hour0 = next(p for p in prices if p["hour"] == 0)
    expected_spot = Decimal("80.00") / Decimal("10")
    assert hour0["spot_c_kwh"] == expected_spot


def test_total_c_kwh_includes_tax_and_vat() -> None:
    """total_c_kwh = (spot_c_kwh + electricity_tax) * (1 + vat_rate), rounded to 4dp."""
    prices = normalize_nordpool_response(
        _VALID_NORDPOOL_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    hour0 = next(p for p in prices if p["hour"] == 0)
    spot = Decimal("80.00") / Decimal("10")  # 8.0000
    tax = Decimal("2.24")
    vat = Decimal("0.255")
    expected_total = ((spot + tax) * (1 + vat)).quantize(Decimal("0.0001"))
    assert hour0["total_c_kwh"] == expected_total


def test_negative_price_produces_valid_row() -> None:
    """Negative EUR/MWh prices (common during wind surplus) are accepted."""
    response = {
        "deliveryDateCET": "2025-01-15",
        "currency": "EUR",
        "rows": [
            {
                "startTime": "2025-01-15T02:00:00.000Z",
                "endTime": "2025-01-15T03:00:00.000Z",
                "value": -15.00,
            }
        ],
    }
    prices = normalize_nordpool_response(response, region=_REGION_FI, ingest_run_id=1)
    assert len(prices) == 1
    assert prices[0]["price_eur_mwh"] == Decimal("-15.00")
    assert prices[0]["spot_c_kwh"] == Decimal("-1.50")


def test_region_code_copied_to_each_row() -> None:
    """region_code field matches the region config passed in."""
    prices = normalize_nordpool_response(
        _VALID_NORDPOOL_RESPONSE, region=_REGION_FI, ingest_run_id=1
    )
    assert all(p["region_code"] == "FI" for p in prices)


def test_ingest_run_id_copied_to_each_row() -> None:
    """ingest_run_id is present in every row."""
    prices = normalize_nordpool_response(
        _VALID_NORDPOOL_RESPONSE, region=_REGION_FI, ingest_run_id=42
    )
    assert all(p["ingest_run_id"] == 42 for p in prices)


def test_empty_rows_returns_empty_list() -> None:
    """An empty rows list produces no output — caller handles NoDataError."""
    response = {"deliveryDateCET": "2025-01-15", "currency": "EUR", "rows": []}
    prices = normalize_nordpool_response(response, region=_REGION_FI, ingest_run_id=1)
    assert prices == []
