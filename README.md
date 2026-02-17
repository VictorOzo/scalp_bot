# Scalp Bot (Phase 4)

## Scope
This repository is currently in **Phase 4**:
- Phase 2 data pipeline hardening for OANDA candle ingestion
- Technical indicator modules (ATR, ADX, RSI, EMA, VWAP, MACD, Bollinger)
- Phase 3 trading gates:
  - Session gate
  - Spread gate (offline + optional live pricing wrapper)
  - News gate (offline-first, optional fetch wrapper)
  - Enemy detector / market-state classifier
- Phase 4 strategy signal generation with mandatory 7-gate flow

## Mandatory 7-gate strategy order
Every strategy must evaluate in this exact order:
1. Session active (`filters/session_filter.py`)
2. Spread acceptable (`filters/spread_filter.py`)
3. News window clear (`filters/news_filter.py`)
4. Open position (`execution/order_manager.py`)
5. Daily loss limit (`execution/risk_manager.py`)
6. Enemy state allowed (`filters/market_state.py`)
7. Signal logic (`strategies/*.py`)

## Requirements
- Python 3.11+
- See `requirements.txt` for runtime packages
- See `requirements-dev.txt` for developer tooling

## Running tests
```bash
pytest -q
```

## Debug console lines in integration test
```bash
set DEBUG_PHASE4=1
pytest -s -q tests/integration/test_phase4_pipeline_offline.py
```

## Console runner
```bash
python -m tests.tools.run_phase3_console
```

## Safety warning
This project is **not** ready for live trading. It currently provides data/indicators, gate logic, and strategy signal scaffolding only.
