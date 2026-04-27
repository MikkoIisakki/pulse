# ADR-004: ENTSO-E Transparency Platform replaces Nordpool for day-ahead prices

**Date**: 2026-04-27
**Status**: Accepted
**Deciders**: architect, orchestrator

## Context

The energy ingest (task 2.2) was built on Nordpool's unauthenticated public
endpoint `dataportal-api.nordpoolgroup.com/api/DayAheadPrices`. As of 2026-04-26
that endpoint returns HTTP 401 for historical dates and empty 200 responses for
current dates without authentication (RISK-014, Critical, score 20). The
electricity ingest produces zero rows; this blocks Phase 2 DoD and the Phase 7.1
electricity App Store release.

Constraints:
- Free or near-free running cost (Phase A target ≈$20/month total).
- Coverage of all currently seeded bidding zones: FI, SE3, SE4, EE, LT, LV.
- Durable: not a scrape against an undocumented public endpoint.
- Must not change the public surface of `run_energy_ingest(pool, target_date=...)`.

## Options Considered

### Option 1: ENTSO-E Transparency Platform (`web-api.tp.entsoe.eu/api`)
- **Pros**: Free with self-service registration; pan-EU coverage including all
  six seeded bidding zones; official EU TSO data, durable and unlikely to be
  walled off; documented `documentType=A44` day-ahead price contract.
- **Cons**: XML response (vs JSON); requires user to register and provide a
  Web API Security Token; query uses bidding-zone EIC codes (extra mapping
  table); rate limits exist (400 req/min, generous for daily ingest).

### Option 2: Re-authenticate against Nordpool dataportal
- **Pros**: Smallest code change — keep current normaliser nearly intact.
- **Cons**: No public free tier documented; ToS for the dataportal API is
  unclear; the fact that they silently 401'd unauthenticated traffic suggests
  the next step is paid licensing. High risk of having to migrate again.

### Option 3: Country-specific aggregators (elprisetjustnu.se, fingrid open data, etc.)
- **Pros**: Free, simple JSON.
- **Cons**: Per-country integration effort; does not cleanly cover Finland
  (elprisetjustnu.se is SE only, fingrid does not publish Nordpool spot in the
  shape we need); two or three providers required to cover the existing six
  regions. Anti-corruption layer would proliferate.

## Decision

Chose Option 1 (ENTSO-E). Free, official, single integration covers all seeded
regions, and the EIC mapping is small and well-documented. Token is supplied
by the user via env var `ENTSOE_API_TOKEN` (added to `Settings` and
`.env.example`); the agent cannot self-register.

The XML schema is parsed with the stdlib `xml.etree.ElementTree` to avoid
adding a new direct dependency (`lxml` is a transitive dep but not used
elsewhere in our code).

## Bidding zone → EIC mapping

| Region | Country | EIC code |
|---|---|---|
| FI  | Finland       | `10YFI-1--------U` |
| SE3 | Sweden North  | `10Y1001A1001A46L` |
| SE4 | Sweden South  | `10Y1001A1001A47J` |
| EE  | Estonia       | `10Y1001A1001A39I` |
| LT  | Lithuania     | `10YLT-1001A0008Q` |
| LV  | Latvia        | `10YLV-1001A00074` |

For day-ahead prices `in_Domain == out_Domain`. `periodStart` / `periodEnd`
are UTC, formatted `YYYYMMDDHHMM`. We request `00:00 → 24:00` of the requested
delivery date (UTC), which maps onto a 24-hour window of `<Point>` entries
inside one or more `<TimeSeries><Period>` blocks.

## Consequences

**Positive**:
- Energy ingest works again (assuming a token is provisioned).
- Public function signatures unchanged — scheduler, repo, normalisation
  caller code requires no edits.
- Single provider for all six regions; future additions (NO, DK1/DK2) are a
  one-line EIC mapping change.

**Negative / trade-offs**:
- Ingest cannot run in CI or in fresh local dev without a token; tests mock
  the HTTP layer with `respx`.
- XML parsing adds modest complexity vs the previous JSON shape.
- Adds a manual operator step: register at transparency.entsoe.eu (Settings →
  Web API Security Token), set `ENTSOE_API_TOKEN` in `.env`, restart workers.

**Revisit when**:
- ENTSO-E imposes auth changes, paywalls, or rate-limit enforcement that
  breaks daily ingest.
- We need sub-hourly resolution (15-minute settlement period rollout in 2025+)
  — at that point parse `<Point>` resolution attribute properly rather than
  assuming PT60M.
