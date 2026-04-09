# Platform Requirements

**Project**: Pulse — White-label Screener Platform
**Last updated**: 2026-04-09
**Status**: Active

---

## Platform Vision

A single codebase that powers multiple domain-focused screener apps. Each app ingests structured time-series data from a specific domain (electricity prices, stocks, crypto), scores or ranks it, and delivers threshold alerts via push notification. Users install one focused app — not a multi-domain aggregator.

---

## Platform-level Requirements (all domains)

### PLT-01 — Domain-configurable pipeline

```
As a developer
I want to add a new domain by dropping a config file and an ingestion module
So that the platform is extensible without changing shared code
```

**Acceptance criteria:**
```gherkin
Given a new domain config exists at config/domains/<domain>.yaml
When the scheduler starts
Then it loads and runs the new domain's ingest job at the configured time
And stores results in the shared DB schema without schema changes
```

---

### PLT-02 — Unified health check across domains

```
As an operator
I want a single health endpoint that reflects all active domain ingest jobs
So that I can monitor the whole platform from one place
```

**Acceptance criteria:**
```gherkin
Given multiple domains are active
When I call GET /v1/health/ready
Then the response reflects the staleness of every domain's last ingest
And status is "degraded" if any domain has not ingested within its configured threshold
```

---

### PLT-03 — Push notification alerts

```
As a user
I want to receive a push notification when a tracked metric crosses my configured threshold
So that I notice the event without opening the app
```

**Acceptance criteria:**
```gherkin
Given I have registered my device and set a threshold alert
When an ingest run produces a value that crosses my threshold
Then I receive a push notification within 5 minutes
And the notification shows the metric name, current value, and threshold
And tapping the notification opens the relevant screen in the app
```

---

### PLT-04 — Secure authentication

```
As a user
I want to authenticate so that my alert preferences are stored and private
So that my configuration persists across devices
```

**Acceptance criteria:**
```gherkin
Given I have a valid API token
When I make any request to a protected endpoint
Then the request succeeds with 200
When I make the same request with no token or an invalid token
Then the request fails with 401
```

---

### PLT-05 — Raw data audit trail

```
As an operator
I want every ingested API response stored verbatim
So that I can replay normalisation without re-fetching and audit data lineage
```

**Acceptance criteria:**
```gherkin
Given an ingest run completes for any domain
Then every raw API response is stored in raw_source_snapshot before normalisation
And the snapshot links to the ingest_run that produced it
And re-running normalisation against the snapshot produces the same output
```

---

### PLT-06 — White-label mobile build

```
As a developer
I want to build a separate mobile app binary for each domain from one codebase
So that each app has its own name, icon, and App Store listing
```

**Acceptance criteria:**
```gherkin
Given an EAS build profile exists for a domain (e.g. --profile energy)
When I run eas build --profile energy
Then the resulting binary has the energy domain's name, icon, and bundle ID
And it connects to the energy domain's API endpoint
And the stock app binary is a separate, independently submittable artifact
```

---

## Electricity Domain Requirements (Phase 2 — priority)

### ELY-01 — View tomorrow's hourly prices

```
As a user
I want to see tomorrow's hourly electricity spot prices
So that I can plan when to run high-consumption appliances
```

**Acceptance criteria:**
```gherkin
Given Nordpool has published tomorrow's day-ahead prices (published ~13:00 CET)
When I open the electricity app
Then I see 24 hourly price bars for tomorrow
And prices are shown in c/kWh including Finnish VAT (25.5%)
And the cheapest and most expensive hours are visually highlighted
And the data is available by 14:00 CET at the latest
```

---

### ELY-02 — Price spike alert

```
As a user
I want to receive an alert when tomorrow's peak price exceeds my threshold
So that I can plan to avoid expensive periods
```

**Acceptance criteria:**
```gherkin
Given I have set a spike threshold of X c/kWh
When tomorrow's prices are ingested and any hour exceeds X c/kWh
Then I receive a push notification by 14:00 CET
And the notification shows the peak price and the hours affected
When no hour exceeds X c/kWh
Then no notification is sent
```

---

### ELY-03 — Cheap hours summary

```
As a user
I want a "best hours today" summary
So that I immediately know when to run my dishwasher, EV charger, or sauna
```

**Acceptance criteria:**
```gherkin
Given today's hourly prices are available
When I view the cheap hours screen
Then I see the 5 cheapest remaining hours of today ranked lowest to highest
And each shows the hour window (e.g. 02:00–03:00) and price in c/kWh
And hours already passed are excluded
```

---

### ELY-04 — 30-day price trend

```
As a user
I want to see the last 30 days of daily average prices
So that I understand whether current prices are high or low relative to recent history
```

**Acceptance criteria:**
```gherkin
Given at least 7 days of historical data exist
When I view the trend screen
Then I see a line chart of daily average prices for the available period (up to 30 days)
And the current day's average is visually marked
And the chart shows the 30-day average as a reference line
```

---

### ELY-05 — Region selection

```
As a user
I want to select my electricity region (FI, SE3, NO1, etc.)
So that I see prices relevant to my location
```

**Acceptance criteria:**
```gherkin
Given I select region "FI" in settings
When I view any price screen
Then all prices shown are for the FI Nordpool bidding zone
And my region selection persists across app restarts
When I change region
Then all screens immediately reflect the new region
```

---

## Stock Domain Requirements (Phase 4–5)

### STK-01 — Ingest EOD prices (US + FI)

```
As a user
I want US and Finnish stock prices ingested daily after market close
So that scores are based on fresh data
```

*Implementation complete in Phase 1.*

---

### STK-02 — View ranked assets

```
As a user
I want to see a ranked list of assets scored by composite signal
So that I can identify which stocks match my screening criteria today
```

**Acceptance criteria:**
```gherkin
Given scores have been computed for today
When I call GET /v1/rankings?domain=stocks&market=US
Then I receive assets sorted by composite score descending
And each entry shows symbol, name, score, score delta vs yesterday, and top contributing factor
And the response time is under 200ms
```

---

### STK-03 — Score explanation

```
As a user
I want to see which factors drove an asset's score
So that I understand why it ranks where it does
```

**Acceptance criteria:**
```gherkin
Given an asset has a computed score
When I call GET /v1/rankings/AAPL
Then I receive the composite score plus individual factor scores and weights
And each factor shows value, signal type (bullish/neutral/bearish), and weight used
And unavailable factors are listed as "unavailable" with weight 0
```

---

### STK-04 — Price history query

```
As a user
I want to query historical prices for any tracked asset
So that I can review price context around a screening result
```

*Implementation complete in Phase 1.*

---

### STK-05 — Stock screening alert

```
As a user
I want to receive an alert when an asset's composite score crosses a threshold
So that I notice when a stock enters or exits my screening criteria
```

**Acceptance criteria:**
```gherkin
Given I have set an alert: "notify me when any US stock score exceeds 80"
When the daily scoring run produces a score above 80
Then I receive a push notification within 5 minutes of scoring completing
And the notification shows the asset symbol, score, and top factor
```

---

### STK-06 — Backtest scoring weights

```
As a user
I want to validate that past composite scores predicted subsequent returns
So that I can trust the model before acting on its results
```

**Acceptance criteria:**
```gherkin
Given at least 6 months of historical score_snapshot data exists
When I run the backtest module
Then it produces a report showing: top-quintile score cohort return vs benchmark
And the report includes Sharpe ratio, max drawdown, and hit rate
And the report flags any factor with negative contribution to returns
```

---

## Crypto Domain Requirements (Phase 6)

### CRY-01 — Ingest top crypto by market cap

```
As a user
I want daily OHLCV data for the top 50 cryptocurrencies by market cap
So that the screener covers the most liquid part of the crypto market
```

**Acceptance criteria:**
```gherkin
Given the CoinGecko ingest job runs at the scheduled time
When it completes
Then OHLCV data for the top 50 coins by market cap is stored for today
And raw responses are stored in raw_source_snapshot
And the ingest_run record shows assets_attempted = 50
```

---

### CRY-02 — Crypto screening score

```
As a user
I want crypto assets scored by technical signals (RS vs BTC, RSI, volume)
So that I can identify technically strong crypto setups
```

**Acceptance criteria:**
```gherkin
Given OHLCV data exists for today
When the scoring job runs
Then each coin receives a composite score from: RS vs BTC, RSI, MACD, volume spike
And a ranked list is available via GET /v1/rankings?domain=crypto
And scores are computed only for coins with at least 30 days of history
```

---

### CRY-03 — Crypto alert

```
As a user
I want to receive an alert when a coin's RSI crosses overbought/oversold levels
So that I notice potential turning points
```

**Acceptance criteria:**
```gherkin
Given I have set an RSI alert for BTC at oversold (RSI < 30)
When the daily scoring run computes RSI < 30 for BTC
Then I receive a push notification within 5 minutes
And the notification shows the coin name, current RSI, and the threshold
```

---

## Non-Functional Requirements

### NFR-01 — API response time
All read endpoints respond in < 200ms at p95. All data is pre-computed — no heavy aggregation at request time.

### NFR-02 — Ingest reliability
Each domain ingest job must complete within 30 minutes of its scheduled trigger. Failures must be recorded in `ingest_run` with an error message within 60 seconds of failure.

### NFR-03 — Alert delivery latency
Push notifications fire within 5 minutes of the triggering ingest completing.

### NFR-04 — Test coverage
No module ships below 70% test coverage. Architecture fitness function tests enforce module boundary rules on every CI run.

### NFR-05 — Zero manual setup
A new developer must reach a fully working system with `git clone && cp .env.example .env && make up && make migrate && make seed`. No additional manual steps.

### NFR-06 — Data traceability
100% of ingested values must link to a `raw_source_snapshot` row. No derived value exists without an auditable source.

### NFR-07 — Screening language
No user-facing copy, API response field, or documentation uses the words "advice", "recommend", or "should buy". All output is framed as screening criteria matches.
