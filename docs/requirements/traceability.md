# Requirement Traceability Matrix

| ID | User Story | Phase | MoSCoW | AC Count | Design Artifact | Test File(s) | Status |
|----|---|---|---|---|---|---|---|
| US-01 | Ingest EOD prices for US top 50 S&P 500 + Nasdaq tech | 1 | Must | — | — | — | Pending |
| US-02 | Ingest Finnish (.HE) EOD prices | 1 | Must | — | — | — | Pending |
| US-03 | Store raw API responses (audit trail) | 1 | Must | — | — | — | Pending |
| US-04 | Schedule daily ingestion after market close (US + FI) | 1 | Must | — | — | — | Pending |
| US-05 | Query asset price history via API | 1 | Must | — | — | — | Pending |
| US-06 | List assets with metadata | 1 | Must | — | — | — | Pending |
| NFR-01 | API p95 response < 200ms | 1 | Must | 1 | nfr-matrix.md | test_api_performance.py | Pending |
| NFR-02 | Test coverage ≥ 80% per module | 1 | Must | 1 | — | CI (--cov-fail-under=80) | Pending |
| NFR-03 | New dev setup < 15 min (make up) | 1 | Must | 1 | — | Manual | Pending |
| US-07 | Compute long-term signals (EPS, revenue, margins, ROE) | 2 | Must | — | — | — | Pending |
| US-08 | Compute short-term signals (RS, RSI, MACD, volume) | 2 | Must | — | — | — | Pending |
| US-09 | Composite score per asset per day (long + short horizon) | 2 | Must | — | — | — | Pending |
| US-10 | View ranked assets via API | 2 | Must | — | — | — | Pending |
| US-11 | Score is explainable (factor contributions visible) | 2 | Must | — | — | — | Pending |
| US-12 | Define threshold-based alert rules | 3 | Must | — | — | — | Pending |
| US-13 | Receive alert events when rules trigger | 3 | Must | — | — | — | Pending |
| US-14 | Grafana pipeline health dashboard | 3 | Must | — | — | — | Pending |
| US-15 | Grafana market overview dashboard | 3 | Should | — | — | — | Pending |
| US-16 | Backtest: did past scores predict returns? | 4 | Should | — | — | — | Pending |
| US-17 | Next.js watchlist + screener UI | 4 | Could | — | — | — | Pending |

*Update AC Count, Design Artifact, and Test File columns as work progresses.*
