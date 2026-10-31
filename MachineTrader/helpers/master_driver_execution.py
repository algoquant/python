from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import Any, Iterable

from alpaca.trading.enums import OrderSide
from MachineTrader.helpers.broker_orders import resolve_insufficient_qty_retry

try:
    from MachineTrader.helpers.driver_common import NY_TZ
    from MachineTrader.helpers.alpacasdk import Trading
    from MachineTrader.helpers.api_responses import ORDER_STATUS_GROUPS
    from MachineTrader.helpers.file_writing_helpers import sync_strategy_daily_file_names
except ImportError:
    from MachineTrader.helpers.driver_common import NY_TZ
    from MachineTrader.helpers.alpacasdk import Trading
    from MachineTrader.helpers.api_responses import ORDER_STATUS_GROUPS
    from MachineTrader.helpers.file_writing_helpers import sync_strategy_daily_file_names


def print_trade_gate_summary(gate_type: str, symbols: Iterable[str]) -> None:
    symbol_keys = sorted({str(symbol or "").strip().upper() for symbol in symbols if str(symbol or "").strip()})
    if not symbol_keys:
        return
    print("⏸️ ", f"Trade deltas gated type={gate_type} symbols={symbol_keys}")


async def handle_trade_update_signed_queue(
    event_data,
    *,
    trade_symbol: str,
    alpaca_sdk,
    strategy_name: str,
    dir_name: str | None,
    timezone,
    orders_list: dict,
    position_queue: dict[str, list[float]],
    order_filled_qty: dict,
    latest_data: dict,
    pnl_real: float,
    position_shares: int,
    state_ref: dict[str, Any] | None = None,
) -> tuple[float, int]:
    """Driver-level trade confirmation handler for signed-queue strategy state.

    Strategies should call this helper instead of implementing trade confirmation
    logic inline.
    """
    if state_ref is not None:
        pnl_real = float(state_ref.get("pnl_real", pnl_real))
        position_shares = int(state_ref.get("position_shares", position_shares))

    file_names = sync_strategy_daily_file_names(alpaca_sdk, strategy_name, dir_name, timezone)
    fills_file = file_names["fills_file"]
    canceled_file = file_names["canceled_file"]

    trading_helper = Trading(trade_symbol)
    symbol_key = str(trade_symbol or "").upper()
    if not isinstance(position_queue, dict):
        position_queue = {}
    queue_prices = position_queue.get(symbol_key, [])
    if not isinstance(queue_prices, list):
        queue_prices = []

    result = await trading_helper.handle_trade_event_signed_queue(
        event_data=event_data,
        orders_list=orders_list,
        queue_prices=queue_prices,
        pnl_real=pnl_real,
        order_filled_qty=order_filled_qty,
        fills_file=fills_file,
        canceled_file=canceled_file,
    )

    position_queue[symbol_key] = list(queue_prices)

    if not result.get("processed"):
        return float(pnl_real), int(position_shares)

    updated_pnl_real = float(result.get("pnl_real", pnl_real))
    updated_position_shares = int(result.get("position_shares", position_shares))
    latest_data.update(
        {
            "position_shares": updated_position_shares,
            "pnl_real": updated_pnl_real,
            "pending_orders": int(result.get("pending_orders", len(orders_list))),
        }
    )

    if state_ref is not None:
        state_ref["pnl_real"] = updated_pnl_real
        state_ref["position_shares"] = updated_position_shares

    return updated_pnl_real, updated_position_shares


def _insufficient_qty_retry_amount(driver, symbol: str, side_text: str, requested_qty: int) -> int:
    # Outside regular session, qty_available is often reported as zero even when
    # the intended close/flatten logic should continue via limit repricing.
    # Skip available-share-based fallback sizing in closed-market mode.
    market_open_checker = getattr(driver, "_is_market_open_now", None)
    if callable(market_open_checker):
        try:
            if not bool(market_open_checker()):
                return 0
        except Exception:
            return 0

    rejection = getattr(driver, "_last_submit_rejection", None)
    same_symbol_rejection = (
        isinstance(rejection, dict)
        and str(rejection.get("symbol", "")).upper() == str(symbol or "").upper()
        and str(rejection.get("side", "")).lower() == str(side_text or "").lower()
        and bool(rejection.get("is_insufficient_qty", False))
    )
    if not same_symbol_rejection:
        return 0

    alpaca_api = getattr(driver, "alpaca_api", None)
    resolver = getattr(alpaca_api, "resolve_submittable_qty", None)
    retry_qty = resolve_insufficient_qty_retry(
        requested_qty,
        side_text,
        rejection_payload=rejection,
        broker_qty=0.0,
        resolver=resolver,
    )
    return int(max(0, retry_qty))


def _submit_available_qty_after_insufficient(
    driver,
    *,
    symbol: str,
    side: OrderSide,
    side_text: str,
    requested_qty: int,
    order_type: str,
    limit_price: float | None,
) -> str | None:
    retry_qty = _insufficient_qty_retry_amount(driver, symbol, side_text, requested_qty)
    if retry_qty <= 0:
        print(
            "⏳ ",
            f"Order gate: no shares available for {symbol} side={side_text} requested_qty={requested_qty}; "
            "waiting for next bar.",
        )
        return None

    retry_order_id = driver._submit_order(symbol, side, float(retry_qty), order_type, limit_price)
    if not retry_order_id:
        print(
            "⏳ ",
            f"Order gate: insufficient qty fallback submit failed for {symbol} side={side_text}; "
            f"requested_qty={requested_qty} available_qty={retry_qty}. Waiting for next bar.",
        )
        return None

    print(
        "🔁 ",
        f"Order gate: insufficient qty fallback for {symbol} side={side_text}; "
        f"requested_qty={requested_qty} available_qty={retry_qty} order_id={retry_order_id}. "
        "Waiting for next bar while confirm stream updates position queues.",
    )
    return str(retry_order_id)


async def wait_for_limit_cancellations(
    driver,
    symbol: str,
    strategy_label: str | None = None,
    timeout_seconds: float = 30.0,
    poll_interval_seconds: float = 0.2,
) -> bool:
    """Wait until strategy-owned open limit orders for symbol reach zero."""
    deadline = asyncio.get_running_loop().time() + max(0.0, float(timeout_seconds))
    while True:
        remaining = driver._count_open_limit_orders(symbol, strategy_label=strategy_label)
        if remaining <= 0:
            return True
        if asyncio.get_running_loop().time() >= deadline:
            return False
        await asyncio.sleep(max(0.05, float(poll_interval_seconds)))


async def wait_for_market_order_resolution(driver, order_id: str) -> tuple[bool, int]:
    if not order_id:
        return False, 0

    started = datetime.now(NY_TZ)
    pending_statuses = ORDER_STATUS_GROUPS["pending"]
    terminal_statuses = ORDER_STATUS_GROUPS["terminal_excluding_filled"]
    update_events = getattr(driver, "_broker_order_update_events_by_id", None)

    while True:
        age = (datetime.now(NY_TZ) - started).total_seconds()
        if age > driver.order_fill_timeout:
            print(
                "⏰ ",
                f"Order gate: fill wait timeout for order_id={order_id}. "
                "Keeping market-order lock active; no new market orders will be submitted until status is terminal.",
            )
            return False, 0

        order = driver._latest_broker_order_update(order_id)
        if isinstance(order, dict):
            status = driver._normalize_order_status(order.get("status") or order.get("event") or order.get("order_status"))
            filled_qty = int(round(float(order.get("filled_qty", 0.0) or 0.0)))
            requested_qty = int(round(float(order.get("qty", filled_qty) or filled_qty)))

            if status == "filled":
                driver._compute_realized_pnl_from_local_signed_queue()
                return True, requested_qty
            if status in terminal_statuses:
                driver._compute_realized_pnl_from_local_signed_queue()
                print("⚠️ ", f"Order gate: order {order_id} ended in terminal status={status} filled_qty={filled_qty}")
                return False, filled_qty
            if status not in pending_statuses:
                print("ℹ️ ", f"Order gate: order {order_id} replaced status={status}; waiting for terminal update")

        event_obj = None
        if isinstance(update_events, dict):
            event_obj = update_events.get(order_id)
            if event_obj is None:
                event_obj = asyncio.Event()
                update_events[order_id] = event_obj
        remaining_timeout = max(0.0, float(driver.order_fill_timeout) - age)
        if event_obj is None:
            await asyncio.sleep(max(0.05, float(driver.order_fill_poll_seconds or 0.2)))
            continue
        try:
            await asyncio.wait_for(event_obj.wait(), timeout=remaining_timeout)
        except asyncio.TimeoutError:
            print(
                "⏰ ",
                f"Order gate: fill wait timeout for order_id={order_id}. "
                "Keeping market-order lock active; no new market orders will be submitted until status is terminal.",
            )
            return False, 0
        finally:
            if event_obj.is_set():
                event_obj.clear()


async def execute_per_share_take_profit_loop(driver, symbol: str, delta_qty: float, hint: dict[str, Any]):
    requested_qty = int(round(abs(float(delta_qty))))
    if requested_qty <= 0:
        return

    close_side = OrderSide.BUY if float(delta_qty) > 0 else OrderSide.SELL
    per_share_take_profit_level = driver._safe_float(hint.get("per_share_take_profit_level"), default=0.0)
    close_side_text = driver._normalize_order_status(close_side)
    print(
        "🎯 ",
        f"Order gate: per-share take-profit execution for {symbol}; "
        f"requested_qty={requested_qty} side={close_side_text} "
        f"per_share_take_profit_level={per_share_take_profit_level:.4f}.",
    )
    order_id = driver._submit_order(symbol, close_side, float(requested_qty), "market", None)
    if order_id:
        print(
            "📝 ",
            f"Per-share take-profit order submitted for {symbol}; order_id={order_id}. "
            "Fill and partial-fill accounting will continue through the confirmation stream.",
        )
        return

    rejection = getattr(driver, "_last_submit_rejection", None)
    is_insufficient_qty = bool(isinstance(rejection, dict) and rejection.get("is_insufficient_qty", False))
    if is_insufficient_qty:
        _submit_available_qty_after_insufficient(
            driver,
            symbol=symbol,
            side=close_side,
            side_text=close_side_text,
            requested_qty=requested_qty,
            order_type="market",
            limit_price=None,
        )


async def execute_symbol_delta(driver, symbol: str, delta_qty: float, current_qty: float):
    """Execute delta trade with flip-safe behavior."""
    qty = int(round(delta_qty))
    current = int(round(current_qty))

    # A zero strategy delta means no new intent; keep any submitted order alive.
    if qty == 0:
        return

    tracked_orders_lookup = getattr(driver, "_tracked_open_orders_for_symbol", None)
    if callable(tracked_orders_lookup):
        tracked_orders = tracked_orders_lookup(symbol)
    else:
        tracked_order_lookup = getattr(driver, "_tracked_open_order_for_symbol", None)
        tracked_order = tracked_order_lookup(symbol) if callable(tracked_order_lookup) else None
        tracked_orders = [tracked_order] if tracked_order is not None else []

    matching_order_ids: list[str] = []
    waiting_order_ids: list[str] = []
    cancel_tracked_order = getattr(driver, "_cancel_tracked_order", None)
    for order_id, order_metadata in tracked_orders:
        pending_delta = float(order_metadata.get("delta", 0.0) or 0.0)
        if pending_delta == float(qty):
            matching_order_ids.append(order_id)
            continue
        if not callable(cancel_tracked_order) or not cancel_tracked_order(order_id):
            waiting_order_ids.append(order_id)

    if waiting_order_ids:
        return "tracked_order_pending"

    if matching_order_ids:
        print(
            "⏭️ ",
            f"Order gate: keeping tracked order id={matching_order_ids[0]} for {symbol}; "
            f"strategy delta remains {qty}.",
        )
        return

    def _clear_symbol_working_balance() -> None:
        balance_map = getattr(driver, "_working_balance_by_symbol", None)
        if isinstance(balance_map, dict):
            balance_map[symbol] = 0.0

    post_qty = current + qty
    crosses_zero = current != 0 and post_qty != 0 and (current > 0) != (post_qty > 0)
    bar_driven_mode = bool(getattr(driver, "_use_bar_driven_execution_mode", lambda: False)())
    market_is_open = bool(driver._is_market_open_now())

    async def _execute_position_flip(*, force_market: bool = False, rebuild_limits: bool = False) -> None:
        flatten_side = OrderSide.SELL if current > 0 else OrderSide.BUY
        flatten_side_text = driver._normalize_order_status(flatten_side)
        flatten_order_type, flatten_limit = driver._resolve_order_preference(symbol, flatten_side)
        if force_market:
            flatten_order_type = "market"
            flatten_limit = None
        elif rebuild_limits and flatten_order_type == "limit":
            rebuilt_flatten_limit = driver._rebuild_limit_price_from_live_inputs(symbol, flatten_side)
            if rebuilt_flatten_limit is not None:
                flatten_limit = rebuilt_flatten_limit
        print(
            "✂️ ",
            f"Order split: {symbol} request={qty} would flip position {current:+d} → {post_qty:+d}. "
            f"Step 1: {flatten_side_text} {abs(current)} to flatten. "
            f"Step 2: {driver._normalize_order_status(OrderSide.BUY if post_qty > 0 else OrderSide.SELL)} {abs(post_qty)} to open.",
        )
        flatten_order_id = driver._submit_order(
            symbol,
            flatten_side,
            float(abs(current)),
            flatten_order_type,
            flatten_limit,
        )
        if not flatten_order_id:
            rejection = getattr(driver, "_last_submit_rejection", None)
            if bool(isinstance(rejection, dict) and rejection.get("is_insufficient_qty", False)):
                _submit_available_qty_after_insufficient(
                    driver,
                    symbol=symbol,
                    side=flatten_side,
                    side_text=flatten_side_text,
                    requested_qty=int(abs(current)),
                    order_type=flatten_order_type,
                    limit_price=flatten_limit,
                )
            _clear_symbol_working_balance()
            return
        if not await driver._wait_for_fill(flatten_order_id):
            return

        open_side = OrderSide.BUY if post_qty > 0 else OrderSide.SELL
        open_side_text = driver._normalize_order_status(open_side)
        open_order_type, open_limit = driver._resolve_order_preference(symbol, open_side)
        if force_market:
            open_order_type = "market"
            open_limit = None
        elif rebuild_limits and open_order_type == "limit":
            rebuilt_open_limit = driver._rebuild_limit_price_from_live_inputs(symbol, open_side)
            if rebuilt_open_limit is not None:
                open_limit = rebuilt_open_limit
        open_order_id = driver._submit_order(
            symbol,
            open_side,
            float(abs(post_qty)),
            open_order_type,
            open_limit,
        )
        if not open_order_id:
            rejection = getattr(driver, "_last_submit_rejection", None)
            if bool(isinstance(rejection, dict) and rejection.get("is_insufficient_qty", False)):
                _submit_available_qty_after_insufficient(
                    driver,
                    symbol=symbol,
                    side=open_side,
                    side_text=open_side_text,
                    requested_qty=int(abs(post_qty)),
                    order_type=open_order_type,
                    limit_price=open_limit,
                )
            _clear_symbol_working_balance()
            return
        await driver._wait_for_fill(open_order_id)

    async def _submit_position_flatten_leg() -> None:
        """Flip step 1 only: flatten now, let the next bar's delta open the new side."""
        flatten_side = OrderSide.SELL if current > 0 else OrderSide.BUY
        flatten_side_text = driver._normalize_order_status(flatten_side)
        flatten_order_type, flatten_limit = driver._resolve_order_preference(symbol, flatten_side)
        print(
            "✂️ ",
            f"Order split: {symbol} request={qty} would flip position {current:+d} → {post_qty:+d}. "
            f"Step 1: {flatten_side_text} {abs(current)} to flatten now. "
            f"Step 2: deferred to the next bar so the confirm stream can update the position queue.",
        )
        flatten_order_id = driver._submit_order(
            symbol,
            flatten_side,
            float(abs(current)),
            flatten_order_type,
            flatten_limit,
        )
        if not flatten_order_id:
            rejection = getattr(driver, "_last_submit_rejection", None)
            if bool(isinstance(rejection, dict) and rejection.get("is_insufficient_qty", False)):
                _submit_available_qty_after_insufficient(
                    driver,
                    symbol=symbol,
                    side=flatten_side,
                    side_text=flatten_side_text,
                    requested_qty=int(abs(current)),
                    order_type=flatten_order_type,
                    limit_price=flatten_limit,
                )
            _clear_symbol_working_balance()

    if crosses_zero and bar_driven_mode:
        await _submit_position_flatten_leg()
        return

    if crosses_zero and not market_is_open:
        await _execute_position_flip()
        return

    if bar_driven_mode:
        side = OrderSide.BUY if qty > 0 else OrderSide.SELL
        side_text = driver._normalize_order_status(side)
        order_type, limit_price = driver._resolve_order_preference(symbol, side)

        order_id = driver._submit_order(symbol, side, float(abs(qty)), order_type, limit_price)
        if not order_id:
            rejection = getattr(driver, "_last_submit_rejection", None)
            is_insufficient_qty = bool(isinstance(rejection, dict) and rejection.get("is_insufficient_qty", False))
            if is_insufficient_qty:
                _submit_available_qty_after_insufficient(
                    driver,
                    symbol=symbol,
                    side=side,
                    side_text=side_text,
                    requested_qty=int(abs(qty)),
                    order_type=order_type,
                    limit_price=limit_price,
                )
            _clear_symbol_working_balance()
            return

        print(
            "📝 ",
            f"Bar-driven execution: submitted symbol={symbol} side={side_text} qty={abs(qty)} "
            f"order_type={order_type} order_id={order_id}. Awaiting confirm stream on next bar.",
        )
        return

    # Closed-market mode: submit one repriced limit order for the entire current
    # working balance and let confirmations update balances asynchronously.
    if not market_is_open:
        side = OrderSide.BUY if qty > 0 else OrderSide.SELL
        side_text = driver._normalize_order_status(side)
        order_type, limit_price = driver._resolve_order_preference(symbol, side)
        if order_type != "limit" or limit_price is None or float(limit_price or 0.0) <= 0.0:
            rebuilt_limit = driver._rebuild_limit_price_from_live_inputs(symbol, side)
            if rebuilt_limit is not None and float(rebuilt_limit) > 0.0:
                order_type = "limit"
                limit_price = float(rebuilt_limit)

        if order_type != "limit" or limit_price is None or float(limit_price or 0.0) <= 0.0:
            print(
                "⚠️ ",
                f"Closed-market limit mode: unable to derive limit price for {symbol} side={side_text} balance={qty}.",
            )
            return

        order_id = driver._submit_order(symbol, side, float(abs(qty)), "limit", float(limit_price))
        if not order_id:
            rejection = getattr(driver, "_last_submit_rejection", None)
            is_insufficient_qty = bool(isinstance(rejection, dict) and rejection.get("is_insufficient_qty", False))
            if is_insufficient_qty:
                _submit_available_qty_after_insufficient(
                    driver,
                    symbol=symbol,
                    side=side,
                    side_text=side_text,
                    requested_qty=int(abs(qty)),
                    order_type="limit",
                    limit_price=float(limit_price),
                )
            _clear_symbol_working_balance()
            return

        print(
            "📝 ",
            f"Closed-market limit mode: submitted symbol={symbol} side={side_text} qty={abs(qty)} "
            f"limit={float(limit_price):.4f} order_id={order_id}. Waiting for next bar reprice cycle.",
        )
        return

    intended_side = OrderSide.BUY if qty > 0 else OrderSide.SELL

    hint = driver.latest_execution_hints.get(symbol, {})
    strategy_label = str(hint.get("strategy", "master_driver") or "master_driver")
    intended_side_text = driver._normalize_order_status(intended_side)
    opposite_side_text = "sell" if intended_side_text == "buy" else "buy"

    canceled_limits_this_cycle = False
    is_liquidation_trade = current != 0 and ((current > 0 and qty < 0) or (current < 0 and qty > 0))
    if is_liquidation_trade and not bool(hint.get("eod_flatten", False)):
        print(
            "🧹 ",
            f"Order gate: liquidation detected for {symbol}; canceling strategy-owned open limit orders "
            f"for strategy={strategy_label} before new submission.",
        )
        canceled_count = driver._cancel_all_limit_orders(symbol, strategy_label=strategy_label)
        canceled_limits_this_cycle = canceled_limits_this_cycle or (canceled_count > 0)

    if hint.get("eod_flatten"):
        existing_eod_limits = driver._count_open_limit_orders(symbol, strategy_label=strategy_label)
        if existing_eod_limits > 0:
            open_limit_details = driver._list_open_limit_orders(symbol, strategy_label=strategy_label)
            has_opposite_limits = any(
                detail.startswith(f"{symbol}:{opposite_side_text}@") for detail in open_limit_details
            )
            has_same_side_limits = any(
                detail.startswith(f"{symbol}:{intended_side_text}@") for detail in open_limit_details
            )

            if has_opposite_limits:
                print(
                    "🧹 ",
                    f"Order gate: EOD flatten for {symbol}; canceling opposite-side open strategy-owned "
                    f"limit orders for strategy={strategy_label} before flatten submit.",
                )
                canceled_count = driver._cancel_opposite_limit_orders(
                    symbol,
                    incoming_side=intended_side,
                    strategy_label=strategy_label,
                )
                canceled_limits_this_cycle = canceled_limits_this_cycle or (canceled_count > 0)

                cancellations_cleared = await wait_for_limit_cancellations(
                    driver,
                    symbol,
                    strategy_label=strategy_label,
                    timeout_seconds=30.0,
                    poll_interval_seconds=0.2,
                )
                if not cancellations_cleared:
                    remaining_eod_limits = driver._count_open_limit_orders(symbol, strategy_label=strategy_label)
                    print(
                        "⏸️ ",
                        f"Order gate: EOD flatten waiting for opposite limit cancellations for {symbol}; "
                        f"remaining_open_limits={remaining_eod_limits} strategy={strategy_label}. "
                        "Skipping flatten submission this cycle."
                    )
                    return

            if has_same_side_limits and not has_opposite_limits:
                print(
                    "⏳ ",
                    f"Order gate: EOD flatten pending for {symbol}; keeping existing same-side strategy-owned "
                    f"limit order(s) for strategy={strategy_label} and skipping re-submission this cycle."
                )
                return

    if hint.get("take_profit_triggered"):
        print("🎯 ",
            f"Order gate: TAKE-PROFIT triggered for {symbol}; "
            f"canceling strategy-owned limit orders and resetting limit price calculator."
        )
        canceled_count = driver._cancel_all_limit_orders(symbol, strategy_label=strategy_label)
        canceled_limits_this_cycle = canceled_limits_this_cycle or (canceled_count > 0)
        driver._mark_limit_price_reset(symbol)

    take_profit_triggered = bool(hint.get("take_profit_triggered", False))
    take_profit_reason = str(hint.get("take_profit_reason", "") or "").strip().lower()

    if take_profit_triggered and take_profit_reason == "per_share":
        await execute_per_share_take_profit_loop(driver, symbol=symbol, delta_qty=float(qty), hint=hint)
        return

    if crosses_zero:
        await _execute_position_flip(
            force_market=take_profit_triggered,
            rebuild_limits=canceled_limits_this_cycle,
        )
        return

    side = OrderSide.BUY if qty > 0 else OrderSide.SELL
    side_text = driver._normalize_order_status(side)
    order_type, limit_price = driver._resolve_order_preference(symbol, side)
    if take_profit_triggered:
        order_type = "market"
        limit_price = None
    elif order_type == "limit" and canceled_limits_this_cycle:
        rebuilt_limit = driver._rebuild_limit_price_from_live_inputs(symbol, side)
        if rebuilt_limit is not None:
            limit_price = rebuilt_limit

    # Allow hints to override order type (e.g., for EOD flatten to force market orders)
    hint_order_type = str(hint.get("order_type", "") or "").strip().lower()
    if hint_order_type in ("market", "limit"):
        order_type = hint_order_type
        if hint_order_type == "market":
            limit_price = None

    requested_qty = int(round(abs(float(qty))))
    if requested_qty <= 0:
        return

    order_id = driver._submit_order(symbol, side, float(requested_qty), order_type, limit_price)
    if not order_id:
        rejection = getattr(driver, "_last_submit_rejection", None)
        is_insufficient_qty = (
            isinstance(rejection, dict)
            and str(rejection.get("symbol", "")).upper() == str(symbol or "").upper()
            and str(rejection.get("side", "")).lower() == side_text
            and bool(rejection.get("is_insufficient_qty", False))
        )
        if is_insufficient_qty:
            _submit_available_qty_after_insufficient(
                driver,
                symbol=symbol,
                side=side,
                side_text=side_text,
                requested_qty=requested_qty,
                order_type=order_type,
                limit_price=limit_price,
            )
        _clear_symbol_working_balance()
        return

    fully_filled, filled_qty = await wait_for_market_order_resolution(driver, order_id)
    driver._refresh_broker_state()

    if filled_qty <= 0 and not fully_filled:
        print(
            "⏳ ",
            f"Order gate: no confirmed fill progress for {symbol}; requested_qty={requested_qty}. "
            "Waiting for next bar strategy signal.",
        )
        return

    if not fully_filled and filled_qty > 0:
        remaining_qty = max(0, int(requested_qty - int(filled_qty)))
        if remaining_qty > 0:
            print(
                "⏳ ",
                f"Order gate: partial fill for {symbol}; filled={filled_qty} remaining_qty={remaining_qty}. "
                "Waiting for next bar strategy signal.",
            )
    return


async def execute_bar_deltas(driver, execution_deltas_by_symbol: dict[str, float], positions_snapshot: dict[str, dict]):
    """Submit one pass of per-symbol deltas for the current bar.

    A failure on one symbol must not stop the remaining symbols, and the loop yields
    between submissions so the confirmation listener keeps draining mid-pass.
    """
    submitted_count = 0
    failed_symbols: list[str] = []
    gated_symbols_by_type: dict[str, list[str]] = {}

    for symbol in sorted(driver.required_symbols):
        delta_qty = float(execution_deltas_by_symbol.get(symbol, 0.0) or 0.0)
        current_qty = positions_snapshot.get(symbol, {}).get("qty", 0.0)
        try:
            gate_type = await driver._execute_symbol_delta(
                symbol=symbol,
                delta_qty=delta_qty,
                current_qty=current_qty,
            )
            if gate_type:
                gated_symbols_by_type.setdefault(str(gate_type), []).append(symbol)
            submitted_count += 1
        except Exception as exc:
            failed_symbols.append(symbol)
            print(
                "❌ ",
                f"Order submit raised for symbol={symbol} delta={delta_qty:.4f}: {exc}. "
                "Continuing with the remaining symbols.",
            )
        await asyncio.sleep(0)

    for gate_type, symbols in sorted(gated_symbols_by_type.items()):
        print_trade_gate_summary(gate_type, symbols)

    if failed_symbols:
        print(
            "⚠️ ",
            f"Bar submission pass finished with errors: submitted={submitted_count} "
            f"failed={sorted(failed_symbols)}",
        )
