"""File-writing helpers used by strategy scripts."""

from __future__ import annotations

from typing import Any

from .file_handlers import create_daily_file_names


def sync_strategy_daily_file_names(alpaca_sdk: Any, strategy_name: str, dir_name: str | None, timezone):
    """Create daily file names and mirror them onto SDK instance attributes.

    This preserves behavior expected by strategy scripts that call
    sync_strategy_daily_file_names(...) on startup and during date rollovers.
    """
    file_names = create_daily_file_names(strategy_name, dir_name, timezone)
    if alpaca_sdk is not None:
        for key, value in file_names.items():
            try:
                setattr(alpaca_sdk, key, value)
            except Exception:
                pass
    return file_names
