# ADR-005: Interval-based time-series schema for any cadence

**Date**: 2026-04-28
**Status**: Accepted
**Deciders**: architect, orchestrator

## Context

The energy domain stored prices in `energy_price` keyed by
`(region_code, price_date DATE, hour SMALLINT 0..23)`. This shape was correct
when ENTSO-E published one delivery period per hour (`<resolution>PT60M</resolution>`).

In 2026 the Nordic/Baltic bidding zones (FI, EE, LT, LV) switched to
**15-minute resolution** (`PT15M`, 96 points per day). The existing schema
silently collapsed 4 quarter-hours into the **last** value (PK conflict on
`(region, date, hour)` with `ON CONFLICT … DO UPDATE`). Verified locally on
2026-04-28: rows landed but the prices were wrong.

ADR-004 already noted this as the next failure mode for the ingest:

> Revisit when … rollout of 15-minute settlement periods (would require
> resolution-aware Point parsing).

The user's directive: do not aggregate-to-hourly. Adopt a schema that supports
**arbitrary bucket widths** so the same convention serves stocks intraday,
crypto OHLCV, and any future intraday series, not just energy.

Constraints:

- The user's existing local DB already has rows in the old hour-of-day shape;
  the migration must backfill those rows, not lose them.
- API contract may change cleanly — no compatibility layer (user instruction).
- The migration must be safe in CI (fresh DB) and in dev (existing rows).

## Options Considered

### Option 1: Keep `(date, hour)` PK, alias 15-min slots into hour buckets

- **Pros**: Smallest schema change.
- **Cons**: Either silently aggregates (wrong) or requires fractional hours,
  which `SMALLINT 0..23` cannot represent. Doesn't generalise to other cadences
  (1-min crypto, 5-min intraday). Locks the platform out of intraday series.

### Option 2: Aggregate-to-hourly at ingest

- **Pros**: Schema unchanged.
- **Cons**: Throws away resolution we paid for. Cheap-slot recommendations are
  wrong (the cheap quarter is averaged into a more expensive hour). Sets a bad
  precedent for crypto/stocks intraday: we'd never get the resolution we want.
  Explicitly rejected by the user.

### Option 3: One table per cadence (`energy_price_15m`, `energy_price_60m`, …)

- **Pros**: Each table has a fixed-width assumption.
- **Cons**: Cross-cadence queries become unions; routing logic in the API
  must know which table to read. Schema multiplies for every new cadence.
  Doesn't reflect the reality that one bidding zone may emit different
  resolutions on different days (DST, maintenance windows, regulator changes).

### Option 4 (chosen): Interval-based time series

Store a UTC start, a UTC end, and a width-in-minutes column on every row:

| Column | Type | Meaning |
|---|---|---|
| `interval_start` | `TIMESTAMPTZ NOT NULL` | UTC start of the bucket (PK part with the entity). |
| `interval_end` | `TIMESTAMPTZ NOT NULL` | UTC end (exclusive). |
| `interval_minutes` | `INT NOT NULL CHECK (interval_minutes > 0)` | Bucket width — 1, 5, 15, 60, 1440. |

- **Pros**:
  - Same shape works for 15-min energy, 1-min crypto, 5-min stocks intraday,
    daily aggregates. One convention across the platform.
  - Mixed cadences in one table are valid: a region may publish PT60M one day
    and PT15M the next.
  - Date-range queries use a functional index on
    `((interval_start AT TIME ZONE 'UTC')::date)` — cheap.
  - DST-safe: rows are always UTC; client computes local time for display.
- **Cons**:
  - Two timestamp columns per row instead of one date+SMALLINT (≈16 extra
    bytes/row — negligible vs. the value stored).
  - Slightly heavier PK (`(region_code, interval_start)` with timestamptz vs.
    `(region_code, price_date, hour)` with date+smallint).

## Decision

Adopt Option 4 as the **platform convention** for any time-bucketed series.
Apply it to the energy domain immediately (`energy_price`, `energy_alert`).

Future intraday tables (crypto OHLCV, stocks intraday, anything sub-daily that
isn't already a `daily_price`) MUST use the same three columns and the same
`(entity, interval_start)` unique key pattern. The existing `daily_price` table
is unchanged: it's already correctly daily, and the convention applies to any
*future* intraday or alternative-cadence series.

## Schema migration

`db/migrations/004_energy_interval_schema.sql` (DESTRUCTIVE comment per
RISK-005):

1. Add `interval_start TIMESTAMPTZ`, `interval_end TIMESTAMPTZ`,
   `interval_minutes INT` to `energy_price`. Backfill from existing
   `(price_date, hour)` rows assuming hourly cadence:
   `interval_start = (price_date::timestamp + (hour || ' hours')::interval) AT TIME ZONE 'UTC'`,
   `interval_end = interval_start + INTERVAL '1 hour'`,
   `interval_minutes = 60`.
2. Drop `price_date`, `hour`, the old unique constraint and the old check.
3. Add new unique constraint `(region_code, interval_start)` and
   `CHECK (interval_minutes > 0)`.
4. Add functional date-index: `(region_code, ((interval_start AT TIME ZONE 'UTC')::date))`.
5. Same on `energy_alert`: replace `peak_hour SMALLINT` with
   `peak_interval_start TIMESTAMPTZ`. Keep `price_date DATE` on `energy_alert`
   only as the calendar day the alert is **about** (human-friendly summary).

## API contract changes

Clean break — no `?legacy=true` mode.

### `GET /v1/energy/prices?region=&date=`

```json
{
  "region": "FI",
  "date": "2026-04-29",
  "interval_minutes": 15,
  "prices": [
    {"interval_start": "2026-04-29T00:00:00Z",
     "interval_end":   "2026-04-29T00:15:00Z",
     "price_eur_mwh": 45.20,
     "spot_c_kwh":     4.52,
     "total_c_kwh":    8.46},
    …
  ]
}
```

### `GET /v1/energy/cheap-intervals?region=&date=&limit=`

Renamed from `/cheap-hours`. Old route deleted (clean break per user
instruction). Same row shape as `/prices`, plus a `rank` field starting at 1,
plus `interval_minutes` at top level.

### `GET /v1/energy/alerts?region=`

`peak_hour` replaced with `peak_interval_start` (ISO8601 UTC). `price_date`
kept (calendar day the alert is about).

## Consequences

**Positive**:

- Energy ingest now stores 96 distinct price points per day on PT15M zones
  (FI, EE, LT, LV) and 24 on PT60M zones (SE3, SE4) without lossy aggregation.
- Cheap-slot recommendations are correct: the user's app can highlight
  "23:15-23:30 is the cheapest quarter today" when the data warrants it.
- Convention is established for crypto OHLCV (Phase 6) and any future
  stocks intraday work.
- DST is handled: a 23-hour spring-forward day is naturally 23 (or 92) rows;
  a 25-hour fall-back day is 25 (or 100). No padding logic required.

**Negative / trade-offs**:

- One-time API break for any external consumer of `/v1/energy/prices`,
  `/v1/energy/cheap-hours`, or `/v1/energy/alerts`. Pre-release; acceptable.
- Migration is destructive (drops `price_date`, `hour` columns) — flagged with
  `-- DESTRUCTIVE` per RISK-005. Existing rows are preserved via backfill.
- Grafana SQL queries are rewritten in the same change.

**Revisit when**:

- A series needs millisecond resolution (the `INT` minutes column would
  become the wrong unit; revisit to add `interval_seconds` instead).
- Postgres becomes the bottleneck for the date-range index — at that point
  consider TimescaleDB (already deferred per ADR-002, with explicit revisit
  trigger).

## References

- ADR-002: PostgreSQL over TimescaleDB (defer hypertables; revisit if needed).
- ADR-004: ENTSO-E replaces Nordpool — the migration trigger that surfaced
  PT15M data and exposed the schema's hour-only assumption.
- RISK-005: Schema migration safety. This migration is DESTRUCTIVE-flagged
  and backfills before drop.
- RISK-014: Now fully resolved (the PT15M caveat in the review trigger is
  removed by this ADR).
