-- Migration: 001_core_schema
-- Description: Core tables for asset master data, EOD prices, ingestion audit trail
-- Applies to: all environments

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- asset — securities master data
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS asset (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    symbol      TEXT        NOT NULL,
    name        TEXT        NOT NULL,
    exchange    TEXT        NOT NULL,   -- e.g. NASDAQ, NYSE, HEL
    market      TEXT        NOT NULL,   -- US | FI
    currency    TEXT        NOT NULL,   -- USD | EUR
    active      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT asset_symbol_exchange_uq UNIQUE (symbol, exchange),
    CONSTRAINT asset_market_check       CHECK (market IN ('US', 'FI')),
    CONSTRAINT asset_currency_check     CHECK (currency IN ('USD', 'EUR'))
);

COMMENT ON TABLE  asset            IS 'Securities master data — one row per ticker.';
COMMENT ON COLUMN asset.symbol     IS 'Ticker as used by the data source, e.g. AAPL or NOKIA.HE.';
COMMENT ON COLUMN asset.market     IS 'US = US markets (S&P 500 / Nasdaq); FI = Helsinki exchange.';


-- ─────────────────────────────────────────────────────────────────────────────
-- ingest_run — audit log for each ingestion job execution
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ingest_run (
    id                BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    started_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at       TIMESTAMPTZ,
    status            TEXT        NOT NULL DEFAULT 'running',  -- running | success | failed
    market            TEXT        NOT NULL,                    -- US | FI | ALL
    assets_attempted  INT,
    assets_succeeded  INT,
    error_message     TEXT,

    CONSTRAINT ingest_run_status_check CHECK (status IN ('running', 'success', 'failed')),
    CONSTRAINT ingest_run_market_check CHECK (market IN ('US', 'FI', 'ALL'))
);

COMMENT ON TABLE  ingest_run               IS 'One row per ingestion job execution — used for health checks and alerting.';
COMMENT ON COLUMN ingest_run.status        IS 'running while in progress; success / failed on completion.';
COMMENT ON COLUMN ingest_run.started_at    IS 'Queried by /v1/health/ready to detect stale ingest (threshold: 25h).';


-- ─────────────────────────────────────────────────────────────────────────────
-- daily_price — end-of-day OHLCV data
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS daily_price (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    asset_id      BIGINT      NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    ingest_run_id BIGINT      REFERENCES ingest_run(id) ON DELETE SET NULL,
    price_date    DATE        NOT NULL,
    open          NUMERIC(16, 6),
    high          NUMERIC(16, 6),
    low           NUMERIC(16, 6),
    close         NUMERIC(16, 6) NOT NULL,
    adj_close     NUMERIC(16, 6),
    volume        BIGINT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT daily_price_asset_date_uq UNIQUE (asset_id, price_date)
);

CREATE INDEX IF NOT EXISTS daily_price_asset_date_idx
    ON daily_price (asset_id, price_date DESC);

COMMENT ON TABLE  daily_price              IS 'End-of-day OHLCV prices; one row per asset per trading day.';
COMMENT ON COLUMN daily_price.adj_close    IS 'Adjusted close accounting for splits and dividends (source: yfinance).';
COMMENT ON COLUMN daily_price.ingest_run_id IS 'Which ingest run inserted this row — for lineage tracking.';


-- ─────────────────────────────────────────────────────────────────────────────
-- raw_source_snapshot — immutable raw API responses for audit and replay
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS raw_source_snapshot (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ingest_run_id BIGINT      REFERENCES ingest_run(id) ON DELETE SET NULL,
    source        TEXT        NOT NULL,   -- yfinance | finnhub | fred | ...
    symbol        TEXT        NOT NULL,
    snapshot_date DATE        NOT NULL,
    raw_payload   JSONB       NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS raw_snapshot_symbol_date_idx
    ON raw_source_snapshot (symbol, snapshot_date DESC);

COMMENT ON TABLE  raw_source_snapshot             IS 'Immutable raw API responses — never updated, only inserted.';
COMMENT ON COLUMN raw_source_snapshot.source      IS 'Data source identifier, e.g. yfinance, finnhub, fred.';
COMMENT ON COLUMN raw_source_snapshot.raw_payload IS 'Full JSON response as received from the source.';

COMMIT;
