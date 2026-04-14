-- Migration: 003_energy_alerts
-- Description: Threshold-based alert rules and fired alert events for electricity prices
-- Applies to: all environments

BEGIN;

-- ─────────────────────────────────────────────────────────────────────────────
-- energy_alert_rule — per-region threshold configuration
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS energy_alert_rule (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    region_code     TEXT           NOT NULL REFERENCES energy_region(code),
    threshold_c_kwh NUMERIC(8,4)   NOT NULL,   -- fire when daily peak total_c_kwh exceeds this
    active          BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT energy_alert_rule_threshold_positive CHECK (threshold_c_kwh > 0)
);

COMMENT ON TABLE  energy_alert_rule                 IS 'Threshold rules for electricity price spike alerts per region.';
COMMENT ON COLUMN energy_alert_rule.threshold_c_kwh IS 'Alert fires when the daily peak total_c_kwh (spot+tax+VAT) exceeds this value.';


-- ─────────────────────────────────────────────────────────────────────────────
-- energy_alert — fired alert events (one per rule per delivery date)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS energy_alert (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rule_id         BIGINT         NOT NULL REFERENCES energy_alert_rule(id) ON DELETE CASCADE,
    region_code     TEXT           NOT NULL REFERENCES energy_region(code),
    price_date      DATE           NOT NULL,
    peak_c_kwh      NUMERIC(8,4)   NOT NULL,   -- actual peak total_c_kwh that triggered the alert
    peak_hour       SMALLINT       NOT NULL,   -- hour (0-23) of the peak price
    threshold_c_kwh NUMERIC(8,4)   NOT NULL,   -- snapshot of the threshold at fire time
    fired_at        TIMESTAMPTZ    NOT NULL DEFAULT now(),

    CONSTRAINT energy_alert_region_date_rule_uq UNIQUE (rule_id, price_date),
    CONSTRAINT energy_alert_peak_hour_check     CHECK (peak_hour BETWEEN 0 AND 23)
);

CREATE INDEX IF NOT EXISTS energy_alert_region_date_idx
    ON energy_alert (region_code, price_date DESC);

COMMENT ON TABLE  energy_alert              IS 'One row per fired alert — deduplicated by (rule, date) so re-runs are idempotent.';
COMMENT ON COLUMN energy_alert.peak_c_kwh   IS 'Actual peak price that triggered the alert (total_c_kwh incl. VAT+tax).';
COMMENT ON COLUMN energy_alert.peak_hour    IS 'Hour of the peak price (0-23 local delivery time).';


-- ─────────────────────────────────────────────────────────────────────────────
-- Default alert rule: FI region, 30 c/kWh threshold
-- ─────────────────────────────────────────────────────────────────────────────
INSERT INTO energy_alert_rule (region_code, threshold_c_kwh)
VALUES ('FI', 30.00)
ON CONFLICT DO NOTHING;

COMMIT;
