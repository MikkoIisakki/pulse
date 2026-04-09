# Containers (C4 Level 2)

The system is a **modular monolith** — a single Docker image run as three processes, each with a distinct responsibility. This keeps operations simple while enforcing the same module boundaries a microservices design would require.

```mermaid
graph TD
    User(["👤 User"])

    subgraph "Docker Compose (single host)"
        API["api\nFastAPI · :8000\n\nServes REST endpoints.\nAll responses are pre-computed;\nno scoring or aggregation at request time."]
        Scheduler["scheduler\nAPScheduler\n\nCron-triggered ingest jobs.\nFI at 17:00 UTC, US at 21:30 UTC."]
        Worker["worker\nPython process\n\nExecutes jobs dispatched\nby the scheduler."]
        DB[("db\nPostgreSQL 16\n:5432\n\nSingle source of truth.\nStores prices, factors,\nscores, alerts.")]
    end

    YF["yfinance\n(external)"]

    User -->|"HTTP"| API
    API -->|"asyncpg"| DB
    Scheduler -->|"dispatches job"| Worker
    Worker -->|"HTTPS"| YF
    Worker -->|"asyncpg"| DB

    style API fill:#d4edda,stroke:#28a745
    style Scheduler fill:#d1ecf1,stroke:#17a2b8
    style Worker fill:#d1ecf1,stroke:#17a2b8
    style DB fill:#f8d7da,stroke:#dc3545
```

## Container responsibilities

| Container | Image | Start command | Scales? |
|---|---|---|---|
| `api` | `./backend` | `uvicorn app.main:app` | Yes (Phase 4) |
| `scheduler` | `./backend` | `python -m app.jobs.scheduler` | No — single instance |
| `worker` | `./backend` | `python -m app.jobs.worker` | Yes (Redis/RQ in Phase 3) |
| `db` | `postgres:16-alpine` | — | No (single node, Phase 4 if needed) |

All three application containers are built from the same `./backend` Dockerfile and share the same codebase — they differ only in their startup command and environment variables.
