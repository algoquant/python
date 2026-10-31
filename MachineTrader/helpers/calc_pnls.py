from __future__ import annotations

from typing import Any


def normalize_signed_price_queue(raw_queue: Any) -> list[float]:
    """Normalize legacy queue representations to signed-price queue format.

    Canonical queue convention:
    - Long lot -> negative entry price
    - Short lot -> positive entry price
    """
    normalized: list[float] = []
    for entry in list(raw_queue or []):
        if isinstance(entry, (int, float)):
            normalized.append(float(entry))
            continue
        if not isinstance(entry, dict):
            continue
        try:
            entry_qty = int(round(abs(float(entry.get("qty", 0.0) or 0.0))))
            entry_price = abs(float(entry.get("price", 0.0) or 0.0))
        except (TypeError, ValueError):
            continue
        if entry_qty <= 0 or entry_price <= 0.0:
            continue
        entry_side = str(entry.get("side", "") or "").strip().lower()
        side_token = entry_side.replace("-", "_").replace(" ", "_")

        if side_token in {"buy", "long", "buy_to_open", "buy_to_cover", "btc", "b"} or "buy" in side_token:
            signed_entry_price = -entry_price
        elif side_token in {"sell", "short", "sell_short", "sell_to_open", "sto", "s"} or "sell" in side_token:
            signed_entry_price = entry_price
        else:
            # Unknown legacy side text: skip instead of assuming short.
            continue
        normalized.extend([float(signed_entry_price)] * entry_qty)
    return normalized


def signed_queue_unrealized_components(queue: list[float], current_price: float) -> list[float]:
    components: list[float] = []
    px = float(current_price)
    for value in queue:
        entry = float(value)
        if entry < 0.0:
            components.append(entry + px)
        elif entry > 0.0:
            components.append(entry - px)
    return components


def merge_position_queue(driver) -> dict[str, list[float]]:
    merged_by_symbol: dict[str, list[float]] = {}
    source = getattr(driver, "_position_queue", {})
    if not isinstance(source, dict):
        return merged_by_symbol
    for symbol_key, raw_queue in source.items():
        normalized_symbol = str(symbol_key or "").strip().upper()
        if not normalized_symbol or not isinstance(raw_queue, list):
            continue
        merged_by_symbol[normalized_symbol] = [float(v) for v in raw_queue]
    return merged_by_symbol


def queue_avg_entry_price(queue: list[float]) -> float:
    if not queue:
        return 0.0
    return float(sum(abs(float(v)) for v in queue) / len(queue))


def compute_unrealized_pnl_from_local_signed_queue(driver, local_queue_by_symbol: dict[str, list[float]] | None = None) -> tuple[dict[str, float], float]:
    merged_by_symbol = local_queue_by_symbol if isinstance(local_queue_by_symbol, dict) else merge_position_queue(driver)
    unrealized_by_symbol: dict[str, float] = {}
    total_unrealized = 0.0
    for symbol_key in driver.required_symbols:
        queue = merged_by_symbol.get(symbol_key, [])
        current_price = float(driver.latest_symbol_prices.get(symbol_key, 0.0) or 0.0)
        unrealized = float(unrealized_pnl_from_signed_queue(queue, current_price if current_price > 0.0 else None))
        unrealized_by_symbol[symbol_key] = unrealized
        total_unrealized += unrealized
    return unrealized_by_symbol, float(total_unrealized)


def compute_positions_from_local_signed_queue(driver, local_queue_by_symbol: dict[str, list[float]] | None = None, unrealized_by_symbol: dict[str, float] | None = None) -> dict[str, dict[str, Any]]:
    merged_by_symbol = local_queue_by_symbol if isinstance(local_queue_by_symbol, dict) else merge_position_queue(driver)
    unrealized_map = unrealized_by_symbol if isinstance(unrealized_by_symbol, dict) else {}
    positions: dict[str, dict[str, Any]] = {}
    for symbol_key in driver.required_symbols:
        queue = merged_by_symbol.get(symbol_key, [])
        qty = queue_symbol_position_shares(
            merged_by_symbol,
            symbol=symbol_key,
            signed_queue_to_qty=signed_queue_to_qty,
        )
        current_price = float(driver.latest_symbol_prices.get(symbol_key, 0.0) or 0.0)
        avg_entry_price = queue_avg_entry_price(queue)
        last_entry_price = float(queue[-1]) if queue else 0.0
        unrealized = float(unrealized_map.get(symbol_key, unrealized_pnl_from_signed_queue(queue, current_price if current_price > 0.0 else None)) or 0.0)
        pnl_per_share = (unrealized / abs(float(qty))) if abs(float(qty)) > 0.0 else 0.0
        lot_unrealized_components = signed_queue_unrealized_components(queue, current_price) if current_price > 0.0 else []
        largest_unrealized_position_pnl = max(lot_unrealized_components) if lot_unrealized_components else 0.0
        best_lot_close_delta = -1.0 if qty > 0 else 1.0 if qty < 0 else 0.0
        if lot_unrealized_components and len(queue) == len(lot_unrealized_components):
            best_idx = max(range(len(lot_unrealized_components)), key=lambda idx: lot_unrealized_components[idx])
            best_entry = float(queue[best_idx])
            if best_entry < 0.0:
                best_lot_close_delta = -1.0
            elif best_entry > 0.0:
                best_lot_close_delta = 1.0
        positions[symbol_key] = {
            "qty": qty,
            "unrealized_pl": unrealized,
            "pnl_per_share": float(pnl_per_share),
            "position_queue_prices": [float(value) for value in queue],
            "unrealized_position_pnls": [float(value) for value in lot_unrealized_components],
            "largest_unrealized_position_pnl": float(largest_unrealized_position_pnl),
            "best_lot_close_delta": float(best_lot_close_delta),
            "trade_price": current_price,
            "avg_entry_price": avg_entry_price,
            "last_entry_price": last_entry_price,
            "market_value": current_price * qty,
        }
    return positions


def signed_qty_from_alpaca_position(pos: Any) -> float:
    qty_raw = float(getattr(pos, "qty", 0.0) or 0.0)
    qty_abs = abs(qty_raw)
    side_text = str(getattr(pos, "side", "") or "").strip().lower()
    if side_text.endswith("short") or side_text == "sell":
        return -qty_abs
    if side_text.endswith("long") or side_text == "buy":
        return qty_abs
    return qty_raw


def update_position_records_from_snapshot(driver, positions: dict[str, dict[str, Any]]):
    open_positions: dict[str, float] = {}
    for symbol in driver.required_symbols:
        qty = float(positions.get(symbol, {}).get("qty", 0.0) or 0.0)
        if abs(qty) > 1e-9:
            open_positions[symbol] = qty
    driver._position_record_open = open_positions
    driver._position_record_closed = set(driver.required_symbols) - set(open_positions.keys())


def compare_position_records_with_alpaca(driver):
    try:
        broker_positions_raw = driver.trading_client.get_all_positions()
    except Exception:
        return
    broker_open: dict[str, float] = {}
    for pos in broker_positions_raw:
        symbol_key = str(getattr(pos, "symbol", "") or "").strip().upper()
        if not symbol_key or symbol_key not in driver.required_symbols:
            continue
        signed_qty = float(signed_qty_from_alpaca_position(pos))
        if abs(signed_qty) > 1e-9:
            broker_open[symbol_key] = signed_qty

    local_queue_map = merge_position_queue(driver)
    local_open: dict[str, float] = {}
    for symbol_key in sorted(driver.required_symbols):
        queue = local_queue_map.get(symbol_key, [])
        local_qty = float(signed_queue_to_qty(queue)) if isinstance(queue, list) else 0.0
        if abs(local_qty) > 1e-9:
            local_open[symbol_key] = local_qty
    for symbol in sorted(driver.required_symbols):
        local_qty = float(local_open.get(symbol, 0.0) or 0.0)
        broker_qty = float(broker_open.get(symbol, 0.0) or 0.0)
        if abs(local_qty - broker_qty) <= 1e-6:
            continue
        print(
            "⚠️ ",
            (
                f"Position mismatch symbol={symbol} local_qty={local_qty:.4f} alpaca_qty={broker_qty:.4f}. "
                "Local position queue remains the source of truth."
            ),
        )


def compute_realized_pnl_from_local_signed_queue(driver) -> float:
    # Single source of truth: sum per-symbol realized ledger values.
    realized_by_symbol = getattr(driver, "_local_realized_pnl_by_symbol", None)
    if not isinstance(realized_by_symbol, dict):
        realized_by_symbol = {}
    required_symbols = set(getattr(driver, "required_symbols", set()) or set())
    if required_symbols:
        total = float(
            sum(
                float(realized_by_symbol.get(symbol_key, 0.0) or 0.0)
                for symbol_key in sorted(required_symbols)
            )
        )
    else:
        total = float(sum(float(value or 0.0) for value in realized_by_symbol.values()))
    setattr(driver, "_local_realized_pnl_total", float(total))
    return float(total)


def derive_pair_qty_from_leg_qtys(pair, qty1: float, qty2: float) -> float:
    units_from_leg1 = float(qty1) / float(pair.quantity1) if float(pair.quantity1) else 0.0
    units_from_leg2 = -float(qty2) / float(pair.quantity2) if float(pair.quantity2) else 0.0
    if abs(units_from_leg1) > 0.0 and abs(units_from_leg2) > 0.0:
        if units_from_leg1 * units_from_leg2 >= 0.0:
            return float(0.5 * (units_from_leg1 + units_from_leg2))
        return 0.0
    if abs(units_from_leg1) > 0.0:
        return float(units_from_leg1)
    return float(units_from_leg2)


def derive_pair_position(pair, leg1: dict[str, Any], leg2: dict[str, Any], pair_price: float, pair_queue_prices: list[float] | None = None) -> dict[str, Any]:
    qty1 = float(leg1.get("qty", 0.0) or 0.0)
    qty2 = float(leg2.get("qty", 0.0) or 0.0)
    pair_qty = derive_pair_qty_from_leg_qtys(pair, qty1, qty2)
    unrealized_pl = float(leg1.get("unrealized_pl", 0.0) or 0.0) + float(leg2.get("unrealized_pl", 0.0) or 0.0)
    pnl_per_share = (unrealized_pl / abs(pair_qty)) if abs(pair_qty) > 0.0 else 0.0
    best_lot_close_delta = -1.0 if pair_qty > 0 else 1.0 if pair_qty < 0 else 0.0
    queue_prices = [float(value) for value in pair_queue_prices] if isinstance(pair_queue_prices, list) else []
    last_entry_price = float(queue_prices[-1]) if queue_prices else 0.0
    return {
        "qty": float(pair_qty),
        "unrealized_pl": float(unrealized_pl),
        "pnl_per_share": float(pnl_per_share),
        "position_queue_prices": queue_prices,
        "unrealized_position_pnls": [],
        "largest_unrealized_position_pnl": 0.0,
        "best_lot_close_delta": float(best_lot_close_delta),
        "trade_price": float(pair_price),
        "avg_entry_price": float(last_entry_price),
        "last_entry_price": float(last_entry_price),
        "market_value": float(pair_price * pair_qty),
    }


def signed_queue_to_qty(price_queue: list[float] | None) -> float:
    """Convert signed-price queue into net share count."""
    queue = price_queue or []
    if not queue:
        return 0.0
    positive = sum(1.0 for price in queue if float(price) > 0.0)
    negative = sum(1.0 for price in queue if float(price) < 0.0)
    # Queue convention: buys are stored as negative prices, sells as positive.
    # Expose net position in trading sign convention: long positive, short negative.
    return float(negative - positive)


def unrealized_pnl_from_signed_queue(price_queue: list[float] | None, last_price: float | None) -> float:
    """Compute unrealized PnL from local signed-price queue and current price."""
    if last_price is None:
        return 0.0
    queue = price_queue or []
    px = float(last_price)
    total = 0.0
    for entry in queue:
        p = float(entry)
        if p < 0.0:
            total += px + p
        elif p > 0.0:
            total += p - px
    return float(total)


def match_fill_lifo(
    price_queue: list[float] | None,
    *,
    side: str,
    fill_price: float,
    fill_qty: int,
) -> tuple[list[float], float]:
    """Apply a fill to signed queue (LIFO), returning updated queue and realized PnL delta."""
    queue = list(price_queue or [])
    realized = 0.0
    is_buy = "buy" in str(side or "").strip().lower()
    signed_fill = -abs(float(fill_price)) if is_buy else abs(float(fill_price))
    remaining = max(0, int(fill_qty))

    while remaining > 0 and queue:
        last = float(queue[-1])
        same_direction = (last < 0.0 and signed_fill < 0.0) or (last > 0.0 and signed_fill > 0.0)
        if same_direction:
            break
        realized += last + signed_fill
        queue.pop()
        remaining -= 1

    while remaining > 0:
        queue.append(signed_fill)
        remaining -= 1

    return queue, float(realized)


def enforce_notional_limit(
    requested_delta: float,
    *,
    last_price: float | None,
    max_notional: float | None,
) -> float:
    """Clamp share delta so order notional does not exceed max_notional."""
    if max_notional is None or last_price is None:
        return float(requested_delta)
    px = abs(float(last_price))
    if px <= 0.0:
        return float(requested_delta)
    max_shares = int(abs(float(max_notional)) // px)
    if max_shares <= 0:
        return 0.0
    req = float(requested_delta)
    sign = 1.0 if req >= 0.0 else -1.0
    return sign * float(min(abs(req), float(max_shares)))


def compute_symbol_unrealized_map(
    position_queues_by_symbol: dict[str, list[float]],
    latest_prices_by_symbol: dict[str, Any],
) -> dict[str, float]:
    """Compute per-symbol unrealized PnL from signed queues and latest prices."""
    result: dict[str, float] = {}
    for symbol in sorted(position_queues_by_symbol.keys()):
        last_price = latest_prices_by_symbol.get(symbol)
        try:
            last_price_num = float(last_price) if last_price is not None else None
        except (TypeError, ValueError):
            last_price_num = None
        result[symbol] = unrealized_pnl_from_signed_queue(position_queues_by_symbol.get(symbol, []), last_price_num)
    return result


def update_intraday_pnl_extremes_from_account(
    account_snapshot: dict[str, Any] | None,
    *,
    required_symbols: set[str],
    safe_float,
    daily_total_pnl_high: float | None,
    daily_total_pnl_low: float | None,
    daily_pnl_high_by_symbol: dict[str, float] | None,
    daily_pnl_low_by_symbol: dict[str, float] | None,
) -> tuple[float | None, float | None, dict[str, float], dict[str, float]]:
    """Update and return intraday strategy/symbol PnL high-low extremes."""
    snapshot = account_snapshot if isinstance(account_snapshot, dict) else {}
    pnl_by_symbol = snapshot.get("unrealized_pnl_by_symbol", {})
    if not isinstance(pnl_by_symbol, dict):
        pnl_by_symbol = {}

    high_total = daily_total_pnl_high
    low_total = daily_total_pnl_low
    high_by_symbol = dict(daily_pnl_high_by_symbol or {})
    low_by_symbol = dict(daily_pnl_low_by_symbol or {})

    realized_local_total = safe_float(snapshot.get("realized_pnl_local"), default=0.0)
    total_unrealized_local = safe_float(
        snapshot.get("unrealized_pnl_total"),
        default=sum(safe_float(value, default=0.0) for value in pnl_by_symbol.values()),
    )
    total_pnl_value = realized_local_total + total_unrealized_local

    if high_total is None or total_pnl_value > float(high_total):
        high_total = total_pnl_value
    if low_total is None or total_pnl_value < float(low_total):
        low_total = total_pnl_value

    for symbol_key in sorted(required_symbols):
        unrealized_value = safe_float(pnl_by_symbol.get(symbol_key, 0.0), default=0.0)
        prior_high = high_by_symbol.get(symbol_key)
        prior_low = low_by_symbol.get(symbol_key)
        if prior_high is None or unrealized_value > float(prior_high):
            high_by_symbol[symbol_key] = unrealized_value
        if prior_low is None or unrealized_value < float(prior_low):
            low_by_symbol[symbol_key] = unrealized_value

    return high_total, low_total, high_by_symbol, low_by_symbol


def queue_symbol_position_shares(
    merged_local_queue: dict[str, list[float]] | None,
    *,
    symbol: str,
    signed_queue_to_qty,
) -> float:
    """Return net position shares for one symbol from signed local queues."""
    if not isinstance(merged_local_queue, dict) or not merged_local_queue:
        return 0.0

    queue = merged_local_queue.get(str(symbol), [])
    if not isinstance(queue, list) or not queue:
        return 0.0
    return float(signed_queue_to_qty(queue))


__all__ = [
    "normalize_signed_price_queue",
    "signed_queue_to_qty",
    "unrealized_pnl_from_signed_queue",
    "match_fill_lifo",
    "enforce_notional_limit",
    "compute_symbol_unrealized_map",
    "update_intraday_pnl_extremes_from_account",
    "queue_symbol_position_shares",
    "compare_position_records_with_alpaca",
    "compute_positions_from_local_signed_queue",
    "compute_realized_pnl_from_local_signed_queue",
    "compute_unrealized_pnl_from_local_signed_queue",
    "merge_position_queue",
    "queue_avg_entry_price",
    "signed_qty_from_alpaca_position",
    "signed_queue_unrealized_components",
    "update_position_records_from_snapshot",
    "derive_pair_position",
    "derive_pair_qty_from_leg_qtys",
]
