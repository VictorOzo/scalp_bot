from __future__ import annotations

import pandas as pd

from execution.command_executor import process_next_command
from storage.commands import enqueue_command
from storage.db import connect, init_db
from storage.strategy_params import StrategyParamsService, upsert_profile_params
from strategies.ema_vwap import generate_signal_from_df


def _signal_df() -> pd.DataFrame:
    rows = 40
    df = pd.DataFrame(
        {
            "close": [1.0] * rows,
            "vwap": [1.0] * rows,
            "atr": [0.01] * rows,
            "cross_up": [False] * (rows - 1) + [True],
            "cross_down": [False] * rows,
        }
    )
    df.loc[df.index[-1], "close"] = 0.9995
    return df


def test_reload_params_command_updates_strategy_thresholds(tmp_path) -> None:
    db_path = tmp_path / "reload_params.sqlite"
    conn = connect(db_path)
    init_db(conn)

    service = StrategyParamsService(db_path)
    before = service.get("ema_vwap").params
    assert generate_signal_from_df(_signal_df(), params=before) == "BUY"

    upsert_profile_params(
        conn,
        strategy_name="ema_vwap",
        profile="normal",
        params={"vwap_atr_tolerance": 0.01},
        updated_by="test",
    )

    command_id = enqueue_command(conn, actor="test", type="RELOAD_PARAMS")
    paused_pairs, result = process_next_command(
        conn,
        paused_pairs=set(),
        handled_by="unit-test",
        reload_params_fn=service.reload,
    )
    assert paused_pairs == set()
    assert result is not None and int(result["id"]) == command_id

    after = service.get("ema_vwap").params
    assert generate_signal_from_df(_signal_df(), params=after) == "HOLD"
    conn.close()
