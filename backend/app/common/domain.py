"""Domain config loader — typed view over ``config/domains/<name>.yaml``.

Each Pulse white-label app is described by one YAML file under
``config/domains/``. This module loads and validates that file into a
typed Pydantic model so application code can read structured values
instead of duplicating them across SQL seeds, scheduler hardcodes, and
Python constants.

See ADR-006 for the convention.

Usage:
    from app.common.domain import load_domain_config

    cfg = load_domain_config("energy")
    cfg.schedule.ingest_cron.hour       # 11
    cfg.region("FI").vat_rate           # Decimal('0.2550')
    cfg.alert_thresholds_c_kwh["FI"]    # Decimal('30.00')
"""

from __future__ import annotations

from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

# config/domains/ at the repo root, two levels above backend/app/common/.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG_DIR = _REPO_ROOT / "config" / "domains"


class DomainConfigError(RuntimeError):
    """Raised when a domain config file is missing or malformed."""


class CronConfig(BaseModel):
    """A cron trigger expressed in fields APScheduler understands."""

    hour: int = Field(..., ge=0, le=23)
    minute: int = Field(..., ge=0, le=59)
    timezone: str = "UTC"


class ScheduleConfig(BaseModel):
    """Daily ingest schedule for a domain."""

    ingest_cron: CronConfig
    job_id: str
    job_name: str


class RegionConfig(BaseModel):
    """Per-region pricing parameters (energy domain).

    Stocks/crypto domains will likely add their own ``MarketConfig`` /
    ``AssetConfig`` blocks instead of overloading this one.
    """

    code: str
    name: str
    country: str
    vat_rate: Decimal
    electricity_tax_c_kwh: Decimal


class DomainConfig(BaseModel):
    """Top-level domain config.

    Fields are intentionally minimal: they cover only what energy actually
    uses today. Add fields per domain as concrete needs arise; do not
    pre-design for hypothetical future domains.
    """

    name: str
    display_name: str
    description: str = ""
    schedule: ScheduleConfig
    regions: list[RegionConfig] = []
    alert_thresholds_c_kwh: dict[str, Decimal] = {}

    @model_validator(mode="after")
    def _alerts_reference_known_regions(self) -> DomainConfig:
        codes = {r.code for r in self.regions}
        unknown = set(self.alert_thresholds_c_kwh) - codes
        if unknown:
            raise ValueError(
                f"alert_thresholds_c_kwh references unknown regions: {sorted(unknown)}"
            )
        return self

    def region(self, code: str) -> RegionConfig:
        """Return the region with *code*, or raise KeyError."""
        for r in self.regions:
            if r.code == code:
                return r
        raise KeyError(f"Unknown region '{code}' in domain '{self.name}'")


@lru_cache(maxsize=8)
def load_domain_config(name: str, *, config_dir: Path | None = None) -> DomainConfig:
    """Load and validate ``config/domains/<name>.yaml``.

    Cached per ``(name, config_dir)``; tests can pass an explicit ``config_dir``
    to load fixture files without polluting the production cache.
    """
    base = config_dir if config_dir is not None else _DEFAULT_CONFIG_DIR
    path = base / f"{name}.yaml"
    if not path.is_file():
        raise DomainConfigError(f"Domain config not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as e:
        raise DomainConfigError(f"Invalid YAML in {path}: {e}") from e
    if not isinstance(raw, dict):
        raise DomainConfigError(f"{path}: top-level must be a mapping, got {type(raw).__name__}")
    return DomainConfig.model_validate(raw)
