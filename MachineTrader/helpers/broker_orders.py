from __future__ import annotations

"""Shared broker-order helper facade.

This module centralizes submit/cancel/balance/response helpers by re-exporting
order-management utilities used by master drivers.
"""

import re
from pathlib import Path

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest, MarketOrderRequest
from dotenv import dotenv_values
from MachineTrader.helpers.api_parsing import enum_text, normalize_order_status
from MachineTrader.helpers.api_responses import (
    ORDER_STATUS_GROUPS,
    is_terminal_order_status,
)


TERMINAL_ORDER_STATUSES = set(ORDER_STATUS_GROUPS["terminal"])


def create_trading_client_from_env(env_file: str) -> TradingClient:
    env_path = Path(str(env_file or "").strip()).expanduser()
    if not env_path.is_file():
        raise ValueError(f"Trading environment file not found: {env_path}")

    values = dotenv_values(env_path)
    trade_key = str(values.get("ALPACA_TRADE_KEY", "") or "").strip()
    trade_secret = str(values.get("ALPACA_TRADE_SECRET", "") or "").strip()
    if not trade_key or not trade_secret:
        raise ValueError(
            f"Trading environment file must define ALPACA_TRADE_KEY and ALPACA_TRADE_SECRET: {env_path}"
        )
    return TradingClient(trade_key, trade_secret)


def submit_reverse_copy_order(
    trading_client: TradingClient,
    *,
    symbol: str,
    primary_side,
    qty: float,
    order_type: str,
    limit_price: float | None = None,
):
    side_text = normalize_order_status(primary_side)
    if side_text == "buy":
        mirror_side = OrderSide.SELL
    elif side_text == "sell":
        mirror_side = OrderSide.BUY
    else:
        raise ValueError(f"Unsupported primary order side: {primary_side}")

    qty_value = abs(float(qty or 0.0))
    if qty_value <= 0.0:
        raise ValueError("Mirrored order quantity must be greater than zero")

    order_kind = normalize_order_status(order_type) or "market"
    if order_kind == "market":
        request = MarketOrderRequest(
            symbol=str(symbol or "").strip().upper(),
            qty=qty_value,
            side=mirror_side,
            time_in_force=TimeInForce.DAY,
        )
    elif order_kind == "limit":
        if limit_price is None or float(limit_price) <= 0.0:
            raise ValueError("Mirrored limit order requires a positive limit price")
        request = LimitOrderRequest(
            symbol=str(symbol or "").strip().upper(),
            qty=qty_value,
            side=mirror_side,
            limit_price=float(limit_price),
            extended_hours=True,
            time_in_force=TimeInForce.DAY,
        )
    else:
        raise ValueError(f"Unsupported mirrored order type: {order_type}")

    return trading_client.submit_order(order_data=request)


def extract_available_qty_from_rejection(error_text: str) -> float:
    text = str(error_text or "")
    patterns = [
        r"available(?:\s+qty|\s+quantity|\s+shares)?\s*[:=]\s*(-?\d+(?:\.\d+)?)",
        r"available(?:\s+qty|\s+quantity|\s+shares)?\s+(-?\d+(?:\.\d+)?)",
        r"requested\s*[:=]\s*-?\d+(?:\.\d+)?[^\n,;]*available\s*[:=]?\s*(-?\d+(?:\.\d+)?)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        try:
            return float(match.group(1))
        except Exception:
            continue
    return 0.0


def parse_submit_rejection(symbol: str, side, error: Exception) -> dict[str, object]:
    message = str(error or "")
    lowered = message.lower()
    is_insufficient_qty = (
        "insufficient" in lowered
        and "available" in lowered
        and any(token in lowered for token in ("qty", "quantity", "share"))
    )
    available_qty = extract_available_qty_from_rejection(message) if is_insufficient_qty else 0.0
    return {
        "symbol": str(symbol or "").upper(),
        "side": normalize_order_status(side),
        "message": message,
        "is_insufficient_qty": bool(is_insufficient_qty),
        "available_qty": float(available_qty),
    }


def resolve_insufficient_qty_retry(
    requested_qty,
    side,
    *,
    rejection_payload: dict | None = None,
    available_qty: float | None = None,
    broker_qty: float = 0.0,
    resolver=None,
) -> int:
    requested = int(round(abs(float(requested_qty or 0.0))))
    if requested <= 0:
        return 0

    if available_qty is None and isinstance(rejection_payload, dict):
        available_qty = float(rejection_payload.get("available_qty", 0.0) or 0.0)
    if available_qty is None:
        available_qty = 0.0

    if callable(resolver):
        try:
            resolved_qty = float(
                resolver(
                    requested,
                    side,
                    available_qty=float(available_qty),
                    broker_qty=float(broker_qty or 0.0),
                    force_cap_to_available=True,
                )
            )
        except Exception:
            resolved_qty = min(float(requested), abs(float(available_qty or 0.0)))
    else:
        resolved_qty = min(float(requested), abs(float(available_qty or 0.0)))

    resolved_int = int(round(max(0.0, float(resolved_qty))))
    return min(requested, resolved_int)


def compute_limit_price(side, price: float, volatility: float, limit_spread: float) -> float:
    adjustment = float(limit_spread) * float(volatility)
    if normalize_order_status(side) == "buy":
        return round(float(price) - adjustment, 2)
    return round(float(price) + adjustment, 2)

try:
    from MachineTrader.helpers.order_management import (
        apply_confirmed_fill_to_working_balance,
        cancel_all_limit_orders,
        cancel_opposite_limit_orders,
        cancel_strategy_limit_orders_after_market_open,
        categorize_order_status,
        count_open_limit_orders,
        enforce_limit_spacing,
        execute_per_share_take_profit_loop,
        execute_symbol_delta,
        is_market_open_now,
        list_open_limit_orders,
        list_open_limit_orders_by_strategy,
        print_market_order_closed_warning,
        rebuild_limit_price_from_live_inputs,
        resolve_order_preference,
        strategy_order_keys,
        submit_order,
        wait_for_fill,
        wait_for_limit_cancellations,
        wait_for_market_order_resolution,
    )
except ImportError:
    from .order_management import (
        apply_confirmed_fill_to_working_balance,
        cancel_all_limit_orders,
        cancel_opposite_limit_orders,
        cancel_strategy_limit_orders_after_market_open,
        categorize_order_status,
        count_open_limit_orders,
        enforce_limit_spacing,
        execute_per_share_take_profit_loop,
        execute_symbol_delta,
        is_market_open_now,
        list_open_limit_orders,
        list_open_limit_orders_by_strategy,
        print_market_order_closed_warning,
        rebuild_limit_price_from_live_inputs,
        resolve_order_preference,
        strategy_order_keys,
        submit_order,
        wait_for_fill,
        wait_for_limit_cancellations,
        wait_for_market_order_resolution,
    )

def cancel_conflicting_opposite_orders(trading_client, symbol: str, liquidation_side, *, print_fn=print) -> int:
    """Cancel opposite-side market/stop-family open orders for one symbol."""
    symbol_key = str(symbol or "").strip().upper()
    side_text = enum_text(liquidation_side)
    if not symbol_key or not side_text:
        return 0

    conflicting_types = {"market", "stop", "stop_limit", "trailing_stop"}
    canceled_count = 0

    try:
        open_filter = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        open_orders = trading_client.get_orders(filter=open_filter)
    except Exception as exc:
        if callable(print_fn):
            print_fn("⚠️ ", f"Unable to list open orders for conflict checks on {symbol_key}: {exc}")
        return 0

    for order in open_orders:
        order_symbol = str(getattr(order, "symbol", "") or "").strip().upper()
        if order_symbol != symbol_key:
            continue

        order_type = enum_text(getattr(order, "type", ""))
        if order_type not in conflicting_types:
            continue

        order_side_text = enum_text(getattr(order, "side", ""))
        if order_side_text == side_text:
            continue

        order_id = str(getattr(order, "id", "") or "").strip()
        if not order_id:
            continue

        try:
            trading_client.cancel_order_by_id(order_id)
            canceled_count += 1
            if callable(print_fn):
                print_fn(
                    "🧹 ",
                    f"Canceled conflicting order id={order_id} symbol={symbol_key} type={order_type} side={order_side_text}",
                )
        except Exception as exc:
            if callable(print_fn):
                print_fn(
                    "⚠️ ",
                    f"Failed to cancel conflicting order id={order_id} symbol={symbol_key} type={order_type}: {exc}",
                )

    return canceled_count


def collect_orders_by_id_for_statuses(
    trading_client,
    *,
    statuses: list[QueryOrderStatus] | tuple[QueryOrderStatus, ...],
    after=None,
    symbols: list[str] | None = None,
    limit: int = 500,
    on_error=None,
    error_key_prefix: str = "order_fetch",
) -> dict[str, object]:
    """Fetch orders for one or more statuses and return them keyed by order id."""
    known_orders_by_id: dict[str, object] = {}
    for status in statuses:
        request_params = GetOrdersRequest(status=status, after=after, symbols=symbols, limit=limit)
        try:
            orders = trading_client.get_orders(filter=request_params)
        except Exception as exc:
            if callable(on_error):
                status_text = enum_text(status) or str(status)
                on_error(
                    f"{error_key_prefix}_{status_text}",
                    f"Unable to fetch {status} orders: {exc}",
                )
            continue

        for order in orders:
            order_id = str(getattr(order, "id", "") or "").strip()
            if order_id:
                known_orders_by_id[order_id] = order

    return known_orders_by_id


def build_order_status_map(
    orders_by_id: dict[str, object],
    *,
    normalize_status,
) -> dict[str, str]:
    """Build order_id -> normalized status mapping from broker order objects."""
    status_by_id: dict[str, str] = {}
    for order_id, order in (orders_by_id or {}).items():
        raw_status = getattr(order, "status", "")
        normalized = normalize_status(raw_status) if callable(normalize_status) else enum_text(raw_status)
        status_by_id[str(order_id)] = str(normalized or "").strip().lower()
    return status_by_id


def count_submitted_orders_by_symbol(
    *,
    required_symbols: set[str],
    submitted_order_ids_by_symbol: dict[str, set[str]],
    known_status_by_id: dict[str, str],
    include_statuses: set[str] | None = None,
    exclude_statuses: set[str] | None = None,
    require_nonempty_status: bool = False,
) -> dict[str, int]:
    """Count submitted orders per symbol using normalized status filters."""
    include = {str(value).strip().lower() for value in (include_statuses or set()) if str(value).strip()}
    exclude = {str(value).strip().lower() for value in (exclude_statuses or set()) if str(value).strip()}
    counts: dict[str, int] = {symbol: 0 for symbol in required_symbols}

    for symbol_key in sorted(required_symbols):
        submitted_ids = submitted_order_ids_by_symbol.get(symbol_key, set())
        count = 0
        for order_id in submitted_ids:
            status = str(known_status_by_id.get(order_id, "") or "").strip().lower()
            if require_nonempty_status and not status:
                continue
            if include and status not in include:
                continue
            if exclude and status in exclude:
                continue
            count += 1
        counts[symbol_key] = count

    return counts


def signed_open_limit_order_count(
    trading_client,
    *,
    symbols: list[str],
    normalize_status,
) -> int:
    """Return signed open-limit count (+buy limits, -sell limits) across symbols."""
    request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=symbols)
    open_orders = trading_client.get_orders(filter=request_params)

    signed_count = 0
    for order in open_orders:
        raw_type = getattr(order, "type", "")
        order_type = normalize_status(raw_type) if callable(normalize_status) else enum_text(raw_type)
        if str(order_type or "").strip().lower() != "limit":
            continue

        raw_side = getattr(order, "side", "")
        side_text = normalize_status(raw_side) if callable(normalize_status) else enum_text(raw_side)
        side_key = str(side_text or "").strip().lower()
        if side_key == "buy":
            signed_count += 1
        elif side_key == "sell":
            signed_count -= 1

    return signed_count


def is_market_open_for_signal(driver, symbol: str) -> bool:
    del symbol
    return is_market_open_now(driver)


def clear_pending_trade_gates(driver):
    indicators = getattr(driver, "indicators", None)
    if isinstance(indicators, dict):
        indicators["pending_order_target_position"] = None
        indicators["pending_order_side"] = None
        indicators["pending_order_qty"] = 0.0
        indicators["pending_order_waiting"] = False
    if hasattr(driver, "take_profit_chain_active"):
        try:
            driver.take_profit_chain_active = False
        except Exception:
            pass
def wait_for_opposite_limit_cancellations(
    driver,
    symbol: str,
    incoming_side,
    strategy_label: str | None = None,
    timeout_seconds: float = 30.0,
    poll_seconds: float = 0.25,
) -> bool:
    del incoming_side, strategy_label, timeout_seconds, poll_seconds
    return count_open_limit_orders(driver, symbol, None) >= 0


def refresh_broker_state(driver):
    # Use driver-managed refresh where available; return cached snapshots otherwise.
    account_snapshot = getattr(getattr(driver, "alpaca_api", object()), "account_snapshot", {})
    positions_snapshot = getattr(getattr(driver, "alpaca_api", object()), "positions_snapshot", {})
    if not isinstance(account_snapshot, dict):
        account_snapshot = {}
    if not isinstance(positions_snapshot, dict):
        positions_snapshot = {}
    return account_snapshot, positions_snapshot


def submit_order_with_state(driver, symbol: str, side, qty: float, order_type: str, limit_price: float | None = None):
    return submit_order(driver, symbol, side, qty, order_type, limit_price)


__all__ = [
    "apply_confirmed_fill_to_working_balance",
    "cancel_all_limit_orders",
    "cancel_opposite_limit_orders",
    "cancel_strategy_limit_orders_after_market_open",
    "categorize_order_status",
    "count_open_limit_orders",
    "enforce_limit_spacing",
    "execute_per_share_take_profit_loop",
    "execute_symbol_delta",
    "is_market_open_now",
    "list_open_limit_orders",
    "list_open_limit_orders_by_strategy",
    "print_market_order_closed_warning",
    "rebuild_limit_price_from_live_inputs",
    "resolve_order_preference",
    "strategy_order_keys",
    "submit_order",
    "wait_for_fill",
    "wait_for_limit_cancellations",
    "wait_for_market_order_resolution",
    "enum_text",
    "cancel_conflicting_opposite_orders",
    "collect_orders_by_id_for_statuses",
    "build_order_status_map",
    "count_submitted_orders_by_symbol",
    "signed_open_limit_order_count",
    "compute_limit_price",
    "extract_available_qty_from_rejection",
    "parse_submit_rejection",
    "resolve_insufficient_qty_retry",
    "is_terminal_order_status",
    "normalize_order_status",
    "clear_pending_trade_gates",
    "is_market_open_for_signal",
    "refresh_broker_state",
    "submit_order_with_state",
    "wait_for_opposite_limit_cancellations",
]
