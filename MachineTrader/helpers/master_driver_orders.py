from __future__ import annotations

from datetime import datetime

from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest

try:
    from MachineTrader.helpers.driver_common import NY_TZ
except ImportError:
    from MachineTrader.helpers.driver_common import NY_TZ


def _is_terminal_order_status(raw_status) -> bool:
    try:
        import MachineTrader.helpers.broker_orders as _broker_orders
    except ImportError:
        from . import broker_orders as _broker_orders
    return bool(_broker_orders.is_terminal_order_status(raw_status))


def _print_order_gate_error(driver, key: str, message: str):
    throttled_printer = getattr(driver, "_print_error_with_stale_proxy_throttle", None)
    if callable(throttled_printer):
        throttled_printer(key, message)
    else:
        print("❌ ", message)


def strategy_order_keys(driver) -> set[str]:
    """Return sanitized strategy keys expected in client_order_id prefixes."""
    keys: set[str] = set()

    for fn in driver.strategy_functions:
        module_name = str(getattr(fn, "__module__", "") or "").strip()
        if not module_name:
            continue
        module_leaf = module_name.split(".")[-1]
        if module_leaf:
            keys.add(driver._sanitize_strategy_label(module_leaf))

    configured_strategy_name = str(driver.trading_state.strategy_name or driver.strategy_params.get("strategy_name", "") or "").strip()
    if configured_strategy_name:
        keys.add(driver._sanitize_strategy_label(configured_strategy_name))

    return {key for key in keys if key}


def track_strategy_open_orders(driver) -> int:
    """Add broker-open, strategy-owned orders to the authoritative ID map."""
    if driver.trading_client is None:
        return 0

    strategy_keys = strategy_order_keys(driver)
    request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=driver.symbols)
    try:
        open_orders = driver.trading_client.get_orders(filter=request_params)
    except Exception as exc:
        _print_order_gate_error(
            driver,
            "order_gate_unable_reconcile_open_orders",
            f"Order gate: unable to reconcile broker open orders: {exc}",
        )
        return 0

    tracked_count = 0
    for open_order in open_orders:
        symbol_key = driver._normalize_symbol(getattr(open_order, "symbol", ""))
        if symbol_key not in driver.required_symbols:
            continue

        order_strategy = driver._strategy_from_client_order_id(getattr(open_order, "client_order_id", ""))
        if strategy_keys and order_strategy not in strategy_keys:
            continue

        order_id = str(getattr(open_order, "id", "") or "").strip()
        if not order_id or order_id in driver._tracked_open_order_ids:
            continue

        status_text = driver._normalize_order_status(getattr(open_order, "status", ""))
        if _is_terminal_order_status(status_text):
            continue

        driver._track_submitted_order_id(
            order_id=order_id,
            symbol=symbol_key,
            side=driver._normalize_order_status(getattr(open_order, "side", "")),
            order_type=driver._normalize_order_status(getattr(open_order, "type", "")),
            qty=float(getattr(open_order, "qty", 0.0) or 0.0),
        )
        driver._session_submitted_order_ids.add(order_id)
        tracked_count += 1

    return tracked_count


def cancel_tracked_order(driver, order_id: str) -> bool:
    """Request cancellation; permit replacement only after tracking is released."""
    order_key = str(order_id or "").strip()
    metadata = driver._tracked_open_order_ids.get(order_key)
    if not order_key or not isinstance(metadata, dict) or driver.trading_client is None:
        return False

    if metadata.get("cancel_requested"):
        return False

    try:
        driver.trading_client.cancel_order_by_id(order_id=order_key)
    except Exception as exc:
        error_text = str(exc).lower().replace("_", " ")
        if 'order is already in "expired" state' in error_text.replace('\\"', '"'):
            driver._drop_tracked_order_id(order_key)
            print(
                f"Order expired order_id={order_key}; removed from pending orders."
            )
            return order_key not in driver._tracked_open_order_ids
        if "pending cancel" in error_text:
            metadata["cancel_requested"] = True
            print(
                f"Cancellation pending order_id={order_key}; waiting for terminal stream confirmation."
            )
            return False
        if driver._cancel_error_indicates_filled_state(exc):
            metadata["cancel_requested"] = True
            print(
                f"Warning: cancellation reached already-filled order_id={order_key}; "
                "waiting for stream fill confirmation."
            )
            return False
        driver._print_error_with_stale_proxy_throttle(
            f"changed_delta_cancel_failed_{order_key}",
            f"Failed to cancel changed-delta order id={order_key}: {exc}",
        )
        return False

    metadata["cancel_requested"] = True
    print(
        "🧹 ",
        f"Cancellation requested order id={order_key} symbol={metadata.get('symbol', 'unknown')} "
        f"side={metadata.get('side', 'unknown')} qty={metadata.get('qty', 0)}; "
        "waiting for terminal stream confirmation.",
    )
    return order_key not in driver._tracked_open_order_ids


def cancel_strategy_limit_orders_after_market_open(driver, force_cleanup: bool = False):
    """Cancel strategy-owned open limit orders.

    Default behavior runs once per open trading day. When ``force_cleanup`` is
    True, cancellation is attempted immediately. Automatic cleanup is disabled
    when ``use_limit`` is enabled so limit strategies can keep orders open.
    """
    strategy_params = getattr(driver, "strategy_params", {})
    if not force_cleanup and isinstance(strategy_params, dict) and bool(strategy_params.get("use_limit", False)):
        return 0

    strategy_keys = strategy_order_keys(driver)
    is_ladder = "strat_ladder" in strategy_keys
    if is_ladder:
        minute_key = getattr(driver, "current_minute_key", None)
        if minute_key is None:
            now_ny = datetime.now(NY_TZ)
            minute_key = (now_ny.year, now_ny.month, now_ny.day, now_ny.hour, now_ny.minute)
        session_status, _, _ = driver._minute_session_status(minute_key)
        if session_status in {"before_start", "after_end"}:
            return

    if driver.trading_client is None:
        return

    try:
        clock = driver.trading_client.get_clock()
    except Exception as exc:
        timestamp_text = datetime.now(NY_TZ).strftime("%Y-%m-%d %H:%M:%S %Z")
        _print_order_gate_error(
            driver,
            "order_gate_unable_load_market_clock_post_open_cleanup",
            f"timestamp={timestamp_text} | Order gate: unable to load market clock for post-open limit cleanup: {exc}",
        )
        return

    market_is_open = bool(getattr(clock, "is_open", False))
    if not market_is_open:
        return

    now_day_key = datetime.now(NY_TZ).strftime("%Y-%m-%d")
    if not force_cleanup and driver._post_open_limit_cleanup_day == now_day_key:
        return

    strategy_keys = sorted(strategy_keys)
    if not strategy_keys:
        driver._post_open_limit_cleanup_day = now_day_key
        return

    total_canceled = 0
    for symbol_key in sorted(driver.required_symbols):
        symbol_canceled = 0
        for strategy_key in strategy_keys:
            symbol_canceled += int(
                driver._cancel_all_limit_orders(
                    symbol_key,
                    strategy_label=strategy_key,
                    reason="post_open_cleanup",
                )
                or 0
            )
        if symbol_canceled > 0:
            print(
                "🧹 ",
                f"Order gate: post-open cleanup canceled {symbol_canceled} strategy-owned limit order(s) "
                f"for {symbol_key} strategies={','.join(strategy_keys)}",
            )
        total_canceled += symbol_canceled

    if not force_cleanup:
        driver._post_open_limit_cleanup_day = now_day_key
        print(
            "✅ ",
            f"Order gate: post-open strategy-owned limit cleanup complete day={now_day_key} "
            f"total_canceled={total_canceled}",
        )


def cancel_opposite_limit_orders(driver, symbol: str, incoming_side, strategy_label: str | None = None) -> int:
    """Cancel strategy-owned opposite-side open limits for symbol."""
    incoming_side_text = driver._normalize_order_status(incoming_side)
    if incoming_side_text == "buy":
        opposite_side = "sell"
    elif incoming_side_text == "sell":
        opposite_side = "buy"
    else:
        return 0

    strategy_key = driver._sanitize_strategy_label(strategy_label or "") if strategy_label else ""

    request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
    try:
        open_orders = driver.trading_client.get_orders(filter=request_params)
    except Exception as exc:
        _print_order_gate_error(
            driver,
            f"order_gate_unable_fetch_open_orders_opposite_{symbol}",
            f"Order gate: unable to fetch open orders for {symbol}: {exc}",
        )
        return 0

    canceled_count = 0
    for open_order in open_orders:
        order_symbol = str(getattr(open_order, "symbol", "")).upper()
        if order_symbol != symbol.upper():
            continue

        order_type = driver._normalize_order_status(getattr(open_order, "type", ""))
        order_side = driver._normalize_order_status(getattr(open_order, "side", ""))
        if order_type != "limit" or order_side != opposite_side:
            continue

        if strategy_key:
            order_strategy = driver._strategy_from_client_order_id(getattr(open_order, "client_order_id", ""))
            if order_strategy != strategy_key:
                continue

        order_id = str(getattr(open_order, "id", "") or "")
        if not order_id:
            continue

        status_text = driver._normalize_order_status(getattr(open_order, "status", ""))
        if _is_terminal_order_status(status_text):
            print(
                "ℹ️ ",
                f"Order gate: skipping cancel for terminal opposite limit order id={order_id} "
                f"symbol={symbol} status={status_text or 'unknown'}",
            )
            continue

        try:
            driver.trading_client.cancel_order_by_id(order_id=order_id)
            canceled_count += 1
            print("🧹 ",
                f"Order gate: canceled opposite limit order id={order_id} "
                f"symbol={symbol} side={order_side} strategy={strategy_key or 'any'}"
            )
        except Exception as exc:
            _print_order_gate_error(
                driver,
                f"order_gate_failed_cancel_opposite_limit_{symbol}",
                f"Order gate: failed to cancel opposite limit order id={order_id} "
                f"symbol={symbol}: {exc}",
            )

    if canceled_count > 0:
        driver._mark_limit_price_reset(symbol)

    return canceled_count


def cancel_all_limit_orders(
    driver,
    symbol: str,
    strategy_label: str | None = None,
    reason: str | None = None,
) -> int:
    """Cancel all strategy-owned open limit orders for symbol regardless of side."""
    strategy_key = driver._sanitize_strategy_label(strategy_label or "") if strategy_label else ""
    request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
    try:
        open_orders = driver.trading_client.get_orders(filter=request_params)
    except Exception as exc:
        _print_order_gate_error(
            driver,
            f"order_gate_unable_fetch_open_orders_eod_{symbol}",
            f"Order gate: unable to fetch open orders for {symbol}: {exc}",
        )
        return 0

    canceled_count = 0
    for open_order in open_orders:
        order_symbol = str(getattr(open_order, "symbol", "")).upper()
        if order_symbol != symbol.upper():
            continue
        order_type = driver._normalize_order_status(getattr(open_order, "type", ""))
        if order_type != "limit":
            continue

        if strategy_key:
            order_strategy = driver._strategy_from_client_order_id(getattr(open_order, "client_order_id", ""))
            if order_strategy != strategy_key:
                continue

        order_id = str(getattr(open_order, "id", "") or "")
        if not order_id:
            continue

        status_text = driver._normalize_order_status(getattr(open_order, "status", ""))
        if _is_terminal_order_status(status_text):
            print(
                "ℹ️ ",
                f"Order gate: skipping cancel for terminal limit order id={order_id} "
                f"symbol={symbol} status={status_text or 'unknown'}",
            )
            continue

        try:
            driver.trading_client.cancel_order_by_id(order_id=order_id)
            canceled_count += 1
            order_side = driver._normalize_order_status(getattr(open_order, "side", ""))
            reason_key = str(reason or "").strip().lower()
            if reason_key == "eod":
                action_label = "EOD canceled"
            elif reason_key == "post_open_cleanup":
                action_label = "post-open canceled"
            elif reason_key == "new_bar":
                action_label = "new-bar canceled"
            else:
                action_label = "canceled"
            print(
                "🧹 ",
                f"Order gate: {action_label} limit order id={order_id} "
                f"symbol={symbol} side={order_side} strategy={strategy_key or 'any'}",
            )
        except Exception as exc:
            _print_order_gate_error(
                driver,
                f"order_gate_failed_cancel_eod_limit_{symbol}",
                f"Order gate: failed to cancel EOD limit order id={order_id} "
                f"symbol={symbol}: {exc}",
            )

    if canceled_count > 0:
        driver._mark_limit_price_reset(symbol)

    return canceled_count


def cancel_all_open_orders(
    driver,
    symbol: str,
    strategy_label: str | None = None,
    reason: str | None = None,
) -> int:
    """Cancel all strategy-owned open orders for a symbol regardless of order type."""
    strategy_key = driver._sanitize_strategy_label(strategy_label or "") if strategy_label else ""
    request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
    try:
        open_orders = driver.trading_client.get_orders(filter=request_params)
    except Exception as exc:
        _print_order_gate_error(
            driver,
            f"order_gate_unable_fetch_open_orders_all_{symbol}",
            f"Order gate: unable to fetch open orders for {symbol}: {exc}",
        )
        return 0

    canceled_count = 0
    for open_order in open_orders:
        order_symbol = str(getattr(open_order, "symbol", "") or "").upper()
        if order_symbol != str(symbol or "").upper():
            continue

        if strategy_key:
            order_strategy = driver._strategy_from_client_order_id(getattr(open_order, "client_order_id", ""))
            if order_strategy != strategy_key:
                continue

        order_id = str(getattr(open_order, "id", "") or "")
        if not order_id:
            continue

        status_text = driver._normalize_order_status(getattr(open_order, "status", ""))
        if _is_terminal_order_status(status_text):
            continue

        try:
            driver.trading_client.cancel_order_by_id(order_id=order_id)
            canceled_count += 1
            order_type = driver._normalize_order_status(getattr(open_order, "type", "")) or "unknown"
            order_side = driver._normalize_order_status(getattr(open_order, "side", "")) or "unknown"
            reason_key = str(reason or "").strip().lower()
            action_label = "canceled"
            if reason_key == "new_bar":
                action_label = "new-bar canceled"
            print(
                "🧹 ",
                f"Order gate: {action_label} open order id={order_id} "
                f"symbol={symbol} type={order_type} side={order_side} strategy={strategy_key or 'any'}",
            )
        except Exception as exc:
            _print_order_gate_error(
                driver,
                f"order_gate_failed_cancel_all_{symbol}",
                f"Order gate: failed to cancel open order id={order_id} symbol={symbol}: {exc}",
            )

    if canceled_count > 0:
        driver._mark_limit_price_reset(symbol)

    return canceled_count


def count_open_limit_orders(driver, symbol: str, strategy_label: str | None = None) -> int:
    """Return number of currently open strategy-owned limit orders for symbol."""
    strategy_key = driver._sanitize_strategy_label(strategy_label or "") if strategy_label else ""
    request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
    try:
        open_orders = driver.trading_client.get_orders(filter=request_params)
    except Exception as exc:
        _print_order_gate_error(
            driver,
            f"order_gate_unable_count_open_orders_{symbol}",
            f"Order gate: unable to count open orders for {symbol}: {exc}",
        )
        return 0

    count = 0
    for open_order in open_orders:
        order_symbol = str(getattr(open_order, "symbol", "")).upper()
        if order_symbol != symbol.upper():
            continue
        order_type = driver._normalize_order_status(getattr(open_order, "type", ""))
        if order_type != "limit":
            continue
        if strategy_key:
            order_strategy = driver._strategy_from_client_order_id(getattr(open_order, "client_order_id", ""))
            if order_strategy != strategy_key:
                continue
        count += 1
    return count


def list_open_limit_orders(driver, symbol: str, strategy_label: str | None = None) -> list[str]:
    """Return human-readable summaries of open strategy-owned limit orders for symbol."""
    strategy_key = driver._sanitize_strategy_label(strategy_label or "") if strategy_label else ""
    request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
    try:
        open_orders = driver.trading_client.get_orders(filter=request_params)
    except Exception as exc:
        _print_order_gate_error(
            driver,
            f"order_gate_unable_list_open_limits_{symbol}",
            f"Order gate: unable to list open limit orders for {symbol}: {exc}",
        )
        return []

    details: list[str] = []
    for open_order in open_orders:
        order_symbol = str(getattr(open_order, "symbol", "") or "").upper()
        if order_symbol != str(symbol or "").upper():
            continue

        order_type = driver._normalize_order_status(getattr(open_order, "type", ""))
        if order_type != "limit":
            continue

        order_strategy = driver._strategy_from_client_order_id(getattr(open_order, "client_order_id", ""))
        if strategy_key and order_strategy != strategy_key:
            continue

        order_side = driver._normalize_order_status(getattr(open_order, "side", "")) or "unknown"
        limit_price = getattr(open_order, "limit_price", None)
        if limit_price is None:
            continue

        try:
            limit_price_value = float(limit_price)
        except (TypeError, ValueError):
            continue

        details.append(f"{order_symbol}:{order_side}@{limit_price_value:.2f}#{order_strategy}")

    return details


def list_open_limit_orders_by_strategy(driver) -> dict[str, dict[str, list[float]]]:
    """Return open limit orders grouped by strategy key/symbol as signed prices."""
    request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=driver.symbols)
    try:
        open_orders = driver.trading_client.get_orders(filter=request_params)
    except Exception as exc:
        _print_order_gate_error(
            driver,
            "order_gate_unable_list_open_limits_by_strategy",
            f"Order gate: unable to list open limit orders by strategy: {exc}",
        )
        return {}

    grouped: dict[str, dict[str, list[float]]] = {}
    required = set(driver.symbols)
    for open_order in open_orders:
        order_symbol = str(getattr(open_order, "symbol", "") or "").upper()
        if order_symbol not in required:
            continue

        order_type = driver._normalize_order_status(getattr(open_order, "type", ""))
        if order_type != "limit":
            continue

        limit_price = getattr(open_order, "limit_price", None)
        if limit_price is None:
            continue
        try:
            limit_price_value = float(limit_price)
        except (TypeError, ValueError):
            continue

        order_side = driver._normalize_order_status(getattr(open_order, "side", "")) or "unknown"
        strategy_key = driver._strategy_from_client_order_id(getattr(open_order, "client_order_id", ""))
        signed_price = -limit_price_value if order_side == "buy" else limit_price_value
        strategy_bucket = grouped.setdefault(strategy_key, {})
        strategy_bucket.setdefault(order_symbol, []).append(float(signed_price))

    return grouped
