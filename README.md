# Scalp Bot (Phase 8)

## Scope
This repository is currently in **Phase 8**:
- Phase 2 data pipeline hardening for OANDA candle ingestion
- Technical indicator modules (ATR, ADX, RSI, EMA, VWAP, MACD, Bollinger)
- Phase 3 trading gates (session, spread, news, market-state)
- Phase 4 strategy signal generation with mandatory 7-gate flow
- Phase 5 paper-first execution engine with SL/TP attached on entry
- Phase 6 risk management v2.0
- Phase 7 offline backtesting v2.0
- **Phase 8 paper trading & validation**:
  - SQLite-first persistence (`data/paper_trading.db`)
  - Instant paper fills at bid/ask with SL/TP reconciliation
  - Daily loss halt (3% drawdown) + kill switch support
  - Optional CSV export for manual review (`data/signals_log.csv`, `data/trades_log.csv`)

## Phase 8 paper mode

### LIVE paper mode (never sends real orders)
```bash
python -m tests.tools.paper_run --mode LIVE --pairs EUR_USD,GBP_USD
```

### OFFLINE paper mode (fixture CSV)
```bash
python -m tests.tools.paper_run --mode OFFLINE --csv tests/fixtures/sample_ohlcv.csv
```

### Enable optional CSV export
```bash
python -m tests.tools.paper_run --mode OFFLINE --csv tests/fixtures/sample_ohlcv.csv --export-csv
```

## Storage and exports
- SQLite DB path defaults to: `data/paper_trading.db`
- Override DB path with env var: `SCALP_BOT_DB_PATH`
- Optional CSV append logs:
  - `data/signals_log.csv`
  - `data/trades_log.csv`

## Mandatory 7-gate strategy order
Every strategy evaluates in this exact order:
1. Session active (`filters/session_filter.py`)
2. Spread acceptable (`filters/spread_filter.py`)
3. News window clear (`filters/news_filter.py`)
4. Open position (`execution/order_manager.py` / paper reconciliation)
5. Daily loss limit (`execution/risk_manager.py` / paper daily stats)
6. Enemy state allowed (`filters/market_state.py`)
7. Signal logic (`strategies/*.py`)

## Paper trading checklist
- [ ] Run offline fixture mode and verify signals/trades persist to SQLite
- [ ] Run with `--export-csv` and verify CSV append files are created
- [ ] Confirm restart safety (re-run without duplicate open entries)
- [ ] Confirm daily loss halt at drawdown >= 3%
- [ ] Use LIVE paper mode only with OANDA practice credentials

## Requirements
- Python 3.11+
- See `requirements.txt` for runtime packages
- See `requirements-dev.txt` for developer tooling

## Run and test
```bash
pytest -q
python -m tests.tools.paper_run --mode OFFLINE --csv tests/fixtures/sample_ohlcv.csv --export-csv
python -m tests.tools.backtest_run --csv tests/fixtures/sample_ohlcv.csv
```

## Safety warning
This project is still not production-ready for live trading.
