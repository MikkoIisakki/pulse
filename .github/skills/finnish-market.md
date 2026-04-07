---
name: finnish-market
description: Helsinki Stock Exchange specifics — ticker format, market hours, key stocks, and data availability quirks.
---

# Finnish Market (Helsinki Stock Exchange)

## Ticker Format

Yahoo Finance uses `.HE` suffix for Helsinki-listed stocks:

```python
# Format: {TICKER}.HE
"NOKIA.HE"   # Nokia
"STERV.HE"   # Stora Enso R
"NESTE.HE"   # Neste
"KNEBV.HE"   # Kone
"SAMPO.HE"   # Sampo
"UPM.HE"     # UPM-Kymmene
"WRT1V.HE"   # Wärtsilä
"ORNBV.HE"   # Orion B
"ELISA.HE"   # Elisa
"TEM1V.HE"   # Telia Finland (if listed)
"TIETO.HE"   # TietoEVRY
"METSO.HE"   # Metso
"FORTUM.HE"  # Fortum
"KEMIRA.HE"  # Kemira
"QTCOM.HE"   # Qt Group
```

## Market Hours

Helsinki Stock Exchange (Nasdaq Helsinki):
- **Open**: 10:00 EET (Eastern European Time, UTC+2 / UTC+3 DST)
- **Close**: 18:30 EET
- **Pre-market**: 09:00–10:00
- **Holidays**: Finnish national holidays + Midsummer, Christmas Eve

```python
from zoneinfo import ZoneInfo

HELSINKI_TZ = ZoneInfo("Europe/Helsinki")
HELSINKI_OPEN  = time(10, 0)
HELSINKI_CLOSE = time(18, 30)

# Finnish market closes ~2.5 hours after US opens
# Schedule FI EOD ingestion at 19:00 Helsinki time (safe after close)
```

## Currency

All Helsinki prices are in **EUR**. Store `currency = 'EUR'` in the `asset` table. When computing relative strength vs US stocks, convert to a common base or keep comparisons within-market.

## Data Availability via yfinance

```python
import yfinance as yf

ticker = yf.Ticker("NOKIA.HE")

# Price history — works well
df = ticker.history(period="2y", interval="1d")

# Fundamentals — partial coverage
info = ticker.info
# Usually available: marketCap, trailingPE, forwardPE, dividendYield
# Often missing: analyst estimates, detailed income statement line items

# Financial statements — limited for smaller FI stocks
financials = ticker.financials  # may return empty DataFrame
```

**Coverage quality by company size**:
- Large caps (Nokia, Neste, Kone, Sampo): good coverage
- Mid caps: price data good, fundamentals partial
- Small caps: price data only, fundamentals mostly missing

## Benchmark for Relative Strength

Use `^OMXH25` (OMX Helsinki 25 index) as the Finnish market benchmark:

```python
benchmark = yf.Ticker("^OMXH25")
df_benchmark = benchmark.history(period="1y", interval="1d")
```

For US stocks, use `^GSPC` (S&P 500) or `QQQ` (Nasdaq).

## Sector Classification

Finnish stocks don't always map cleanly to GICS sectors via yfinance. Store the raw `sector` from `ticker.info` and normalize manually if needed. Key Finnish sectors:
- **Technology**: Nokia, Qt Group, TietoEVRY
- **Industrials**: Kone, Wärtsilä, Metso, Cargotec
- **Materials**: UPM, Stora Enso, Kemira
- **Energy**: Neste, Fortum
- **Finance**: Sampo, Nordea (if listed)
- **Healthcare**: Orion, Terveystalo

## Seed Tickers

```sql
-- Finnish stocks for initial seed
INSERT INTO asset (symbol, name, exchange, market, sector, currency) VALUES
('NOKIA.HE',  'Nokia',      'HSE', 'FI', 'Technology',  'EUR'),
('NESTE.HE',  'Neste',      'HSE', 'FI', 'Energy',      'EUR'),
('KNEBV.HE',  'Kone',       'HSE', 'FI', 'Industrials', 'EUR'),
('SAMPO.HE',  'Sampo',      'HSE', 'FI', 'Finance',     'EUR'),
('UPM.HE',    'UPM',        'HSE', 'FI', 'Materials',   'EUR'),
('STERV.HE',  'Stora Enso', 'HSE', 'FI', 'Materials',   'EUR'),
('WRT1V.HE',  'Wärtsilä',   'HSE', 'FI', 'Industrials', 'EUR'),
('ORNBV.HE',  'Orion',      'HSE', 'FI', 'Healthcare',  'EUR'),
('ELISA.HE',  'Elisa',      'HSE', 'FI', 'Telecom',     'EUR'),
('QTCOM.HE',  'Qt Group',   'HSE', 'FI', 'Technology',  'EUR'),
('TIETO.HE',  'TietoEVRY',  'HSE', 'FI', 'Technology',  'EUR'),
('METSO.HE',  'Metso',      'HSE', 'FI', 'Industrials', 'EUR'),
('FORTUM.HE', 'Fortum',     'HSE', 'FI', 'Energy',      'EUR'),
('KEMIRA.HE', 'Kemira',     'HSE', 'FI', 'Materials',   'EUR')
ON CONFLICT (symbol) DO NOTHING;
```
