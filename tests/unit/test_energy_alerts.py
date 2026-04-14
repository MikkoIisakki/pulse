"""Unit tests for the electricity threshold alert engine.

Pure logic tests — no DB, no HTTP.
"""

from datetime import date
from decimal import Decimal

from app.alerts.energy import check_threshold_alerts

_REGION_CODE = "FI"
_PRICE_DATE = date(2025, 1, 15)

_RULE = {
    "id": 1,
    "region_code": _REGION_CODE,
    "threshold_c_kwh": Decimal("30.00"),
    "active": True,
}


def _hourly_prices(peak_total_c_kwh: float, peak_hour: int = 14) -> list[dict]:
    """Build 24 hourly price rows with one configurable peak hour."""
    rows = []
    for h in range(24):
        rows.append(
            {
                "hour": h,
                "total_c_kwh": Decimal(str(peak_total_c_kwh))
                if h == peak_hour
                else Decimal("10.00"),
            }
        )
    return rows


def test_alert_fires_when_peak_exceeds_threshold() -> None:
    """Peak above threshold → alert dict returned."""
    prices = _hourly_prices(peak_total_c_kwh=35.50, peak_hour=16)
    alerts = check_threshold_alerts(prices, rules=[_RULE], price_date=_PRICE_DATE)
    assert len(alerts) == 1
    assert alerts[0]["rule_id"] == 1
    assert alerts[0]["peak_c_kwh"] == Decimal("35.50")
    assert alerts[0]["peak_hour"] == 16
    assert alerts[0]["threshold_c_kwh"] == Decimal("30.00")
    assert alerts[0]["price_date"] == _PRICE_DATE
    assert alerts[0]["region_code"] == _REGION_CODE


def test_no_alert_when_peak_below_threshold() -> None:
    """Peak below threshold → empty list."""
    prices = _hourly_prices(peak_total_c_kwh=25.00)
    alerts = check_threshold_alerts(prices, rules=[_RULE], price_date=_PRICE_DATE)
    assert alerts == []


def test_no_alert_when_peak_equals_threshold() -> None:
    """Exactly at threshold → no alert (strictly greater-than)."""
    prices = _hourly_prices(peak_total_c_kwh=30.00)
    alerts = check_threshold_alerts(prices, rules=[_RULE], price_date=_PRICE_DATE)
    assert alerts == []


def test_no_alert_when_prices_empty() -> None:
    """No price data → no alert."""
    alerts = check_threshold_alerts([], rules=[_RULE], price_date=_PRICE_DATE)
    assert alerts == []


def test_no_alert_when_no_active_rules() -> None:
    """Inactive rule → no alert."""
    inactive_rule = {**_RULE, "active": False}
    prices = _hourly_prices(peak_total_c_kwh=50.00)
    alerts = check_threshold_alerts(prices, rules=[inactive_rule], price_date=_PRICE_DATE)
    assert alerts == []


def test_multiple_rules_each_evaluated_independently() -> None:
    """Two rules with different thresholds → only the breached one fires."""
    low_rule = {**_RULE, "id": 1, "threshold_c_kwh": Decimal("20.00")}
    high_rule = {**_RULE, "id": 2, "threshold_c_kwh": Decimal("40.00")}
    prices = _hourly_prices(peak_total_c_kwh=35.00)
    alerts = check_threshold_alerts(prices, rules=[low_rule, high_rule], price_date=_PRICE_DATE)
    assert len(alerts) == 1
    assert alerts[0]["rule_id"] == 1


def test_negative_prices_do_not_trigger_alert() -> None:
    """Negative spot prices (wind surplus) never exceed a positive threshold."""
    prices = [{"hour": h, "total_c_kwh": Decimal("-5.00")} for h in range(24)]
    alerts = check_threshold_alerts(prices, rules=[_RULE], price_date=_PRICE_DATE)
    assert alerts == []
