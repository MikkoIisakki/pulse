# ADR-002: Plain PostgreSQL over TimescaleDB

**Date**: 2026-04-07
**Status**: Accepted
**Deciders**: architect, orchestrator

## Context

The system stores time-series data (daily OHLCV prices, factor snapshots, score snapshots) that will grow over time. TimescaleDB is a PostgreSQL extension designed specifically for time-series data, offering automatic partitioning (hypertables), continuous aggregates, and compression. The question is whether to use it from the start or stick with plain PostgreSQL.

The initial universe is ~65 tickers × 252 trading days/year ≈ 16,000 rows/year for prices alone. Factor and score snapshots add similar volumes. This is small by database standards.

## Options Considered

### Option 1: TimescaleDB from day one
- **Pros**: Hypertable partitioning for fast time-range queries, continuous aggregates for pre-computed rollups, compression after retention period, native Grafana datasource awareness
- **Cons**: Adds a PostgreSQL extension that must be managed in the Docker image and migrations, hypertable DDL is non-standard SQL, `CREATE EXTENSION` must succeed before schema creation, adds ops complexity for a volume that doesn't justify it yet, extension version pinning adds a dependency vector

### Option 2: Plain PostgreSQL 16
- **Pros**: Standard SQL, no extension management, migrations are simpler, Grafana PostgreSQL datasource works identically, all query patterns at current scale are fast with standard indexes, upgrade path to TimescaleDB is additive (can add the extension later without data migration)
- **Cons**: No automatic partitioning, continuous aggregates require scheduled materialized views instead of native TimescaleDB syntax, may need manual optimization if data volume grows significantly

### Option 3: InfluxDB or other purpose-built time-series DB
- **Pros**: Optimized for time-series at extreme scale
- **Cons**: No relational model (can't join with `asset`, `watchlist`, etc.), separate system to operate, no standard SQL, Grafana plugin required, complete mismatch for the relational parts of the schema

## Decision

Chose Option 2: plain PostgreSQL 16. At the current data volume, well-indexed PostgreSQL performs equivalently to TimescaleDB. The relational schema (assets, watchlists, alert rules, users) benefits from standard SQL and joins. TimescaleDB can be added as an extension later with no data migration required — the upgrade path is preserved.

## Consequences

**Positive**:
- Standard SQL everywhere, no extension-specific syntax to learn or maintain
- Simpler Docker setup (`postgres:16-alpine`, no custom image)
- Migrations are plain SQL, runnable with any `psql` client
- Grafana datasource needs no special configuration

**Negative / trade-offs**:
- Continuous aggregates (e.g. daily OHLCV from intraday data) require scheduled `REFRESH MATERIALIZED VIEW` jobs instead of native TimescaleDB syntax
- Time-range query performance degrades if data volume reaches millions of rows per table — manual partitioning would then be required

**Revisit when**:
- p99 query latency on `daily_price` or `factor_snapshot` range queries exceeds 200ms at actual data volume
- Universe expands to >500 tickers with intraday data (>1M rows/day)
- TimescaleDB continuous aggregates would meaningfully simplify the scheduler logic
