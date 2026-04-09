# Key Flows

## EOD Price Ingest

Triggered by the scheduler at market close (17:00 UTC for Helsinki, 21:30 UTC for US).

```mermaid
sequenceDiagram
    participant Scheduler
    participant Ingest as ingestion/<br/>us_ingest.py
    participant YF as yfinance_client.py<br/>(thread pool)
    participant Norm as normalization/<br/>price.py
    participant Repo as storage/<br/>repository.py
    participant DB as PostgreSQL

    Scheduler->>Ingest: run_us_ingest(pool)
    Ingest->>DB: create_ingest_run(market="US")
    DB-->>Ingest: run_id

    Ingest->>DB: get_active_assets(market="US")
    DB-->>Ingest: [AAPL, MSFT, …] (50 tickers)

    loop Each asset (max 5 concurrent)
        Ingest->>YF: fetch_eod(symbol, lookback_days=5)
        YF-->>Ingest: {symbol, rows: [...]}
        Ingest->>Repo: save_raw_snapshot(run_id, payload)
        Repo->>DB: INSERT INTO raw_source_snapshot
        Ingest->>Norm: normalize_price_rows(rows)
        Norm-->>Ingest: validated rows (bad rows dropped)
        Ingest->>Repo: upsert_daily_prices(prices)
        Repo->>DB: INSERT … ON CONFLICT DO UPDATE
    end

    Ingest->>DB: finish_ingest_run(run_id, status, counts)
```

## API Price History Query

A read-only path — no computation happens at request time.

```mermaid
sequenceDiagram
    participant Client
    participant Router as api/routers/<br/>assets.py
    participant Repo as storage/<br/>repository.py
    participant DB as PostgreSQL

    Client->>Router: GET /v1/assets/AAPL/prices?from=2024-01-01&limit=90
    Router->>Repo: get_price_history(symbol, from, to, limit)
    Repo->>DB: SELECT … FROM daily_price JOIN asset …
    DB-->>Repo: rows
    Repo-->>Router: list[dict]
    Router-->>Client: 200 OK · JSON array of PriceOut
```

## Health Check (Task 1.7)

Checks whether the most recent ingest run finished within the last 25 hours.

```mermaid
sequenceDiagram
    participant Client
    participant Router as api/routers/<br/>health.py
    participant DB as PostgreSQL

    Client->>Router: GET /v1/health/ready
    Router->>DB: SELECT max(finished_at) FROM ingest_run WHERE status='success'
    DB-->>Router: last_success_at
    alt last_success_at within 25h
        Router-->>Client: 200 OK · {"status": "ok"}
    else stale or no runs
        Router-->>Client: 200 OK · {"status": "degraded", "reason": "…"}
    end
```
