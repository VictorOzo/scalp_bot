# Scalp Bot (Phase 2)

## Scope
This repository is currently in **Phase 2**:
- Data pipeline hardening for OANDA candle ingestion
- Technical indicator modules
- Offline deterministic unit tests

Out of scope in this phase:
- Strategy logic
- Execution engine behavior
- Backtesting (beyond stubs)
- Live trading
- News integrations

## Requirements
- Python 3.11+
- See `requirements.txt` for runtime packages
- See `requirements-dev.txt` for developer tooling

## Running tests
Install development dependencies, then run:

```bash
pytest -q
```

The test suite is CI-friendly and designed to run fully offline (no live OANDA requests).

## Safety warning
This project is **not** ready for live trading. It currently provides pipeline and indicator primitives only.
