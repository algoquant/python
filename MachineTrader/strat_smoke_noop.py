"""Smoke-test no-op strategy.

This strategy intentionally never emits trade deltas. It is useful for testing
driver startup, proxy wiring, heartbeat output, and state logging without
submitting any orders.

Examples
--------
Run with master_driver:

    python3 -m MachineTrader.master_driver SPY \
        --strategy MachineTrader.strat_smoke_noop:call_back

Run with master_pairs:

    python3 -m MachineTrader.master_pairs \
        --strategy MachineTrader.strat_smoke_noop:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_proxy

Backtest one trading day:

    python3 -m MachineTrader.master_backtest \\
        --strategy MachineTrader.strat_smoke_noop:call_back \\
        --env-file /Users/jerzy/Develop/trading/config/.env_proxy \\
        --date 2026-09-04
"""

from __future__ import annotations


def call_back(context):
    # Smoke-test strategy: never submits trades.
    return None
