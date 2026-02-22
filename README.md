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

## Dashboard Phase D1 (SQLite single source of truth)
- Dashboard telemetry now uses SQLite as a shared control-plane store.
- `SCALP_BOT_DB_PATH` controls which SQLite file is used for dashboard state.
- Default dashboard DB path: `storage/scalp_bot.sqlite` (relative to repo root).
- Phase D1 is offline-friendly: tests and snapshot writes run without OANDA/network access.
- FastAPI and Next.js integration come in later dashboard phases.

### Inspect latest gate snapshots
```bash
python - <<'PY'
from storage.db import connect, init_db

with connect() as conn:
    init_db(conn)
    rows = conn.execute(
        "SELECT ts_utc, pair, strategy, final_signal, reason FROM gate_snapshots ORDER BY id DESC LIMIT 10"
    ).fetchall()

for row in rows:
    print(row)
PY
```

## Dashboard Phase D3 (DB-driven command executor)
- `commands` now use deterministic statuses: `PENDING`, `RUNNING`, `SUCCEEDED`, `FAILED`, `SKIPPED`.
- Bot loop polls queued commands, claims atomically, executes handlers, and writes structured `result_json`.
- `CLOSE_PAIR` and `CLOSE_ALL` are now executable in addition to pause/resume commands.
- `audit_log` captures claim/start/per-action/completion lifecycle events.
- Command types currently accepted by schema/API:
  - `PAUSE_PAIR`, `RESUME_PAIR`, `PAUSE_ALL`, `RESUME_ALL`
  - `CLOSE_PAIR`, `CLOSE_ALL`, `RELOAD_PARAMS`
- Live close commands are guarded by `LIVE_TRADING_ENABLED=true`; otherwise they are safely marked `SKIPPED`.

### Enqueue a pause command
```bash
python - <<'PY'
from storage.db import connect, init_db
from storage.commands import enqueue_command

with connect() as conn:
    init_db(conn)
    command_id = enqueue_command(
        conn,
        actor="local",
        type="PAUSE_PAIR",
        payload={"pair": "EUR_USD"},
        idempotency_key="pause-eurusd-001",
    )
    print("queued", command_id)
PY
```

### Enqueue a paper close command manually (SQL)
```bash
python - <<'PY'
from storage.db import connect, init_db

with connect() as conn:
    init_db(conn)
    conn.execute(
        """
        INSERT INTO commands (created_ts_utc, actor, type, payload_json, status)
        VALUES (datetime('now'), 'local', 'CLOSE_PAIR', '{"pair":"EUR_USD","mode":"PAPER"}', 'PENDING')
        """
    )
    conn.commit()
PY
```

### Inspect pending commands and audit rows
```bash
python - <<'PY'
from storage.db import connect, init_db

with connect() as conn:
    init_db(conn)
    commands = conn.execute(
        "SELECT id, status, type, actor, created_ts_utc FROM commands WHERE status='PENDING' ORDER BY created_ts_utc ASC"
    ).fetchall()
    audit = conn.execute(
        "SELECT ts_utc, actor, action, command_id FROM audit_log ORDER BY id DESC LIMIT 20"
    ).fetchall()

print("pending commands")
for row in commands:
    print(row)

print("recent audit")
for row in audit:
    print(row)
PY
```

## Dashboard Phase D4 (FastAPI backend)

### Run API server
```bash
uvicorn api.app:app --reload
# or
python -m api
```

### Create admin/viewer users
```bash
python - <<'PY'
from api.auth import ensure_user
from storage.db import connect, init_db

with connect() as conn:
    init_db(conn)
    ensure_user(conn, username="admin", password="change-me", role="admin")
    ensure_user(conn, username="viewer", password="change-me", role="viewer")
PY
```

### Login and enqueue command (cookie auth)
```bash
curl -i -X POST http://127.0.0.1:8000/auth/login \
  -H 'content-type: application/json' \
  -d '{"username":"admin","password":"change-me"}' \
  -c cookies.txt

curl -X POST http://127.0.0.1:8000/commands \
  -H 'content-type: application/json' \
  -d '{"type":"PAUSE_PAIR","payload":{"pair":"EUR_USD"}}' \
  -b cookies.txt
```
