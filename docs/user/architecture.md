# Architecture Overview

Stocklens is a **modular monolith** — a single deployable unit organised into well-defined internal modules. This keeps operations simple (one image, one deploy) while enforcing the same boundaries a microservices design would require.

## Quick map

| Diagram | What it shows |
|---|---|
| [System Context](architecture/system-context.md) | What Stocklens is, who uses it, and which external services it depends on (C4 Level 1) |
| [Containers](architecture/containers.md) | Deployable units (API, scheduler, worker, database) and how they communicate (C4 Level 2) |
| [Module Boundaries](architecture/modules.md) | Internal modules within the backend, dependency rules, and Clean Architecture layers (C4 Level 3) |
| [Data Model](architecture/data-model.md) | ER diagram for all database tables with column-level detail |
| [Key Flows](architecture/sequences.md) | Sequence diagrams for EOD ingest, price history query, and health check |

## Dependency rule

All modules follow **Clean Architecture** — dependencies point inward only:

```
api/ ──────────────────────────────┐
jobs/ ─────────────────────────────┤
ingestion/ · normalization/ ───────┤  → storage/ → PostgreSQL
signals/ · scoring/ · ranking/ ────┤
alerts/ ───────────────────────────┘
                         ↑
                      common/
                  (imported by all)
```

No module may import from `api/` or `jobs/`. All SQL lives exclusively in `storage/`. This is enforced by the architecture fitness function test at `tests/architecture/test_dependency_rules.py`.

## Key decisions

| Decision | Choice | Rationale |
|---|---|---|
| Architecture style | Modular monolith | Simpler ops, single transaction boundary, clear upgrade path |
| Web framework | FastAPI | Async, typed, auto-generates OpenAPI |
| Database driver | asyncpg | Fastest async PostgreSQL driver for Python |
| Scheduler | APScheduler | Cron-style without a broker; upgrades to Redis/RQ when needed |
| Data source | yfinance | Free EOD data covering both US and Helsinki exchange |
| Validation | Pydantic v2 | Runtime type safety on settings and API responses |
| Package manager | uv | Fast, reproducible, replaces pip+venv |
