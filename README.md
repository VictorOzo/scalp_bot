# Scalp Bot (Phase 5)

## Scope
This repository is currently in **Phase 5**:
- Phase 2 data pipeline hardening for OANDA candle ingestion
- Technical indicator modules (ATR, ADX, RSI, EMA, VWAP, MACD, Bollinger)
- Phase 3 trading gates (session, spread, news, market-state)
- Phase 4 strategy signal generation with mandatory 7-gate flow
- Phase 5 paper-first execution engine:
  - Position reconciliation before execution
  - Market orders with SL/TP attached in the same request
  - DRY_RUN safety switch enabled by default

## Mandatory 7-gate strategy order
Every strategy evaluates in this exact order:
1. Session active (`filters/session_filter.py`)
2. Spread acceptable (`filters/spread_filter.py`)
3. News window clear (`filters/news_filter.py`)
4. Open position (`execution/order_manager.py`)
5. Daily loss limit (`execution/risk_manager.py`)
6. Enemy state allowed (`filters/market_state.py`)
7. Signal logic (`strategies/*.py`)

## Execution safety
- `DRY_RUN` defaults to `True`.
- In dry-run mode, the engine prints intended trades and does not place orders.
- To enable real order placement, explicitly set `DRY_RUN=False`.
- Use an OANDA practice account first.

## Requirements
- Python 3.11+
- See `requirements.txt` for runtime packages
- See `requirements-dev.txt` for developer tooling

## Run and test
```bash
pytest -q
python -m tests.tools.run_phase3_console
python -m tests.tools.signal_scan
```

## Debug integration lines
```bash
set DEBUG_PHASE4=1
pytest -s -q tests/integration/test_phase4_pipeline_offline.py
```

## Safety warning
This project is still not production-ready for live trading.
