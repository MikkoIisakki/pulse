"""Health check endpoints.

GET /v1/health/ready — returns 200 OK when healthy, 200 with status=degraded
when the last ingest run finished more than max_ingest_age_hours ago,
or 503 when the database is unreachable.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Any

from fastapi import APIRouter, Depends, Response

from app.api.dependencies import get_pool
from app.common.config import Settings
from app.common.config import settings as default_settings

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/health", tags=["health"])

_STALE_REASON = "ingest stale or never run"


def get_settings() -> Settings:
    """Dependency — allows override in tests."""
    return default_settings


@router.get("/ready")
async def readiness(
    response: Response,
    cfg: Annotated[Settings, Depends(get_settings)],
    pool: Annotated[Any, Depends(get_pool)],
) -> dict[str, str]:
    """Return system readiness status.

    Status values:
    - ``ok``: database reachable, last successful ingest within threshold
    - ``degraded``: database reachable but ingest is stale or has never run
    - ``unavailable``: database unreachable (HTTP 503)
    """
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT MAX(finished_at) AS last_finished
                  FROM ingest_run
                 WHERE status = 'success'
                """
            )
    except Exception:
        logger.exception("Database unreachable during health check")
        response.status_code = 503
        return {"status": "unavailable"}

    last_finished: datetime | None = row["last_finished"] if row else None
    threshold = timedelta(hours=cfg.max_ingest_age_hours)
    now = datetime.now(UTC)

    # asyncpg returns TIMESTAMPTZ as tz-aware datetimes — no .replace() needed
    if last_finished is None or (now - last_finished) > threshold:
        return {"status": "degraded", "reason": _STALE_REASON}

    return {"status": "ok"}
