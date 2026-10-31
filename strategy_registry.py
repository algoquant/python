"""Top-level strategy bundle shim.

setup_strat loads `strategy_registry` via importlib, so this file forwards to
MachineTrader.helpers.strategy_registry.
"""

from MachineTrader.helpers.strategy_registry import *  # noqa: F401,F403
