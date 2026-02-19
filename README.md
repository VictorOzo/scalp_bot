# Scalp Bot (Phase 7)

## Scope
This repository is currently in **Phase 7**:
- Phase 2 data pipeline hardening for OANDA candle ingestion
- Technical indicator modules (ATR, ADX, RSI, EMA, VWAP, MACD, Bollinger)
- Phase 3 trading gates (session, spread, news, market-state)
- Phase 4 strategy signal generation with mandatory 7-gate flow
- Phase 5 paper-first execution engine with SL/TP attached on entry
- Phase 6 risk management v2.0
- **Phase 7 offline backtesting v2.0**:
  - Spread + slippage cost simulation in pips
  - Dual execution modes: `sl_tp` and `time_exit`
  - Walk-forward train/validation split with overfit warning
  - Per-pair strategy mapping runner in `tests/tools/backtest_run.py`

## Phase 6 risk rules
- Max risk per trade: **1%** (`RISK_PER_TRADE=0.01`)
- Max daily loss: **3%** (`MAX_DAILY_LOSS=0.03`)
- Stop-loss distance: `ATR * 1.5`
- Take-profit distance: `SL distance * 2.0` (RR 1:2)
- Max open positions: `1 per pair` and `3 total`
- SL/TP is always attached with market entry orders

## Mandatory 7-gate strategy order
Every strategy evaluates in this exact order:
1. Session active (`filters/session_filter.py`)
2. Spread acceptable (`filters/spread_filter.py`)
3. News window clear (`filters/news_filter.py`)
4. Open position (`execution/order_manager.py`)
5. Daily loss limit (`execution/risk_manager.py`)
6. Enemy state allowed (`filters/market_state.py`)
7. Signal logic (`strategies/*.py`)

## Phase 7 backtesting

### Run the offline backtest tool
Single pair:
```bash
python -m tests.tools.backtest_run --pair EUR_USD --csv tests/fixtures/sample_ohlcv.csv --mode sl_tp
```

All configured pairs:
```bash
python -m tests.tools.backtest_run --csv tests/fixtures/sample_ohlcv.csv --mode time_exit
```

### Cost model
Backtests are fully offline (CSV-only) and apply execution costs before PnL:
- `spread` is modeled as round-turn pips and half-spread is applied at entry.
- `slippage` is uniformly sampled in `[0, max_slip]` pips.
- Effective entry price is adjusted by both spread and slippage.

### `sl_tp` vs `time_exit`
- `sl_tp` (default):
  - Entry at current close.
  - SL/TP computed from ATR via existing risk manager helper.
  - Future bars are scanned for SL/TP hit; otherwise trade times out.
- `time_exit`:
  - Entry at next bar open.
  - Exit at `hold_bars` bars later.
  - SL/TP is ignored.

### Walk-forward validation
- Data is split into train/validation using `train_pct` (default 70/30).
- Strategy is backtested independently on each split.
- Win-rate gap is computed as `abs(train_win_rate - validation_win_rate)`.
- Overfit warning is raised when gap exceeds `0.15` (15%).

### Backtest performance thresholds
| Metric | Minimum |
|---|---:|
| Win Rate | >50% |
| Profit Factor | >1.3 |
| Max Drawdown | <25% |
| Sharpe | >1.0 |
| Train/Val gap | <15% |

## Execution safety
- `DRY_RUN` defaults to `True`.
- In dry-run mode, the engine prints intended trades and does not place orders.
- To enable real order placement, explicitly set `DRY_RUN=False`.
- Use an OANDA practice account first.

## Environment notes
- Broker-aware sizing calls OANDA `AccountInstruments` for pip location and unit constraints.
- Live mode requires:
  - `OANDA_API_KEY`
  - `OANDA_ACCOUNT_ID`

## Requirements
- Python 3.11+
- See `requirements.txt` for runtime packages
- See `requirements-dev.txt` for developer tooling

## Run and test
```bash
pytest -q
python -m tests.tools.run_phase3_console
python -m tests.tools.signal_scan
python -m tests.tools.backtest_run --csv tests/fixtures/sample_ohlcv.csv
```

## Debug integration lines
```bash
set DEBUG_PHASE4=1
pytest -s -q tests/integration/test_phase4_pipeline_offline.py
```

## Safety warning
This project is still not production-ready for live trading.
