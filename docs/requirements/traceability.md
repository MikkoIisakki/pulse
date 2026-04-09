# Requirement Traceability Matrix

| ID | User Story | Phase | Domain | MoSCoW | AC Count | Design Artifact | Test File(s) | Status |
|----|---|---|---|---|---|---|---|---|
| PLT-01 | Domain-configurable pipeline | 3 | Platform | Must | 1 | — | — | Pending |
| PLT-02 | Unified health check across domains | 2 | Platform | Must | 1 | — | test_health_api.py | Partial |
| PLT-03 | Push notification alerts | 3 | Platform | Must | 1 | — | — | Pending |
| PLT-04 | Secure authentication | 3 | Platform | Must | 1 | — | — | Pending |
| PLT-05 | Raw data audit trail | 1 | Platform | Must | 1 | — | — | Done |
| PLT-06 | White-label mobile build | 3 | Platform | Must | 1 | — | — | Pending |
| ELY-01 | View tomorrow's hourly electricity prices | 2 | Energy | Must | 1 | — | — | Pending |
| ELY-02 | Price spike alert | 2 | Energy | Must | 1 | — | — | Pending |
| ELY-03 | Cheap hours summary | 2 | Energy | Must | 1 | — | — | Pending |
| ELY-04 | 30-day price trend | 2 | Energy | Should | 1 | — | — | Pending |
| ELY-05 | Region selection | 2 | Energy | Should | 1 | — | — | Pending |
| STK-01 | Ingest EOD prices (US + FI) | 1 | Stocks | Must | — | — | test_us_ingest.py, test_fi_ingest.py | Done |
| STK-02 | View ranked assets | 4 | Stocks | Must | 1 | — | — | Pending |
| STK-03 | Score explanation | 4 | Stocks | Must | 1 | — | — | Pending |
| STK-04 | Price history query | 1 | Stocks | Must | — | — | test_assets_api.py | Done |
| STK-05 | Stock screening alert | 5 | Stocks | Must | 1 | — | — | Pending |
| STK-06 | Backtest scoring weights | 5 | Stocks | Should | 1 | — | — | Pending |
| CRY-01 | Ingest top crypto by market cap | 6 | Crypto | Must | 1 | — | — | Pending |
| CRY-02 | Crypto screening score | 6 | Crypto | Must | 1 | — | — | Pending |
| CRY-03 | Crypto alert | 6 | Crypto | Should | 1 | — | — | Pending |
| NFR-01 | API p95 response < 200ms | 1 | Platform | Must | 1 | nfr-matrix.md | — | Pending |
| NFR-02 | Ingest completes within 30 min | 1 | Platform | Must | 1 | — | — | Pending |
| NFR-03 | Alert delivery < 5 min | 3 | Platform | Must | 1 | — | — | Pending |
| NFR-04 | Test coverage ≥ 70% per module | 1 | Platform | Must | 1 | — | CI (--cov-fail-under=70) | Done |
| NFR-05 | Zero manual setup (make up) | 1 | Platform | Must | 1 | — | Manual | Done |
| NFR-06 | 100% data traceability via raw_source_snapshot | 1 | Platform | Must | 1 | — | — | Done |
| NFR-07 | No advice/recommendation wording in any output | All | Platform | Must | 1 | — | — | Ongoing |

*Update AC Count, Design Artifact, and Test File columns as work progresses.*
