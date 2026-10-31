"""Order management system.

Single source of truth for all trade-order operations used by every master_* driver.

Covers:
  - Order submission (submit_order, resolve_order_preference, limit pricing)
  - Order cancellation (per-symbol, per-strategy, post-open cleanup)
    - Open-order ID tracking
  - Fill confirmation and balance accounting (apply_confirmed_fill_to_working_balance)
  - Execution logic (execute_symbol_delta, flip / partial fills, take-profit loops)
  - Position-queue updates (tracked via fill accounting)

All master_* drivers reach this module exclusively through MasterDriver's order
management methods in master_driver_core.py — no driver should import from
master_driver_execution, master_driver_orders, or the order sections of
driver_state_helpers directly.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Execution helpers
#   execute_symbol_delta, execute_bar_deltas, execute_per_share_take_profit_loop,
#   wait_for_market_order_resolution, wait_for_limit_cancellations
# ---------------------------------------------------------------------------
try:
    from MachineTrader.helpers.master_driver_execution import (
        execute_symbol_delta,
        execute_bar_deltas,
        print_trade_gate_summary,
        execute_per_share_take_profit_loop,
        wait_for_market_order_resolution,
        wait_for_limit_cancellations,
    )
except ImportError:
    from MachineTrader.helpers.master_driver_execution import (
        execute_symbol_delta,
        execute_bar_deltas,
        print_trade_gate_summary,
        execute_per_share_take_profit_loop,
        wait_for_market_order_resolution,
        wait_for_limit_cancellations,
    )

# ---------------------------------------------------------------------------
# Order cancellation helpers
#   track_strategy_open_orders, cancel_all_limit_orders, cancel_opposite_limit_orders,
#   cancel_strategy_limit_orders_after_market_open,
#   count / list / strategy_order_keys
# ---------------------------------------------------------------------------
try:
    from MachineTrader.helpers.master_driver_orders import (
        strategy_order_keys,
        track_strategy_open_orders,
        cancel_tracked_order,
        cancel_strategy_limit_orders_after_market_open,
        cancel_opposite_limit_orders,
        cancel_all_open_orders,
        cancel_all_limit_orders,
        count_open_limit_orders,
        list_open_limit_orders,
        list_open_limit_orders_by_strategy,
    )
except ImportError:
    from MachineTrader.helpers.master_driver_orders import (
        strategy_order_keys,
        track_strategy_open_orders,
        cancel_tracked_order,
        cancel_strategy_limit_orders_after_market_open,
        cancel_opposite_limit_orders,
        cancel_all_open_orders,
        cancel_all_limit_orders,
        count_open_limit_orders,
        list_open_limit_orders,
        list_open_limit_orders_by_strategy,
    )

# ---------------------------------------------------------------------------
# Submission, fill tracking, and pricing helpers
#   submit_order, wait_for_fill,
#   apply_confirmed_fill_to_working_balance,
#   resolve_order_preference, rebuild_limit_price_from_live_inputs,
#   enforce_limit_spacing, categorize_order_status,
#   is_market_open_now, print_market_order_closed_warning
# ---------------------------------------------------------------------------
try:
    from MachineTrader.helpers.driver_state_helpers import (
        submit_order,
        wait_for_fill,
        apply_confirmed_fill_to_working_balance,
        resolve_order_preference,
        rebuild_limit_price_from_live_inputs,
        enforce_limit_spacing,
        categorize_order_status,
        is_market_open_now,
        print_market_order_closed_warning,
    )
except ImportError:
    from MachineTrader.helpers.driver_state_helpers import (
        submit_order,
        wait_for_fill,
        apply_confirmed_fill_to_working_balance,
        resolve_order_preference,
        rebuild_limit_price_from_live_inputs,
        enforce_limit_spacing,
        categorize_order_status,
        is_market_open_now,
        print_market_order_closed_warning,
    )


__all__ = [
    # Execution
    "execute_symbol_delta",
    "execute_bar_deltas",
    "print_trade_gate_summary",
    "execute_per_share_take_profit_loop",
    "wait_for_market_order_resolution",
    "wait_for_limit_cancellations",
    # Cancellation
    "strategy_order_keys",
    "track_strategy_open_orders",
    "cancel_tracked_order",
    "cancel_strategy_limit_orders_after_market_open",
    "cancel_opposite_limit_orders",
    "cancel_all_open_orders",
    "cancel_all_limit_orders",
    "count_open_limit_orders",
    "list_open_limit_orders",
    "list_open_limit_orders_by_strategy",
    # Submission and fill tracking
    "submit_order",
    "wait_for_fill",
    "apply_confirmed_fill_to_working_balance",
    # Pricing
    "resolve_order_preference",
    "rebuild_limit_price_from_live_inputs",
    "enforce_limit_spacing",
    # Status utilities
    "categorize_order_status",
    "is_market_open_now",
    "print_market_order_closed_warning",
]
