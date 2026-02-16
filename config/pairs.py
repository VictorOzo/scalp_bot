"""Currency pair to strategy mapping."""

PAIR_STRATEGY_MAP: dict[str, str] = {
    "EUR_USD": "ema_vwap",
    "GBP_USD": "bb_breakout",
    "USD_JPY": "vwap_rsi",
}
