"""Helpers for applying control-plane pause/resume commands."""

from __future__ import annotations

from typing import Any

from config.pairs import PAIR_STRATEGY_MAP


PAUSE_COMMANDS = {"PAUSE_PAIR", "RESUME_PAIR", "PAUSE_ALL", "RESUME_ALL"}


def apply_pause_command(paused_pairs: set[str], cmd: dict[str, Any]) -> set[str]:
    """Apply pause/resume command and return updated paused pair set."""
    command_type = cmd.get("type")
    payload = cmd.get("payload") or {}

    updated = set(paused_pairs)
    if command_type == "PAUSE_PAIR":
        pair = payload.get("pair")
        if pair:
            updated.add(pair)
        return updated

    if command_type == "RESUME_PAIR":
        pair = payload.get("pair")
        if pair:
            updated.discard(pair)
        return updated

    if command_type == "PAUSE_ALL":
        return set(PAIR_STRATEGY_MAP.keys())

    if command_type == "RESUME_ALL":
        return set()

    return updated
