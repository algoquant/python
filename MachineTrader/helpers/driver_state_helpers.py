from __future__ import annotations

"""Driver state helper accessors.

Uses lazy imports to avoid import cycles during AlpacaSDK package initialization.
"""

import asyncio
import os
from datetime import datetime

from alpaca.trading.enums import OrderSide
from MachineTrader.helpers.api_parsing import normalize_order_status
from MachineTrader.helpers.api_responses import ORDER_STATUS_GROUPS, event_in_group, status_in_group

try:
    from MachineTrader.helpers.driver_common import NY_TZ
except ImportError:
    from MachineTrader.helpers.driver_common import NY_TZ


PENDING_ORDER_STATUSES = set(ORDER_STATUS_GROUPS["pending"])
FILLED_ORDER_STATUSES = set(ORDER_STATUS_GROUPS["filled"])
TERMINAL_ORDER_STATUSES = set(ORDER_STATUS_GROUPS["terminal_excluding_filled"])


def _canonical_fill_side(value) -> str:
    text = categorize_order_status(value)
    if not text:
        return ""

    normalized = text.replace("-", "_").replace(" ", "_")
    if normalized in {"long", "cover", "buy_to_cover", "btc", "b"}:
        return "buy"
    if normalized in {"short", "sell_short", "sell_to_open", "sto", "s"}:
        return "sell"

    if "buy" in normalized:
        return "buy"
    if "sell" in normalized:
        return "sell"

    if normalized.endswith("_long"):
        return "buy"
    if normalized.endswith("_short"):
        return "sell"

    return ""


def _bo():
    import MachineTrader.helpers.broker_orders as mod
    return mod


def _cp():
    import MachineTrader.helpers.calc_pnls as mod
    return mod


def cancel_all_limit_orders(*args, **kwargs):
    return _bo().cancel_all_limit_orders(*args, **kwargs)


def cancel_opposite_limit_orders(*args, **kwargs):
    return _bo().cancel_opposite_limit_orders(*args, **kwargs)


def wait_for_opposite_limit_cancellations(*args, **kwargs):
    return _bo().wait_for_opposite_limit_cancellations(*args, **kwargs)


def categorize_order_status(*args, **kwargs):
    if not args:
        return ""
    raw_status = args[0]
    return normalize_order_status(raw_status)


def compare_position_records_with_alpaca(*args, **kwargs):
    return _cp().compare_position_records_with_alpaca(*args, **kwargs)


def compute_positions_from_local_signed_queue(*args, **kwargs):
    return _cp().compute_positions_from_local_signed_queue(*args, **kwargs)


def compute_realized_pnl_from_local_signed_queue(*args, **kwargs):
    return _cp().compute_realized_pnl_from_local_signed_queue(*args, **kwargs)


def compute_unrealized_pnl_from_local_signed_queue(*args, **kwargs):
    return _cp().compute_unrealized_pnl_from_local_signed_queue(*args, **kwargs)


def count_open_limit_orders(*args, **kwargs):
    return _bo().count_open_limit_orders(*args, **kwargs)


def enforce_limit_spacing(*args, **kwargs):
    if len(args) < 4:
        return float(args[3]) if len(args) > 3 else 0.0

    driver, symbol, side, proposed_limit_price = args[0], args[1], args[2], args[3]
    proposed = float(proposed_limit_price or 0.0)

    list_open = getattr(driver, "_list_open_limit_orders", None)
    if not callable(list_open):
        return proposed

    try:
        open_details = list_open(symbol, strategy_label=None) or []
    except Exception:
        return proposed

    side_text = categorize_order_status(side)
    prices: list[float] = []
    for detail in open_details:
        text = str(detail or "")
        if f":{side_text}@" not in text:
            continue
        try:
            price_text = text.split("@", 1)[1].split("#", 1)[0]
            prices.append(float(price_text))
        except Exception:
            continue

    if not prices:
        return proposed

    step = max(0.01, float(getattr(driver, "strategy_params", {}).get("limit_spread", 1.0) or 1.0) * 0.01)
    if side_text == "buy":
        best_existing = min(prices)
        if proposed >= best_existing:
            return float(round(best_existing - step, 2))
    elif side_text == "sell":
        best_existing = max(prices)
        if proposed <= best_existing:
            return float(round(best_existing + step, 2))

    return proposed


def is_market_open_now(*args, **kwargs):
    driver = args[0] if args else None
    if driver is None:
        return False

    now_ny = datetime.now(NY_TZ)

    # Use a short cache window to avoid hammering /clock on every symbol/minute path.
    cache_ttl = max(5.0, float(os.getenv("MARKET_CLOCK_CACHE_SECONDS", "60") or 60.0))
    cached_at = getattr(driver, "_market_clock_cached_at", None)
    cached_open = getattr(driver, "_market_clock_cached_is_open", None)
    if isinstance(cached_at, datetime) and cached_open is not None:
        if (now_ny - cached_at).total_seconds() <= cache_ttl:
            return bool(cached_open)

    trading_client = getattr(driver, "trading_client", None)
    if trading_client is None:
        return False

    try:
        clock = trading_client.get_clock()
        is_open = bool(getattr(clock, "is_open", False))
        setattr(driver, "_market_clock_cached_is_open", is_open)
        setattr(driver, "_market_clock_cached_at", now_ny)
        return is_open
    except Exception:
        if cached_open is not None:
            return bool(cached_open)

        if now_ny.weekday() >= 5:
            return False
        hhmm = now_ny.hour * 60 + now_ny.minute
        return (9 * 60 + 30) <= hhmm < (16 * 60)


def list_open_limit_orders(*args, **kwargs):
    return _bo().list_open_limit_orders(*args, **kwargs)


def list_open_limit_orders_by_strategy(*args, **kwargs):
    return _bo().list_open_limit_orders_by_strategy(*args, **kwargs)


def merge_position_queue(*args, **kwargs):
    return _cp().merge_position_queue(*args, **kwargs)


def print_market_order_closed_warning(*args, **kwargs):
    if len(args) < 4:
        return None
    _, symbol, side, qty = args[:4]
    stage = kwargs.get("stage", "submit")
    print(
        "⚠️ ",
        f"Market closed; using limit fallback stage={stage} symbol={symbol} side={categorize_order_status(side)} qty={float(qty or 0.0):.4f}",
    )
    return None


def queue_avg_entry_price(*args, **kwargs):
    return _cp().queue_avg_entry_price(*args, **kwargs)


def rebuild_limit_price_from_live_inputs(*args, **kwargs):
    if len(args) < 3:
        return None

    driver, symbol, side = args[0], args[1], args[2]
    symbol_key = str(symbol or "").strip().upper()
    side_text = categorize_order_status(side)
    if side_text not in {"buy", "sell"}:
        return None

    hint = {}
    latest_hints = getattr(driver, "latest_execution_hints", None)
    if isinstance(latest_hints, dict):
        hint = latest_hints.get(symbol_key, {}) if isinstance(latest_hints.get(symbol_key, {}), dict) else {}

    latest_price = None
    latest_prices = getattr(driver, "latest_symbol_prices", None)
    if isinstance(latest_prices, dict):
        latest_price = latest_prices.get(symbol_key)

    market_price = float((hint or {}).get("price", latest_price or 0.0) or 0.0)
    if market_price <= 0.0:
        return None

    strategy_params = getattr(driver, "strategy_params", {})
    limit_spread = float(strategy_params.get("limit_spread", 1.0) or 1.0) if isinstance(strategy_params, dict) else 1.0
    volatility = float(
        (hint or {}).get("volatility", (hint or {}).get("return_vol", 0.0)) or 0.0
    )
    return float(_bo().compute_limit_price(side_text, market_price, volatility, limit_spread))


def refresh_broker_state(*args, **kwargs):
    return _bo().refresh_broker_state(*args, **kwargs)


def resolve_order_preference(*args, **kwargs):
    if len(args) < 3:
        return "market", None

    driver, symbol, side = args[0], args[1], args[2]
    use_limit = bool(getattr(driver, "strategy_params", {}).get("use_limit", False))
    if is_market_open_now(driver) and not use_limit:
        return "market", None

    limit_price = rebuild_limit_price_from_live_inputs(driver, symbol, side)
    if limit_price is None:
        return "market", None

    constrained = enforce_limit_spacing(driver, symbol, side, limit_price)
    return "limit", float(constrained)


def signed_queue_to_qty(*args, **kwargs):
    return _cp().signed_queue_to_qty(*args, **kwargs)


def signed_queue_unrealized_components(*args, **kwargs):
    return _cp().signed_queue_unrealized_components(*args, **kwargs)


def signed_qty_from_alpaca_position(*args, **kwargs):
    return _cp().signed_qty_from_alpaca_position(*args, **kwargs)


def submit_order(*args, **kwargs):
    if len(args) < 5:
        return ""

    driver, symbol, side, qty, order_type = args[0], args[1], args[2], args[3], args[4]
    limit_price = args[5] if len(args) > 5 else kwargs.get("limit_price")

    symbol_key = str(symbol or "").strip().upper()
    order_kind = str(order_type or "").strip().lower() or "market"
    qty_value = abs(float(qty or 0.0))
    if qty_value <= 0.0:
        return ""

    trading_client = getattr(driver, "trading_client", None)
    alpaca_api = getattr(driver, "alpaca_api", None)
    if trading_client is None or alpaca_api is None:
        return ""

    side_value = side
    side_text = categorize_order_status(side)
    if not isinstance(side, OrderSide):
        side_value = OrderSide.BUY if side_text == "buy" else OrderSide.SELL

    try:
        response = alpaca_api.submit_order(symbol_key, qty_value, side_value, order_kind, limit_price)
    except Exception as exc:
        print("❌ ", f"Order submit failed symbol={symbol_key} side={side_text} qty={qty_value:.4f}: {exc}")
        return ""

    rejection_payload = getattr(alpaca_api, "last_submit_rejection", None)
    if isinstance(rejection_payload, dict):
        normalized = dict(rejection_payload)
        normalized_side = categorize_order_status(normalized.get("side") or side_text)
        normalized["side"] = normalized_side
        normalized["symbol"] = str(normalized.get("symbol") or symbol_key).upper()
        setattr(driver, "_last_submit_rejection", normalized)
    else:
        setattr(driver, "_last_submit_rejection", None)

    order_id = str(getattr(response, "id", "") or "").strip() if response is not None else ""
    if not order_id:
        return ""

    setattr(driver, "_last_submit_rejection", None)

    session_ids = getattr(driver, "_session_submitted_order_ids", None)
    if isinstance(session_ids, set):
        session_ids.add(order_id)

    submitted_map = getattr(driver, "_submitted_order_ids_by_symbol", None)
    if isinstance(submitted_map, dict):
        submitted_map.setdefault(symbol_key, set()).add(order_id)

    filled_accounted_map = getattr(driver, "_filled_qty_accounted_by_order_id", None)
    if isinstance(filled_accounted_map, dict):
        filled_accounted_map.pop(order_id, None)

    ingest_update = getattr(driver, "_ingest_broker_order_update", None)
    if callable(ingest_update):
        ingest_update(response, apply_fill_updates=False)

    return order_id


def apply_confirmed_fill_to_working_balance(*args, **kwargs):
    if len(args) < 2:
        return 0.0

    driver, order = args[0], args[1]
    if isinstance(order, dict):
        symbol = str(order.get("symbol", "") or order.get("broker_symbol", "") or "").strip().upper()
        side = _canonical_fill_side(order.get("side") or order.get("broker_side") or "")
        if not side:
            side = _canonical_fill_side(
                order.get("position_intent")
                or order.get("position_side")
                or order.get("instruction")
                or ""
            )
        status_text = categorize_order_status(order.get("status") or order.get("order_status"))
        event_text = categorize_order_status(order.get("event"))
        event_qty_raw = order.get("event_qty", None)
        filled_qty_raw = order.get("filled_qty", None)
        if filled_qty_raw in (None, ""):
            filled_qty_raw = order.get("filled_quantity", None)
        if filled_qty_raw in (None, ""):
            filled_qty_raw = order.get("qty_filled", None)
        if filled_qty_raw in (None, ""):
            filled_qty_raw = order.get("last_fill_qty", None)
        if filled_qty_raw in (None, ""):
            filled_qty_raw = order.get("last_filled_qty", None)
        if filled_qty_raw in (None, ""):
            filled_qty_raw = order.get("cum_qty", None)
        has_cumulative_filled_qty = filled_qty_raw not in (None, "")
        if not has_cumulative_filled_qty:
            filled_qty_raw = event_qty_raw

        # Use order average fill price for queue/PnL accounting consistency.
        fill_price_raw = order.get("filled_avg_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = order.get("avg_fill_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = order.get("avg_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = order.get("event_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = order.get("fill_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = order.get("last_fill_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = order.get("execution_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = order.get("price", order.get("limit_price", 0.0))
        order_id = str(
            order.get("id", "")
            or order.get("order_id", "")
            or order.get("client_order_id", "")
            or ""
        ).strip()
        execution_id = str(order.get("execution_id", "") or order.get("event_id", "") or "").strip()
    else:
        symbol = str(getattr(order, "symbol", "") or "").strip().upper()
        side = _canonical_fill_side(getattr(order, "side", ""))
        if not side:
            side = _canonical_fill_side(
                getattr(order, "position_intent", None)
                or getattr(order, "position_side", None)
                or getattr(order, "instruction", None)
                or ""
            )
        status_text = categorize_order_status(
            getattr(order, "status", None) or getattr(order, "order_status", None)
        )
        event_text = categorize_order_status(getattr(order, "event", None))
        event_qty_raw = getattr(order, "event_qty", None)
        filled_qty_raw = getattr(order, "filled_qty", None)
        if filled_qty_raw in (None, ""):
            filled_qty_raw = getattr(order, "filled_quantity", None)
        if filled_qty_raw in (None, ""):
            filled_qty_raw = getattr(order, "qty_filled", None)
        if filled_qty_raw in (None, ""):
            filled_qty_raw = getattr(order, "last_fill_qty", None)
        if filled_qty_raw in (None, ""):
            filled_qty_raw = getattr(order, "last_filled_qty", None)
        if filled_qty_raw in (None, ""):
            filled_qty_raw = getattr(order, "cum_qty", None)
        has_cumulative_filled_qty = filled_qty_raw not in (None, "")
        if not has_cumulative_filled_qty:
            filled_qty_raw = event_qty_raw

        # Use order average fill price for queue/PnL accounting consistency.
        fill_price_raw = getattr(order, "filled_avg_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = getattr(order, "avg_fill_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = getattr(order, "avg_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = getattr(order, "event_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = getattr(order, "fill_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = getattr(order, "last_fill_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = getattr(order, "execution_price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = getattr(order, "price", None)
        if fill_price_raw in (None, ""):
            fill_price_raw = getattr(order, "limit_price", 0.0)
        order_id = str(
            getattr(order, "id", "")
            or getattr(order, "order_id", "")
            or getattr(order, "client_order_id", "")
            or ""
        ).strip()
        execution_id = str(getattr(order, "execution_id", "") or getattr(order, "event_id", "") or "").strip()

    if not symbol:
        return 0.0

    if side not in {"buy", "sell"}:
        return 0.0

    if not order_id:
        # Fill accounting and dedupe are order-id scoped.
        return 0.0

    is_fill_progress = status_in_group(status_text, "fill_progress") or event_in_group(event_text, "fill_progress")
    if not is_fill_progress:
        return 0.0

    try:
        filled_qty = abs(float(filled_qty_raw or 0.0))
    except Exception:
        filled_qty = 0.0
    if filled_qty <= 0.0:
        return 0.0

    processed_execution_ids = getattr(driver, "_processed_session_fill_confirmations", None)
    if not isinstance(processed_execution_ids, set):
        processed_execution_ids = set()
        setattr(driver, "_processed_session_fill_confirmations", processed_execution_ids)
    if execution_id and execution_id in processed_execution_ids:
        return 0.0

    accounted_map = getattr(driver, "_filled_qty_accounted_by_order_id", None)
    if not isinstance(accounted_map, dict):
        accounted_map = {}
        setattr(driver, "_filled_qty_accounted_by_order_id", accounted_map)

    if has_cumulative_filled_qty:
        already_accounted = float(accounted_map.get(order_id, 0.0) or 0.0)
        newly_filled_qty = max(0.0, float(filled_qty) - float(already_accounted))
    else:
        newly_filled_qty = float(filled_qty)
    if newly_filled_qty <= 0.0:
        return 0.0
    if has_cumulative_filled_qty:
        accounted_map[order_id] = float(filled_qty)
    if execution_id:
        processed_execution_ids.add(execution_id)

    if isinstance(order, dict):
        confirmed_fill_price_raw = next(
            (
                order.get(field_name)
                for field_name in (
                    "event_price",
                    "fill_price",
                    "last_fill_price",
                    "execution_price",
                    "filled_avg_price",
                    "avg_fill_price",
                    "avg_price",
                )
                if order.get(field_name) not in (None, "")
            ),
            None,
        )
    else:
        confirmed_fill_price_raw = next(
            (
                getattr(order, field_name, None)
                for field_name in (
                    "event_price",
                    "fill_price",
                    "last_fill_price",
                    "execution_price",
                    "filled_avg_price",
                    "avg_fill_price",
                    "avg_price",
                )
                if getattr(order, field_name, None) not in (None, "")
            ),
            None,
        )

    try:
        fill_price = abs(float(fill_price_raw or 0.0))
    except Exception:
        fill_price = 0.0
    try:
        confirmed_fill_price = abs(float(confirmed_fill_price_raw or 0.0))
    except Exception:
        confirmed_fill_price = 0.0
    if fill_price <= 0.0:
        latest_prices = getattr(driver, "latest_symbol_prices", None)
        if isinstance(latest_prices, dict):
            try:
                fill_price = abs(float(latest_prices.get(symbol, 0.0) or 0.0))
            except Exception:
                fill_price = 0.0

    record_fill_price = getattr(driver, "_record_confirmed_fill_price", None)
    if confirmed_fill_price > 0.0 and callable(record_fill_price):
        record_fill_price(
            symbol,
            side,
            confirmed_fill_price,
            float(newly_filled_qty),
            order,
        )

    if fill_price <= 0.0:
        local_queue_map = getattr(driver, "_position_queue", None)
        if isinstance(local_queue_map, dict):
            existing_queue = local_queue_map.get(symbol, [])
            if isinstance(existing_queue, list) and existing_queue:
                try:
                    fill_price = abs(float(existing_queue[-1] or 0.0))
                except Exception:
                    fill_price = 0.0
    if fill_price <= 0.0:
        # Preserve position-qty correctness when broker omits fill price fields.
        fill_price = 1.0

    if fill_price > 0.0:
        local_queue_map = getattr(driver, "_position_queue", None)
        if isinstance(local_queue_map, dict):
            prior_queue = local_queue_map.get(symbol, [])
            if not isinstance(prior_queue, list):
                prior_queue = []
            updated_queue, realized_delta = _cp().match_fill_lifo(
                prior_queue,
                side=side,
                fill_price=float(fill_price),
                fill_qty=int(round(float(newly_filled_qty))),
            )
            local_queue_map[symbol] = list(updated_queue)

            realized_by_symbol = getattr(driver, "_local_realized_pnl_by_symbol", None)
            if not isinstance(realized_by_symbol, dict):
                realized_by_symbol = {}
                setattr(driver, "_local_realized_pnl_by_symbol", realized_by_symbol)
            prior_symbol_realized = float(realized_by_symbol.get(symbol, 0.0) or 0.0)
            realized_by_symbol[symbol] = float(prior_symbol_realized + float(realized_delta))

            required_symbols = set(getattr(driver, "required_symbols", set()) or set())
            if required_symbols:
                realized_total = float(
                    sum(
                        float(realized_by_symbol.get(symbol_key, 0.0) or 0.0)
                        for symbol_key in sorted(required_symbols)
                    )
                )
            else:
                realized_total = float(sum(float(value or 0.0) for value in realized_by_symbol.values()))
            setattr(driver, "_local_realized_pnl_total", float(realized_total))

    signed_fill = newly_filled_qty if side == "buy" else -newly_filled_qty
    working_map = getattr(driver, "_working_balance_by_symbol", None)
    if isinstance(working_map, dict):
        current = float(working_map.get(symbol, 0.0) or 0.0)
        updated = current - signed_fill
        if abs(updated) <= 1e-9:
            updated = 0.0
        working_map[symbol] = float(updated)

    return float(signed_fill)


def update_position_records_from_snapshot(*args, **kwargs):
    return _cp().update_position_records_from_snapshot(*args, **kwargs)


async def wait_for_fill(*args, **kwargs):
    if len(args) < 2:
        return False

    driver, order_id = args[0], str(args[1] or "").strip()
    if not order_id:
        return False

    timeout_seconds = float(getattr(driver, "order_fill_timeout", 30.0) or 30.0)
    deadline = datetime.now(NY_TZ).timestamp() + max(0.1, timeout_seconds)
    update_events = getattr(driver, "_broker_order_update_events_by_id", None)
    latest_update_getter = getattr(driver, "_latest_broker_order_update", None)

    while datetime.now(NY_TZ).timestamp() <= deadline:
        order = latest_update_getter(order_id) if callable(latest_update_getter) else None
        if isinstance(order, dict):
            status = categorize_order_status(order.get("status") or order.get("event") or order.get("order_status"))
            if status in FILLED_ORDER_STATUSES:
                return True
            if status in TERMINAL_ORDER_STATUSES:
                return False

        remaining = max(0.0, deadline - datetime.now(NY_TZ).timestamp())
        if remaining <= 0.0:
            break
        event_obj = None
        if isinstance(update_events, dict):
            event_obj = update_events.get(order_id)
            if event_obj is None:
                event_obj = asyncio.Event()
                update_events[order_id] = event_obj
        if event_obj is None:
            await asyncio.sleep(0.05)
            continue
        try:
            await asyncio.wait_for(event_obj.wait(), timeout=remaining)
        except asyncio.TimeoutError:
            break
        finally:
            if event_obj.is_set():
                event_obj.clear()

    return False


def clear_pending_trade_gates(*args, **kwargs):
    return _bo().clear_pending_trade_gates(*args, **kwargs)


__all__ = [
    "cancel_all_limit_orders",
    "cancel_opposite_limit_orders",
    "wait_for_opposite_limit_cancellations",
    "categorize_order_status",
    "compare_position_records_with_alpaca",
    "compute_positions_from_local_signed_queue",
    "compute_realized_pnl_from_local_signed_queue",
    "compute_unrealized_pnl_from_local_signed_queue",
    "count_open_limit_orders",
    "enforce_limit_spacing",
    "is_market_open_now",
    "list_open_limit_orders",
    "list_open_limit_orders_by_strategy",
    "merge_position_queue",
    "print_market_order_closed_warning",
    "queue_avg_entry_price",
    "rebuild_limit_price_from_live_inputs",
    "refresh_broker_state",
    "resolve_order_preference",
    "signed_queue_to_qty",
    "signed_queue_unrealized_components",
    "signed_qty_from_alpaca_position",
    "submit_order",
    "apply_confirmed_fill_to_working_balance",
    "update_position_records_from_snapshot",
    "wait_for_fill",
    "clear_pending_trade_gates",
]
