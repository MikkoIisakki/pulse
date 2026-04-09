"""Normalise raw Nordpool day-ahead API responses into storage-ready dicts.

Anti-corruption layer: translates Nordpool JSON → domain EnergyPrice records.
No I/O. Pure transformation.
"""

from datetime import date
from decimal import Decimal
from typing import Any


def normalize_nordpool_response(
    raw: dict[str, Any],
    *,
    region: dict[str, Any],
    ingest_run_id: int,
) -> list[dict[str, Any]]:
    """Convert a Nordpool day-ahead response to energy_price insert dicts.

    Args:
        raw: Raw JSON response from Nordpool API.
        region: energy_region row dict with code, vat_rate, electricity_tax_c_kwh.
        ingest_run_id: FK for audit trail.

    Returns:
        List of dicts ready for ``repo.upsert_energy_prices``.
        Empty list if the response contains no hourly rows.
    """
    rows = raw.get("rows", [])
    if not rows:
        return []

    delivery_date = date.fromisoformat(raw["deliveryDateCET"][:10])
    region_code: str = region["code"]
    vat_rate = Decimal(str(region["vat_rate"]))
    electricity_tax = Decimal(str(region["electricity_tax_c_kwh"]))

    result = []
    for row in rows:
        # Derive hour from startTime UTC string: "2025-01-15T14:00:00.000Z" -> 14
        start_time: str = row["startTime"]
        hour = int(start_time[11:13])

        price_eur_mwh = Decimal(str(row["value"])).quantize(Decimal("0.0001"))
        spot_c_kwh = (price_eur_mwh / Decimal("10")).quantize(Decimal("0.0001"))
        total_c_kwh = ((spot_c_kwh + electricity_tax) * (1 + vat_rate)).quantize(Decimal("0.0001"))

        result.append(
            {
                "region_code": region_code,
                "ingest_run_id": ingest_run_id,
                "price_date": delivery_date,
                "hour": hour,
                "price_eur_mwh": price_eur_mwh,
                "spot_c_kwh": spot_c_kwh,
                "total_c_kwh": total_c_kwh,
            }
        )

    return result
