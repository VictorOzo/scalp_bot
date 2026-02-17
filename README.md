# Scalp Bot (Phase 3)

## Scope
This repository is currently in **Phase 3**:
- Phase 2 data pipeline hardening for OANDA candle ingestion
- Technical indicator modules (ATR, ADX, RSI, EMA, VWAP, MACD, Bollinger)
- Phase 3 trading gates:
  - Session gate
  - Spread gate (offline + optional live pricing wrapper)
  - News gate (offline-first, optional fetch wrapper)
  - Enemy detector / market-state classifier

Out of scope in this phase:
- Full strategy signal generation and execution wiring
- Position management behavior
- Live trading

## Requirements
- Python 3.11+
- See `requirements.txt` for runtime packages
- See `requirements-dev.txt` for developer tooling

## Running tests
Install development dependencies, then run:

```bash
pytest -q
pytest -q tests/unit
pytest -q tests/integration
```

The test suite is CI-friendly and designed to run fully offline (no live OANDA requests).

## Gate order (for future phases)
1. Session
2. Spread
3. News
4. Enemy detector (`market_state`)
5. Strategy signal (future)
6. Execution (future)

## Safety warning
This project is **not** ready for live trading. It currently provides data, indicators, and risk gates only.
