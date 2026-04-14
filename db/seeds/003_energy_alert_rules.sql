-- Seed: 003_energy_alert_rules
-- Description: Default threshold alert rules for energy regions
-- Depends on: 002_energy_regions (energy_region must be seeded first)

BEGIN;

-- Default FI rule: alert when daily peak exceeds 30 c/kWh (incl. VAT+tax)
INSERT INTO energy_alert_rule (region_code, threshold_c_kwh)
VALUES ('FI', 30.00)
ON CONFLICT DO NOTHING;

COMMIT;
