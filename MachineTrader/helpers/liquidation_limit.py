from __future__ import annotations

import asyncio
import os
import threading
import time
from types import SimpleNamespace
from typing import Any, Callable

from alpaca.data.enums import DataFeed
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, LimitOrderRequest
from MachineTrader.helpers.alpacasdk import AlpacAPI
from MachineTrader.helpers.broker_orders import (
    cancel_conflicting_opposite_orders,
    compute_limit_price,
    enum_text,
    is_terminal_order_status,
    parse_submit_rejection,
    resolve_insufficient_qty_retry,
)
from MachineTrader.helpers.file_handlers import (
    build_trade_blotter_owner,
    clear_persisted_position_queues,
    record_broker_order_update,
    record_trade_cancel_request,
    record_trade_submission,
)
from MachineTrader.helpers.live_data import (
    event_close,
    event_datetime_ny,
    event_symbol,
    is_bar_event,
    latest_alpaca_market_data_with_feed_fallback,
    resolve_data_proxy_url,
    stream_proxy_events,
)
from MachineTrader.helpers.setup_strat import read_env_file_if_changed

PROXY_INITIAL_SNAPSHOT_TIMEOUT_SECONDS = 65.0


def _resolve_limit_spread(limit_spread: float | None, env_values: dict[str, Any]) -> float:
    raw_value = (
        limit_spread
        if limit_spread is not None
        else env_values.get(
            "STRATEGY_LIMIT_SPREAD",
            env_values.get("LIMIT_SPREAD", os.getenv("STRATEGY_LIMIT_SPREAD", "0.5")),
        )
    )
    try:
        return max(0.0, float(raw_value))
    except (TypeError, ValueError):
        return 0.5


def _wait_for_proxy_snapshot(
    symbols: list[str],
    snapshot_fn: Callable[[list[str]], dict[str, dict[str, Any]]],
    *,
    timeout_seconds: float,
    poll_seconds: float,
) -> dict[str, dict[str, Any]]:
    deadline = time.monotonic() + max(0.0, float(timeout_seconds))
    snapshot = snapshot_fn(symbols)
    while set(snapshot) < set(symbols):
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            break
        time.sleep(min(max(0.05, float(poll_seconds)), remaining))
        snapshot = snapshot_fn(symbols)
    return snapshot


def _fetch_alpaca_fallback_data(
    symbols: list[str],
    *,
    env_file: str,
    alpaca_sdk: AlpacAPI,
    data_client: Any | None,
    print_fn,
):
    if not symbols:
        return data_client, None, None, {}, {}

    if data_client is None:
        alpaca_sdk.create_data_client(
            env_file=env_file,
            DATA_KEY="ALPACA_DATA_KEY",
            DATA_SECRET="ALPACA_DATA_SECRET",
        )
        data_client = alpaca_sdk.get_data_client()

    data_feed, latest_bar_req, latest_bars, latest_quotes = latest_alpaca_market_data_with_feed_fallback(
        data_client=data_client,
        symbols=symbols,
        print_fn=print_fn,
    )
    return data_client, data_feed, latest_bar_req, latest_bars, latest_quotes


def _cancel_submitted_orders(
    *,
    trading_client,
    order_ids: list[str],
    blotter_owner,
    iteration: int,
    print_fn,
) -> None:
    print_fn("🔄 ", f"Cancelling prior submitted limit orders count={len(order_ids)}")
    for order_id in list(order_ids):
        try:
            order_snapshot = trading_client.get_order_by_id(order_id)
        except Exception:
            order_snapshot = None

        status_text = enum_text(getattr(order_snapshot, "status", "")) if order_snapshot is not None else ""
        if is_terminal_order_status(status_text):
            print_fn("ℹ️ ", f"Skipping cancel for order id={order_id}; status={status_text}.")
            if order_snapshot is not None:
                try:
                    record_broker_order_update(blotter_owner, order_snapshot)
                except Exception:
                    pass
            continue

        if order_snapshot is not None:
            record_trade_cancel_request(
                blotter_owner,
                symbol=str(getattr(order_snapshot, "symbol", "") or "").upper(),
                qty=float(getattr(order_snapshot, "qty", 0.0) or 0.0),
                order_type=str(getattr(order_snapshot, "type", "") or "limit"),
                price=float(getattr(order_snapshot, "limit_price", 0.0) or 0.0),
                message=f"cancel before reprice iteration={iteration}",
                order=order_snapshot,
                misc=f"iteration={iteration}",
            )

        try:
            trading_client.cancel_order_by_id(order_id)
        except Exception as exc:
            print_fn("⚠️ ", f"Failed to cancel prior submitted order id={order_id}: {exc}")

        try:
            updated_order = trading_client.get_order_by_id(order_id)
            record_broker_order_update(blotter_owner, updated_order)
        except Exception:
            pass


def _cancel_open_limit_orders(
    *,
    trading_client,
    symbols_for_quotes: list[str],
    blotter_owner,
    iteration: int,
    print_fn,
) -> None:
    try:
        open_filter = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        open_orders = trading_client.get_orders(filter=open_filter)
    except Exception as exc:
        open_orders = []
        print_fn("⚠️ ", f"Unable to list open orders before liquidation: {exc}")

    symbol_set = {str(symbol).strip().upper() for symbol in symbols_for_quotes if str(symbol).strip()}
    canceled_limit_count = 0
    for order in open_orders:
        order_symbol = str(getattr(order, "symbol", "") or "").strip().upper()
        if order_symbol not in symbol_set:
            continue

        order_type = enum_text(getattr(order, "type", ""))
        if order_type != "limit":
            continue

        order_id = str(getattr(order, "id", "") or "").strip()
        if not order_id:
            continue

        record_trade_cancel_request(
            blotter_owner,
            symbol=order_symbol,
            qty=float(getattr(order, "qty", 0.0) or 0.0),
            order_type=str(getattr(order, "type", "") or "limit"),
            price=float(getattr(order, "limit_price", 0.0) or 0.0),
            message=f"cancel stale open limit before liquidation iteration={iteration}",
            order=order,
            misc=f"iteration={iteration}",
        )

        try:
            latest_order = trading_client.get_order_by_id(order_id)
        except Exception:
            latest_order = None

        latest_status_text = enum_text(getattr(latest_order, "status", "")) if latest_order is not None else ""
        if is_terminal_order_status(latest_status_text):
            print_fn("ℹ️ ", f"Skipping cancel for order id={order_id}; status={latest_status_text}.")
            if latest_order is not None:
                try:
                    record_broker_order_update(blotter_owner, latest_order)
                except Exception:
                    pass
            continue

        try:
            trading_client.cancel_order_by_id(order_id)
            canceled_limit_count += 1
            print_fn("🧹 ", f"Canceled open limit order id={order_id} symbol={order_symbol}")
        except Exception as exc:
            print_fn("⚠️ ", f"Failed to cancel open limit order id={order_id} symbol={order_symbol}: {exc}")

        try:
            updated_order = trading_client.get_order_by_id(order_id)
            record_broker_order_update(blotter_owner, updated_order)
        except Exception:
            pass

    if canceled_limit_count > 0:
        print_fn("✅ ", f"Canceled {canceled_limit_count} open limit order(s) before liquidation submits.")
    else:
        print_fn("ℹ️ ", "No open limit orders to cancel before liquidation submits.")


def liquidate_positions_with_limit_loop(
    *,
    env_file: str,
    limit_spread: float | None = None,
    bar_poll_seconds: float = 1.0,
    data_proxy_url: str | None = None,
    symbols: list[str] | None = None,
    alpaca_sdk: AlpacAPI | None = None,
    trading_client: Any | None = None,
    data_client: Any | None = None,
    position_qty_provider: Callable[[], dict[str, float]] | None = None,
    on_order_submitted: Callable[[Any], None] | None = None,
    update_position_file_on_complete: bool = True,
    print_fn=print,
) -> dict[str, Any]:
    """Liquidate positions using limit orders and the shared live-data proxy.

    A persistent listener caches proxy bars. The first iteration waits up to
    ``PROXY_INITIAL_SNAPSHOT_TIMEOUT_SECONDS`` for a complete initial snapshot;
    any remaining symbols alone use Alpaca data fallback. Each submitted limit
    is canceled and repriced when the next source bar arrives. Persisted
    position queues are cleared only after broker positions confirm completion.
    """
    env_file_text = str(env_file or "").strip()
    loaded_env_values, env_file_signature = read_env_file_if_changed(env_file_text)
    env_values = loaded_env_values or {}

    env_data_proxy_url = str(env_values.get("DATA_PROXY_URL", "") or "").strip()
    resolved_data_proxy_url = resolve_data_proxy_url(data_proxy_url or env_data_proxy_url or None)
    resolved_limit_spread = _resolve_limit_spread(limit_spread, env_values)
    poll_seconds = max(0.2, float(bar_poll_seconds))

    strategy_name = str(env_values.get("STRATEGY_NAME", "") or "").strip() or "liquidate_positions"
    log_dir_name = str(env_values.get("LOG_DIR_NAME", "") or os.getenv("LOG_DIR_NAME", "") or "logs").strip()
    blotter_owner = build_trade_blotter_owner(
        strategy_name=strategy_name,
        log_dir_name=log_dir_name,
        blotter_suffix="blotterliquid",
    )

    if alpaca_sdk is None:
        alpaca_sdk = AlpacAPI()

    if trading_client is None:
        alpaca_sdk.create_trade_clients(
            env_file=env_file_text,
            TRADE_KEY="ALPACA_TRADE_KEY",
            TRADE_SECRET="ALPACA_TRADE_SECRET",
        )
        trading_client = alpaca_sdk.get_trading_client()

    symbol_filter = {str(symbol).strip().upper() for symbol in (symbols or []) if str(symbol).strip()}

    print_fn(
        "🧾 ",
        f"Liquidation parameters: symbols={sorted(symbol_filter) if symbol_filter else 'ALL'}, "
        f"limit_spread={resolved_limit_spread}, env_file={env_file_text}, data_proxy_url={resolved_data_proxy_url}",
    )

    submitted_order_ids: list[str] = []
    latest_proxy_bars: dict[str, dict[str, Any]] = {}
    proxy_bars_lock = threading.Lock()
    proxy_listener_stop: threading.Event | None = None
    proxy_listener_thread: threading.Thread | None = None
    initial_proxy_snapshot_waited = False
    iteration = 0
    interrupted = False
    fatal_error: str | None = None
    liquidation_complete = False

    async def _cache_proxy_event(event: dict[str, Any]) -> None:
        if not isinstance(event, dict) or not is_bar_event(event):
            return
        symbol_key = event_symbol(event)
        close_price = event_close(event)
        if not symbol_key or close_price is None or close_price <= 0.0:
            return
        with proxy_bars_lock:
            latest_proxy_bars[symbol_key] = dict(event)

    def _start_proxy_listener() -> None:
        nonlocal proxy_listener_stop, proxy_listener_thread
        listener_stop = threading.Event()
        proxy_listener_stop = listener_stop
        listener_url = resolved_data_proxy_url

        def _run_listener() -> None:
            asyncio.run(
                stream_proxy_events(
                    listener_url,
                    _cache_proxy_event,
                    stop_event=listener_stop,
                )
            )

        proxy_listener_thread = threading.Thread(
            target=_run_listener,
            name="liquidation-proxy-listener",
            daemon=True,
        )
        proxy_listener_thread.start()

    def _stop_proxy_listener() -> None:
        if proxy_listener_stop is not None:
            proxy_listener_stop.set()
        if proxy_listener_thread is not None:
            proxy_listener_thread.join(timeout=2.0)

    def _proxy_bar_snapshot(requested_symbols: list[str]) -> dict[str, dict[str, Any]]:
        with proxy_bars_lock:
            return {
                symbol: dict(latest_proxy_bars[symbol])
                for symbol in requested_symbols
                if symbol in latest_proxy_bars
            }

    _start_proxy_listener()
    print_fn("📡 ", f"Listening to live data proxy: {resolved_data_proxy_url}")

    try:
        while True:
            iteration += 1
            reloaded_env_values, env_file_signature = read_env_file_if_changed(
                env_file_text,
                env_file_signature,
            )
            if reloaded_env_values is not None:
                old_limit_spread = resolved_limit_spread
                old_data_proxy_url = resolved_data_proxy_url
                env_values = reloaded_env_values
                resolved_limit_spread = _resolve_limit_spread(limit_spread, env_values)
                env_data_proxy_url = str(env_values.get("DATA_PROXY_URL", "") or "").strip()
                resolved_data_proxy_url = resolve_data_proxy_url(data_proxy_url or env_data_proxy_url or None)
                if old_limit_spread != resolved_limit_spread:
                    print_fn(
                        "♻️ ",
                        f"Environment reload: limit_spread old={old_limit_spread} new={resolved_limit_spread}",
                    )
                if old_data_proxy_url != resolved_data_proxy_url:
                    print_fn(
                        "♻️ ",
                        f"Environment reload: data_proxy_url old={old_data_proxy_url} new={resolved_data_proxy_url}",
                    )
                    _stop_proxy_listener()
                    _start_proxy_listener()
                    initial_proxy_snapshot_waited = False
            try:
                if position_qty_provider is None:
                    positions = trading_client.get_all_positions()
                else:
                    local_qty_by_symbol = position_qty_provider()
                    positions = [
                        SimpleNamespace(symbol=symbol, qty=qty)
                        for symbol, qty in sorted((local_qty_by_symbol or {}).items())
                        if abs(float(qty or 0.0)) > 1e-9
                    ]
            except Exception as exc:
                print_fn("⚠️ ", f"Failed to fetch open positions; retrying: {exc}")
                time.sleep(poll_seconds)
                continue
            if symbol_filter:
                positions = [p for p in positions if str(getattr(p, "symbol", "") or "").strip().upper() in symbol_filter]
            if not positions:
                print_fn("✅ ", f"All positions liquidated after {iteration - 1} iteration(s).")
                liquidation_complete = True
                break

            symbols_for_quotes = sorted({str(position.symbol).upper() for position in positions})
            if not symbols_for_quotes:
                print_fn("✅ ", "No symbols with open positions. Liquidation complete.")
                break

            print_fn("🔁 ", f"Liquidation iteration={iteration} symbols={symbols_for_quotes}")

            proxy_bars = _proxy_bar_snapshot(symbols_for_quotes)

            proxy_prices = {
                symbol: float(event_close(proxy_bars[symbol]) or 0.0)
                for symbol in symbols_for_quotes
                if symbol in proxy_bars and float(event_close(proxy_bars[symbol]) or 0.0) > 0.0
            }
            proxy_symbols = set(proxy_prices)
            fallback_symbols = sorted(set(symbols_for_quotes) - proxy_symbols)

            if fallback_symbols and not initial_proxy_snapshot_waited:
                initial_proxy_snapshot_waited = True
                print_fn(
                    "⏳ ",
                    f"Waiting up to {PROXY_INITIAL_SNAPSHOT_TIMEOUT_SECONDS:.0f}s for the first complete "
                    "WebSocket bar batch before using Alpaca data.",
                )
                proxy_bars = _wait_for_proxy_snapshot(
                    symbols_for_quotes,
                    _proxy_bar_snapshot,
                    timeout_seconds=PROXY_INITIAL_SNAPSHOT_TIMEOUT_SECONDS,
                    poll_seconds=poll_seconds,
                )
                proxy_prices = {
                    symbol: float(event_close(proxy_bars[symbol]) or 0.0)
                    for symbol in symbols_for_quotes
                    if symbol in proxy_bars and float(event_close(proxy_bars[symbol]) or 0.0) > 0.0
                }
                proxy_symbols = set(proxy_prices)
                fallback_symbols = sorted(set(symbols_for_quotes) - proxy_symbols)

            latest_bar_req = None
            latest_bars: dict[str, Any] = {}
            latest_quotes = {}
            baseline_bar_timestamps = {
                symbol: event_datetime_ny(proxy_bars[symbol])
                for symbol in proxy_symbols
            }

            if not fallback_symbols:
                pairs = ", ".join(f"{symbol}={price:.4f}" for symbol, price in sorted(proxy_prices.items()))
                print_fn("📡 ", f"Using WebSocket prices only: {pairs}")
            else:
                print_fn(
                    "⚠️ ",
                    f"Proxy data stream has no cached bars for some positions; requesting Alpaca data only "
                    f"for missing_symbols={fallback_symbols}",
                )
                try:
                    (
                        data_client,
                        data_feed,
                        latest_bar_req,
                        latest_bars,
                        latest_quotes,
                    ) = _fetch_alpaca_fallback_data(
                        fallback_symbols,
                        env_file=env_file_text,
                        alpaca_sdk=alpaca_sdk,
                        data_client=data_client,
                        print_fn=print_fn,
                    )
                except Exception as exc:
                    fatal_error = str(exc)
                    print_fn(
                        "❌ ",
                        f"Proxy, SIP, and IEX market data are unavailable; exiting without canceling or "
                        f"submitting orders: {fatal_error}",
                    )
                    break

                baseline_bar_timestamps.update(
                    {
                        symbol: getattr(latest_bars.get(symbol), "timestamp", None)
                        for symbol in fallback_symbols
                    }
                )
                for symbol_key in fallback_symbols:
                    quote = latest_quotes[symbol_key]
                    print_fn("📈 ", f"Latest quote for {symbol_key}: ask={quote.ask_price}, bid={quote.bid_price}")

            if submitted_order_ids:
                _cancel_submitted_orders(
                    trading_client=trading_client,
                    order_ids=submitted_order_ids,
                    blotter_owner=blotter_owner,
                    iteration=iteration,
                    print_fn=print_fn,
                )
            else:
                _cancel_open_limit_orders(
                    trading_client=trading_client,
                    symbols_for_quotes=symbols_for_quotes,
                    blotter_owner=blotter_owner,
                    iteration=iteration,
                    print_fn=print_fn,
                )

            submitted_order_ids = []
            for position in positions:
                symbol = str(position.symbol).upper()
                quote = latest_quotes.get(symbol)

                broker_qty = int(round(float(getattr(position, "qty", 0.0) or 0.0)))
                if broker_qty == 0:
                    continue

                qty_to_liquidate = int(abs(broker_qty))
                if qty_to_liquidate <= 0:
                    print_fn("⚠️ ", f"Skipping {symbol}: computed liquidation quantity is zero.")
                    continue

                proxy_price = proxy_prices.get(symbol)
                if broker_qty > 0:
                    side = OrderSide.SELL
                    reference_price = float(proxy_price) if proxy_price is not None else float(quote.bid_price or 0.0)
                else:
                    side = OrderSide.BUY
                    reference_price = float(proxy_price) if proxy_price is not None else float(quote.ask_price or 0.0)

                limit_price = float(compute_limit_price(side, reference_price, 0.0, resolved_limit_spread))
                if reference_price <= 0.0:
                    print_fn("⚠️ ", f"Skipping {symbol}: invalid reference quote for limit price.")
                    continue
                if limit_price <= 0.0:
                    limit_price = 0.01

                request = LimitOrderRequest(
                    symbol=symbol,
                    qty=qty_to_liquidate,
                    side=side,
                    type="limit",
                    limit_price=limit_price,
                    extended_hours=True,
                    time_in_force=TimeInForce.DAY,
                )

                print_fn(
                    "📝 ",
                    f"Submitting limit liquidation: symbol={symbol}, side={side}, qty={qty_to_liquidate}, "
                    f"reference_price={reference_price:.2f}, limit_price={limit_price:.2f}",
                )

                canceled_conflicts = cancel_conflicting_opposite_orders(trading_client, symbol, side, print_fn=print_fn)
                if canceled_conflicts > 0:
                    print_fn(
                        "✅ ",
                        f"Canceled {canceled_conflicts} opposite-side market/stop order(s) for {symbol} before submit.",
                    )
                    time.sleep(0.35)

                submitted_order = None
                try:
                    submitted_order = trading_client.submit_order(order_data=request)
                except Exception as exc:
                    error_text = str(exc).lower()
                    if "opposite side market/stop order exists" in error_text:
                        print_fn(
                            "⚠️ ",
                            f"Wash-trade conflict reported for {symbol}; rechecking and canceling opposite-side market/stop orders, then retrying once.",
                        )
                        canceled_retry = cancel_conflicting_opposite_orders(trading_client, symbol, side, print_fn=print_fn)
                        if canceled_retry > 0:
                            print_fn(
                                "✅ ",
                                f"Canceled {canceled_retry} additional conflicting order(s) for {symbol} before retry.",
                            )
                        time.sleep(0.5)
                        submitted_order = trading_client.submit_order(order_data=request)
                    else:
                        rejection_payload = parse_submit_rejection(symbol, side, exc)
                        if bool(rejection_payload.get("is_insufficient_qty", False)):
                            available_qty = float(rejection_payload.get("available_qty", 0.0) or 0.0)
                            retry_qty = int(
                                resolve_insufficient_qty_retry(
                                    qty_to_liquidate,
                                    side,
                                    rejection_payload=rejection_payload,
                                    available_qty=available_qty,
                                    broker_qty=float(broker_qty),
                                    resolver=getattr(alpaca_sdk, "resolve_submittable_qty", None),
                                )
                            )
                            if retry_qty <= 0:
                                print_fn(
                                    "⚠️ ",
                                    f"Skipping {symbol}: insufficient available qty for liquidation submit "
                                    f"(requested={qty_to_liquidate}, available={available_qty}).",
                                )
                                continue

                            print_fn(
                                "🔁 ",
                                f"Retrying liquidation submit for {symbol} with available qty={retry_qty} "
                                f"(requested={qty_to_liquidate}).",
                            )
                            retry_request = LimitOrderRequest(
                                symbol=symbol,
                                qty=retry_qty,
                                side=side,
                                type="limit",
                                limit_price=limit_price,
                                extended_hours=True,
                                time_in_force=TimeInForce.DAY,
                            )
                            submitted_order = trading_client.submit_order(order_data=retry_request)
                        else:
                            print_fn(
                                "⚠️ ",
                                f"Liquidation submit failed for {symbol}; skipping this symbol this iteration: {exc}",
                            )
                            continue

                if submitted_order is None:
                    continue

                order_id = str(getattr(submitted_order, "id", "") or "").strip()
                if order_id:
                    submitted_order_ids.append(order_id)
                if on_order_submitted is not None:
                    on_order_submitted(submitted_order)

                record_trade_submission(
                    blotter_owner,
                    symbol=symbol,
                    side_text=str(side).split(".")[-1].lower(),
                    qty=float(getattr(submitted_order, "qty", qty_to_liquidate) or qty_to_liquidate),
                    order_type="limit",
                    price=float(limit_price),
                    strategy_label="liquidate_positions_limit",
                    broker_order=submitted_order,
                    misc=f"iteration={iteration}",
                )

            if not submitted_order_ids:
                print_fn("⚠️ ", "No liquidation orders were accepted this iteration; retrying with fresh positions.")
                time.sleep(poll_seconds)
                continue

            print_fn("⏳ ", "Waiting for next price bar before cancel/reprice cycle...")
            saw_next_bar = False
            while not saw_next_bar:
                time.sleep(poll_seconds)
                if proxy_symbols:
                    next_proxy_bars = _proxy_bar_snapshot(sorted(proxy_symbols))
                    for symbol in proxy_symbols:
                        next_event = next_proxy_bars.get(symbol)
                        if next_event is None:
                            continue
                        prev_ts = baseline_bar_timestamps.get(symbol)
                        next_ts = event_datetime_ny(next_event)
                        if prev_ts is None or next_ts > prev_ts:
                            saw_next_bar = True
                            break

                if fallback_symbols:
                    try:
                        next_bars = data_client.get_stock_latest_bar(latest_bar_req)
                    except Exception as exc:
                        print_fn("⚠️ ", f"Alpaca latest bar fetch failed while waiting for next bar: {exc}")
                        break
                    for symbol in fallback_symbols:
                        prev_ts = baseline_bar_timestamps.get(symbol)
                        next_bar = next_bars.get(symbol)
                        next_ts = getattr(next_bar, "timestamp", None)
                        if next_ts is not None and (prev_ts is None or next_ts > prev_ts):
                            saw_next_bar = True
                            break
    except KeyboardInterrupt:
        interrupted = True
        print_fn("🛑 ", "Ctrl+C received. Exiting liquidation loop cleanly.")
    finally:
        _stop_proxy_listener()

    blotter_path = str(getattr(blotter_owner, "_trade_blotter_path", ""))
    print_fn("📄 ", f"Liquidation blotter written to {blotter_path}")
    if interrupted:
        print_fn("ℹ️ ", f"Stopped after {iteration} iteration(s).")

    position_queue_path = ""
    if liquidation_complete and update_position_file_on_complete:
        cleared_path = clear_persisted_position_queues(
            strategy_name=strategy_name,
            log_dir_name=log_dir_name,
            symbols=sorted(symbol_filter) if symbol_filter else None,
        )
        position_queue_path = str(cleared_path)
        print_fn("✅ ", f"Updated position queue file with zero positions: {cleared_path}")

    return {
        "iterations": int(iteration),
        "interrupted": bool(interrupted),
        "blotter_path": blotter_path,
        "strategy_name": strategy_name,
        "limit_spread": float(resolved_limit_spread),
        "data_proxy_url": resolved_data_proxy_url,
        "liquidation_complete": bool(liquidation_complete),
        "position_queue_path": position_queue_path,
        "error": fatal_error,
    }


__all__ = ["liquidate_positions_with_limit_loop"]
