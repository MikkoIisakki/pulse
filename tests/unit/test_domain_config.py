"""Unit tests for the domain config loader (task 3.1, ADR-006).

The loader reads ``config/domains/<name>.yaml`` and produces a typed
DomainConfig. These tests exercise the production energy.yaml plus
fixture YAML strings written to a tmp_path so we can validate edge cases
without polluting the production cache.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.common.domain import (
    DomainConfig,
    DomainConfigError,
    load_domain_config,
)


def _write(tmp_path: Path, name: str, content: str) -> Path:
    """Write a domain YAML to tmp_path/<name>.yaml and return the dir."""
    (tmp_path / f"{name}.yaml").write_text(content)
    return tmp_path


_VALID_YAML = """\
name: demo
display_name: Demo
description: minimal valid config
schedule:
  ingest_cron:
    hour: 11
    minute: 30
    timezone: UTC
  job_id: demo_ingest
  job_name: Demo ingest
regions:
  - code: AA
    name: Region A
    country: AA
    vat_rate: 0.20
    electricity_tax_c_kwh: 1.50
alert_thresholds_c_kwh:
  AA: 25.00
"""


# ─── Production energy.yaml ──────────────────────────────────────────────────


def test_loads_production_energy_config() -> None:
    """The shipped energy.yaml must validate and expose all six bidding zones."""
    cfg = load_domain_config("energy")
    assert isinstance(cfg, DomainConfig)
    assert cfg.name == "energy"
    codes = {r.code for r in cfg.regions}
    assert codes == {"FI", "SE3", "SE4", "EE", "LV", "LT"}


def test_energy_fi_matches_seed_values() -> None:
    """FI region in YAML must match db/seeds/002_energy_regions.sql."""
    cfg = load_domain_config("energy")
    fi = cfg.region("FI")
    assert fi.vat_rate == Decimal("0.2550")
    assert fi.electricity_tax_c_kwh == Decimal("2.2400")
    assert fi.country == "FI"


def test_energy_schedule_is_1130_utc() -> None:
    """Energy ingest cron must match the deployed scheduler — 11:30 UTC."""
    cfg = load_domain_config("energy")
    assert cfg.schedule.ingest_cron.hour == 11
    assert cfg.schedule.ingest_cron.minute == 30
    assert cfg.schedule.ingest_cron.timezone == "UTC"
    assert cfg.schedule.job_id == "energy_price_ingest"


def test_energy_alert_threshold_for_fi() -> None:
    cfg = load_domain_config("energy")
    assert cfg.alert_thresholds_c_kwh["FI"] == Decimal("30.00")


# ─── Loader behaviour ────────────────────────────────────────────────────────


def test_loads_from_custom_directory(tmp_path: Path) -> None:
    config_dir = _write(tmp_path, "demo", _VALID_YAML)
    cfg = load_domain_config("demo", config_dir=config_dir)
    assert cfg.display_name == "Demo"
    assert cfg.region("AA").vat_rate == Decimal("0.20")


def test_unknown_domain_raises_domain_config_error(tmp_path: Path) -> None:
    with pytest.raises(DomainConfigError, match="not found"):
        load_domain_config("nope-doesnt-exist", config_dir=tmp_path)


def test_invalid_yaml_raises_domain_config_error(tmp_path: Path) -> None:
    config_dir = _write(tmp_path, "broken", "not: [valid: yaml: here")
    with pytest.raises(DomainConfigError, match="Invalid YAML"):
        load_domain_config("broken", config_dir=config_dir)


def test_top_level_must_be_mapping(tmp_path: Path) -> None:
    config_dir = _write(tmp_path, "list", "- one\n- two\n")
    with pytest.raises(DomainConfigError, match="must be a mapping"):
        load_domain_config("list", config_dir=config_dir)


# ─── Schema validation ───────────────────────────────────────────────────────


def test_alert_threshold_referencing_unknown_region_rejected(tmp_path: Path) -> None:
    from pydantic import ValidationError

    yaml_text = _VALID_YAML.replace("AA: 25.00", "AA: 25.00\n  ZZ: 99.00")
    config_dir = _write(tmp_path, "bad-alerts", yaml_text)
    with pytest.raises(ValidationError) as exc_info:
        load_domain_config("bad-alerts", config_dir=config_dir)
    assert "ZZ" in str(exc_info.value)


def test_cron_hour_out_of_range_rejected(tmp_path: Path) -> None:
    from pydantic import ValidationError

    yaml_text = _VALID_YAML.replace("hour: 11", "hour: 24")
    config_dir = _write(tmp_path, "bad-cron", yaml_text)
    with pytest.raises(ValidationError):
        load_domain_config("bad-cron", config_dir=config_dir)


def test_region_lookup_unknown_code_raises_keyerror() -> None:
    cfg = load_domain_config("energy")
    with pytest.raises(KeyError, match="Unknown region 'ZZ'"):
        cfg.region("ZZ")
