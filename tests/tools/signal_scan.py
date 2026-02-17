"""Simple signal scanner for configured pairs."""

from __future__ import annotations

from config.pairs import PAIR_STRATEGY_MAP
from config.settings import OANDA_ACCOUNT_ID, OANDA_API_KEY
from data.fetcher import get_oanda_client
from strategies import bb_breakout, ema_vwap, vwap_rsi

STRATEGY_FN = {
    "ema_vwap": ema_vwap.get_signal,
    "bb_breakout": bb_breakout.get_signal,
    "vwap_rsi": vwap_rsi.get_signal,
}


def run_scan() -> None:
    if not (OANDA_API_KEY and OANDA_ACCOUNT_ID):
        print("signal_scan: missing OANDA credentials; skipping live scan")
        return

    client = get_oanda_client()
    for pair, strategy_name in PAIR_STRATEGY_MAP.items():
        signal = STRATEGY_FN[strategy_name](client, OANDA_ACCOUNT_ID)
        print(f"{pair} {strategy_name} -> {signal}")


if __name__ == "__main__":
    run_scan()
