"""Emergency kill switch for paper trading."""

from __future__ import annotations

from execution.paper_broker import PaperBroker


def close_all_positions(broker: PaperBroker, reason: str = "KILL_SWITCH") -> list[dict]:
    """Close all open paper positions immediately."""
    return broker.close_all_positions(reason=reason)
