"""Pair-trading entrypoint for live bar ingestion and Alpaca API interaction.

This module mirrors master_driver.py runtime behavior, but transforms two live
symbol bars into a synthetic pair bar:

    pair_price = Q1 * price1 - Q2 * price2

The synthetic bar is passed to strategy functions as a single-symbol bar stream,
while resulting pair deltas are translated back into two-leg orders.

Order Lifecycle
---------------
Pair orders use the same shared MasterDriver order-management helpers as other
live masters. Each leg's submitted order IDs and signed deltas are tracked by
symbol. Pending orders remain open while that leg's strategy delta is
unchanged, and zero deltas leave them open; a different nonzero delta cancels
the stale tracked order(s) for that symbol before replacement. The shared confirmation stream asynchronously removes
terminal order IDs and applies confirmed fills to the position queue.

Confirmation Flow
-----------------
Pair execution uses the shared event-driven confirmation owner.
The owner holds the single Alpaca trade-update stream and fans broker updates
out to drivers over a local websocket.

If the owner is not already running, this driver attempts to start it safely in
the background and then waits for the confirmation websocket handshake.
Concurrent driver startups converge on a single owner by retrying the shared
fanout port.

You can still start the owner manually:

    python3 -m MachineTrader.confirm_stream_owner \
        --env-file /Users/jerzy/Develop/trading/config/.env_ratchet_spy_nvda

If the owner cannot be reached and auto-start does not succeed, this driver
fails fast at startup.
Configure the local fanout URL with ``TRADE_PROXY_URL``. Resolution order is:

1. ``trade_proxy_url`` in merged strategy parameters,
2. ``TRADE_PROXY_URL`` in the selected ``--env-file``,
3. process environment ``TRADE_PROXY_URL``,
4. fallback ``ws://127.0.0.1:8766``.

Examples
--------
Environment file values:

    STRATEGY_SYMBOL1=SPY
    STRATEGY_QUANTITY1=1
    STRATEGY_SYMBOL2=QQQ
    STRATEGY_QUANTITY2=1

Run with strat_ratchet_single:

    python3 -m MachineTrader.master_pairs \
        --strategy MachineTrader.strat_ratchet_single:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_ratchet_spy_nvda

    python3 -m MachineTrader.master_pairs \
        --strategy MachineTrader.strat_ratchet_single:call_back \
        --data-proxy-url ws://localhost:8765 \
        --env-file /path/to/pair.env

Run with custom strategy parameters:

    python3 -m MachineTrader.master_pairs \
        --strategy MachineTrader.strat_ratchet_single:call_back \
        --env-file /path/to/pair.env \
        --alpha 0.2 \
        --vol-floor 0.1 \
        --risk-premium 1.5 \
        --start-time 09:35 \
        --end-time 15:55

Override the confirmation fanout URL explicitly via environment:

    TRADE_PROXY_URL=ws://127.0.0.1:9001 \
    python3 -m MachineTrader.master_pairs \
        --strategy MachineTrader.strat_ratchet_single:call_back \
        --env-file /path/to/pair.env

Note: ``--strategy`` module paths must be package-qualified (e.g.
``MachineTrader.strat_ratchet_single:call_back``); a bare module name like
``strat_ratchet_single`` is not importable when running via
``python3 -m MachineTrader.master_pairs``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

from MachineTrader.helpers.driver_entrypoint_helpers import (
    build_strategy_functions as _build_shared_strategy_functions,
    build_strategy_params as _build_shared_strategy_params,
    create_common_driver_arg_parser as _create_common_driver_arg_parser,
    run_async_entrypoint as _run_async_entrypoint,
)
from MachineTrader.helpers.parse_args import (
    warn_ignored_pair_cli_symbols as _warn_ignored_pair_cli_symbols,
)
from MachineTrader.helpers.driver_common import (
    NY_TZ,
    StrategyContext,
    default_noop_strategy as _default_noop_strategy,
    load_strategy_callable as _load_strategy_callable,
    merge_strategy_params_with_env as _merge_strategy_params_with_env,
    normalize_symbol as _normalize_symbol,
    rounded_print as _rounded_print,
)
from MachineTrader.helpers.master_driver_core import MasterDriver
from MachineTrader.helpers.pair_helpers import (
    PairConfig,
    build_pair_bar as _build_pair_bar,
    derive_pair_position as _derive_pair_position,
    derive_pair_qty_from_leg_qtys as _derive_pair_qty_from_leg_qtys,
    pair_close_from_bars as _pair_close_from_bars,
    resolve_pair_config as _resolve_pair_config,
)

__all__ = ["MasterPairsDriver", "main"]


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


class _PairTradingStateProxy:
    """Adapts synthetic pair deltas into two-leg trade instructions."""

    def __init__(
        self,
        base_trading_state,
        pair: PairConfig,
        pair_symbol: str,
        current_pair_price: float,
        is_market_open_fn: Callable[[], bool],
        record_pair_fill_fn: Callable[[str, float], None],
    ):
        self._base = base_trading_state
        self._pair = pair
        self._pair_symbol = pair_symbol
        self._current_pair_price = float(current_pair_price)
        self._is_market_open_fn = is_market_open_fn
        self._record_pair_fill_fn = record_pair_fill_fn

    def __getattr__(self, name: str):
        return getattr(self._base, name)

    def add_strategy_amount(self, symbol: str, qty: float, metadata: dict[str, Any] | None = None):
        symbol_key = _normalize_symbol(symbol)
        if symbol_key != self._pair_symbol:
            self._base.add_strategy_amount(symbol, qty, metadata=metadata)
            return

        pair_qty = float(qty or 0.0)
        if abs(pair_qty) <= 0.0:
            return

        if not self._is_market_open_fn():
            print(
                "WARNING",
                f"Skipping pair order while market is closed: pair={self._pair_symbol} qty={pair_qty:.4f}",
            )
            return

        base_metadata = dict(metadata or {})
        base_metadata["pair_symbol"] = self._pair_symbol
        base_metadata["order_type"] = "market"
        base_metadata["convert_market_to_limit_when_closed"] = False

        leg1_qty = pair_qty * float(self._pair.quantity1)
        if abs(leg1_qty) > 0.0:
            leg1_meta = dict(base_metadata)
            leg1_meta["pair_leg"] = "symbol1"
            self._base.add_strategy_amount(self._pair.symbol1, float(leg1_qty), metadata=leg1_meta)

        leg2_qty = -pair_qty * float(self._pair.quantity2)
        if abs(leg2_qty) > 0.0:
            leg2_meta = dict(base_metadata)
            leg2_meta["pair_leg"] = "symbol2"
            self._base.add_strategy_amount(self._pair.symbol2, float(leg2_qty), metadata=leg2_meta)

        self._record_pair_fill_fn("buy" if pair_qty > 0.0 else "sell", self._current_pair_price)


class MasterPairsDriver(MasterDriver):
    """MasterDriver extension that feeds strategies a synthetic pair bar."""

    def __init__(
        self,
        pair: PairConfig,
        strategy_functions: list[Callable[[StrategyContext], Any]],
        strategy_labels: list[str] | None = None,
        strategy_params: dict[str, float] | None = None,
        data_proxy_url: str | None = None,
        env_file: str | None = None,
        preflight_timeout: float = 10.0,
        preflight_wait_for_bars: float = 60.0,
        preflight_connect_only: bool = False,
        cancel_stale_order_seconds: float = 10.0,
        order_fill_timeout: float = 30.0,
        order_fill_poll_seconds: float = 0.5,
    ):
        self.pair = pair
        self.pair_symbol = pair.pair_symbol
        self._pair_position_queue_prices: list[float] = []
        wrapped_functions = [self._wrap_strategy_function(fn) for fn in strategy_functions]

        super().__init__(
            symbols=[pair.symbol1, pair.symbol2],
            strategy_functions=wrapped_functions,
            strategy_labels=strategy_labels,
            strategy_params=strategy_params,
            data_proxy_url=data_proxy_url,
            env_file=env_file,
            preflight_timeout=preflight_timeout,
            preflight_wait_for_bars=preflight_wait_for_bars,
            preflight_connect_only=preflight_connect_only,
            cancel_stale_order_seconds=cancel_stale_order_seconds,
            order_fill_timeout=order_fill_timeout,
            order_fill_poll_seconds=order_fill_poll_seconds,
        )

    def _record_pair_fill(self, side_text: str, pair_price: float):
        signed_price = -float(pair_price) if str(side_text or "").strip().lower() == "buy" else float(pair_price)
        self._pair_position_queue_prices.append(float(signed_price))

    def _wrap_strategy_function(self, fn: Callable[[StrategyContext], Any]) -> Callable[[StrategyContext], Any]:
        def _runner(context: StrategyContext):
            bar1 = context.minute_bars.get(self.pair.symbol1)
            bar2 = context.minute_bars.get(self.pair.symbol2)
            if not isinstance(bar1, dict) or not isinstance(bar2, dict):
                return None

            pair_bar = _build_pair_bar(self.pair, bar1, bar2)
            pair_price = _pair_close_from_bars(self.pair, bar1, bar2)

            leg1_position = context.positions.get(self.pair.symbol1, {})
            leg2_position = context.positions.get(self.pair.symbol2, {})
            pair_position = _derive_pair_position(
                self.pair,
                leg1_position,
                leg2_position,
                pair_price,
                pair_queue_prices=self._pair_position_queue_prices,
            )
            pair_display_symbol = self.pair.display_symbol

            pair_account = dict(context.account)
            pair_account["unrealized_pnl_by_symbol"] = {
                self.pair_symbol: float(pair_position.get("unrealized_pl", 0.0) or 0.0),
                pair_display_symbol: float(pair_position.get("unrealized_pl", 0.0) or 0.0),
            }
            pair_account["unrealized_pnl_total"] = float(pair_position.get("unrealized_pl", 0.0) or 0.0)

            pair_strategy_params = dict(context.strategy_params)
            pair_strategy_params["strategy_symbol"] = pair_display_symbol
            pair_strategy_params["pair_symbol"] = pair_display_symbol
            pair_strategy_params["pair_internal_symbol"] = self.pair_symbol
            pair_strategy_params["pair_symbol1"] = self.pair.symbol1
            pair_strategy_params["pair_symbol2"] = self.pair.symbol2
            pair_strategy_params["pair_quantity1"] = float(self.pair.quantity1)
            pair_strategy_params["pair_quantity2"] = float(self.pair.quantity2)

            pair_context = StrategyContext(
                minute_key=context.minute_key,
                minute_bars={
                    self.pair_symbol: pair_bar,
                    pair_display_symbol: pair_bar,
                },
                account=pair_account,
                positions={
                    self.pair_symbol: pair_position,
                    pair_display_symbol: pair_position,
                },
                alpaca_api=context.alpaca_api,
                trading_state=_PairTradingStateProxy(
                    context.trading_state,
                    pair=self.pair,
                    pair_symbol=self.pair_symbol,
                    current_pair_price=float(pair_price),
                    is_market_open_fn=self._is_market_open_now,
                    record_pair_fill_fn=self._record_pair_fill,
                ),
                strategy_params=pair_strategy_params,
            )
            return fn(pair_context)

        return _runner

    def _write_eod_report_if_needed(
        self,
        minute_key: tuple[int, int, int, int, int],
        account_snapshot: dict[str, Any],
        positions_snapshot: dict[str, dict[str, Any]],
    ):
        return _reporting_helpers.write_pair_eod_report_if_needed(
            self,
            minute_key,
            account_snapshot,
            positions_snapshot,
        )

    def _submit_order(self, symbol: str, side, qty: float, order_type: str, limit_price: float | None = None) -> str:
        if not self._is_market_open_now():
            print(
                "WARNING",
                f"Skipping order because market is closed: symbol={symbol} side={side} qty={float(qty):.4f}",
            )
            return ""

        # Pair driver enforces market-only submission while market is open.
        return super()._submit_order(symbol, side, qty, "market", None)

    def _heartbeat_stock_price_text(self, use_live_prices: bool) -> str:
        if not use_live_prices:
            return "None"

        price1 = self.latest_symbol_prices.get(self.pair.symbol1)
        price2 = self.latest_symbol_prices.get(self.pair.symbol2)
        if price1 is None or price2 is None:
            return "None"

        bar1 = {
            "o": float(price1),
            "h": float(price1),
            "l": float(price1),
            "c": float(price1),
            "vw": float(price1),
            "v": 0.0,
            "n": 0,
        }
        bar2 = {
            "o": float(price2),
            "h": float(price2),
            "l": float(price2),
            "c": float(price2),
            "vw": float(price2),
            "v": 0.0,
            "n": 0,
        }
        pair_price = _pair_close_from_bars(self.pair, bar1, bar2)
        return self._fmt_optional_number(pair_price, precision=6)

    def _heartbeat_display_symbol(self) -> str:
        return self.pair.display_symbol

    def _internal_queue_pair_qty(self, merged_local_queue: dict[str, list[float]]) -> float:
        leg1_queue = merged_local_queue.get(self.pair.symbol1, []) if isinstance(merged_local_queue, dict) else []
        leg2_queue = merged_local_queue.get(self.pair.symbol2, []) if isinstance(merged_local_queue, dict) else []
        leg1_qty = float(self._signed_queue_to_qty(leg1_queue)) if isinstance(leg1_queue, list) else 0.0
        leg2_qty = float(self._signed_queue_to_qty(leg2_queue)) if isinstance(leg2_queue, list) else 0.0
        return float(_derive_pair_qty_from_leg_qtys(self.pair, leg1_qty, leg2_qty))

    def _broker_pair_qty(self) -> float | None:
        if self.trading_client is None:
            return None

        try:
            broker_positions_raw = self.trading_client.get_all_positions()
        except Exception as exc:
            self._print_error_with_stale_proxy_throttle(
                "pair_broker_qty_fetch_failed",
                f"Pair heartbeat: unable to fetch Alpaca positions for broker pair qty: {exc}",
            )
            return None

        leg_qty1 = 0.0
        leg_qty2 = 0.0
        for pos in broker_positions_raw:
            symbol_key = self._normalize_symbol(getattr(pos, "symbol", ""))
            if symbol_key == self.pair.symbol1:
                leg_qty1 = float(self._signed_qty_from_alpaca_position(pos))
            elif symbol_key == self.pair.symbol2:
                leg_qty2 = float(self._signed_qty_from_alpaca_position(pos))

        return float(_derive_pair_qty_from_leg_qtys(self.pair, leg_qty1, leg_qty2))

    def _emit_heartbeat(
        self,
        *,
        minute_text: str,
        merged_local_queue: dict[str, list[float]],
        unrealized_by_symbol: dict[str, float],
        realized_local_num: float,
        emit_none_price: bool,
    ):
        _ = minute_text
        display_symbol = self._heartbeat_display_symbol()
        stock_price_text = self._heartbeat_stock_price_text(use_live_prices=not emit_none_price)
        heartbeat_timestamp_text = self._heartbeat_timestamp_text(emit_none_price)
        broker_response_message = self._recent_broker_response_messages_text(lookback_seconds=60.0)
        self._last_broker_response_message = broker_response_message

        open_limit_count = self._heartbeat_signed_open_limit_order_count()
        internal_pair_qty = self._internal_queue_pair_qty(merged_local_queue)
        broker_pair_qty = self._broker_pair_qty()
        position_pairs_num = float(broker_pair_qty) if broker_pair_qty is not None else float(internal_pair_qty)

        if broker_pair_qty is not None and abs(float(internal_pair_qty) - float(broker_pair_qty)) > 1e-6:
            print(
                "⚠️ ",
                "Pair position mismatch detected: "
                f"internal_queue_pairs={float(internal_pair_qty):.6f} "
                f"broker_pairs={float(broker_pair_qty):.6f} "
                f"pair={self.pair.display_symbol}",
            )

        pnl_unreal_pair = float(unrealized_by_symbol.get(self.pair.symbol1, 0.0) or 0.0) + float(
            unrealized_by_symbol.get(self.pair.symbol2, 0.0) or 0.0
        )
        position_pairs_text = self._fmt_optional_number(position_pairs_num, precision=6)
        pnl_real_text = self._fmt_optional_number(float(realized_local_num), precision=6)
        pnl_unreal_text = self._fmt_optional_number(float(pnl_unreal_pair), precision=6)

        heartbeat_message = (
            f"timestamp={heartbeat_timestamp_text} | "
            f"symbol={display_symbol} | "
            f"shares={position_pairs_text} | "
            f"price={stock_price_text} | "
            f"pnlReal={pnl_real_text} | "
            f"pnlUnreal={pnl_unreal_text} | "
            f"limit_orders={open_limit_count} | "
            f"broker_message={broker_response_message}"
        )
        heartbeat_message = self._normalize_console_csv_message_fields(heartbeat_message)
        print("💓 ", heartbeat_message, flush=True)
        self._append_message_csv(
            heartbeat_timestamp_text,
            {
                "timestamp": heartbeat_timestamp_text,
                "symbol": display_symbol,
                "shares": position_pairs_text,
                "price": stock_price_text,
                "pnlReal": pnl_real_text,
                "pnlUnreal": pnl_unreal_text,
                "limit_orders": int(open_limit_count),
                "broker_message": broker_response_message,
                "message": heartbeat_message,
            },
            "heartbeat",
        )
        if self._hold_overnight_enabled():
            try:
                self._persist_position_queue_file()
            except Exception as exc:
                print("❌ ", f"Position queue save failed: {exc}")
        print()
        self._last_heartbeat_emitted_at = datetime.now(NY_TZ)


async def _main_async():
    parser = _create_common_driver_arg_parser(
        description="Master pair driver for strategy orchestration",
        symbols_help=(
            "Optional args. master_pairs resolves symbols from "
            "STRATEGY_SYMBOL1/2 in env file."
        ),
        limit_spread_help="Accepted but ignored; market-only submission is enforced in this driver.",
        eod_flatten_help="Liquidate all positions before the end of the trading window. Default: enabled.",
        message_file_help="Optional csv file path where strategy log messages are appended.",
    )
    parser.set_defaults(env_file=str(DEFAULT_ENV_FILE))
    args = parser.parse_args()
    pair = _resolve_pair_config(args.env_file)

    _warn_ignored_pair_cli_symbols(
        args,
        pair_symbol1=pair.symbol1,
        pair_symbol2=pair.symbol2,
        normalize_symbol=_normalize_symbol,
        print_fn=print,
        prefix="INFO",
    )

    strategy_params = _build_shared_strategy_params(args, _merge_strategy_params_with_env)
    strategy_params["strategy_symbol"] = pair.display_symbol
    strategy_params["pair_symbol"] = pair.display_symbol
    strategy_params["pair_internal_symbol"] = pair.pair_symbol
    strategy_params["pair_symbol1"] = pair.symbol1
    strategy_params["pair_symbol2"] = pair.symbol2
    strategy_params["pair_quantity1"] = float(pair.quantity1)
    strategy_params["pair_quantity2"] = float(pair.quantity2)

    strategy_functions, strategy_labels = _build_shared_strategy_functions(
        args,
        load_strategy_callable=_load_strategy_callable,
        default_noop_strategy=_default_noop_strategy,
        print_fn=print,
        no_strategy_prefix="INFO",
    )

    driver = MasterPairsDriver(
        pair=pair,
        strategy_functions=strategy_functions,
        strategy_labels=strategy_labels,
        strategy_params=strategy_params,
        data_proxy_url=args.data_proxy_url,
        env_file=args.env_file,
        preflight_timeout=args.preflight_timeout,
        preflight_wait_for_bars=args.preflight_bars_timeout,
        preflight_connect_only=args.preflight_connect_only,
        cancel_stale_order_seconds=args.cancel_stale_order_seconds,
        order_fill_timeout=args.order_fill_timeout,
        order_fill_poll_seconds=args.order_fill_poll,
    )

    await driver.run()


def main():
    _run_async_entrypoint(
        _main_async,
        print_fn=print,
        interrupted_message="Interrupted by user",
        runtime_error_help="Master pairs driver exited. Start the proxy server and retry.",
    )


if __name__ == "__main__":
    main()
