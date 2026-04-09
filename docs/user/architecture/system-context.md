# System Context (C4 Level 1)

Stocklens sits between the user and a set of free financial data APIs. It ingests, normalises, and stores price data, then exposes it via a REST API and Grafana dashboards.

```mermaid
graph TD
    User(["👤 User\n(personal use)"])

    subgraph Stocklens
        API["REST API\n:8000"]
        Scheduler["Scheduler\n(APScheduler cron)"]
        DB[("PostgreSQL\n:5432")]
    end

    subgraph External APIs
        YF["yfinance\n(US + FI prices)"]
        FRED["FRED\n(macro data — Phase 2)"]
        FH["Finnhub\n(fundamentals — Phase 2)"]
    end

    Grafana["Grafana\n(dashboards — Phase 3)"]

    User -->|"query prices / scores"| API
    API -->|"reads"| DB
    Scheduler -->|"fetches EOD prices"| YF
    Scheduler -->|"writes"| DB
    Grafana -->|"SQL queries"| DB
    User -->|"views dashboards"| Grafana

    style Stocklens fill:#e8f4fd,stroke:#4a90d9
    style External APIs fill:#fff8e8,stroke:#d4a017
```

## Scope boundary

Everything inside the **Stocklens** box is owned, deployed, and operated by this project. External APIs are third-party services consumed over HTTPS — Stocklens has no write access to them.

| Actor | Role |
|---|---|
| User | Queries the REST API, views Grafana dashboards |
| yfinance | Primary source of EOD price data (US + Helsinki exchange) |
| FRED | Macro-economic indicators (Phase 2) |
| Finnhub | Fundamental data supplement (Phase 2) |
| Grafana | Read-only dashboards over PostgreSQL (Phase 3) |
