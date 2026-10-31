"""Momentum portfolio master driver.

This entrypoint extends MasterDriver to:
- parse STRATEGY_SYMBOLS / STRATEGY_QUANTITY from env file,
- enforce market orders during market hours and limit orders otherwise,
- emit momentum-specific heartbeat schema and file naming.

Order Lifecycle
---------------
Live order submission and management are owned by MasterDriver's shared order
helpers. Each submitted order ID is tracked with its symbol, side, share amount,
and signed strategy delta. An unchanged delta leaves its pending order open
across bars; a changed delta requests cancellation of the symbol's stale order(s).
Their IDs remain tracked and the symbol stays gated until terminal stream
confirmation, unless the cancellation reply confirms the order already expired.
An already-expired reply removes the pending ID and permits replacement immediately.
A later bar supplies a fresh delta using updated positions for
replacement; a zero delta leaves the pending order untouched, while a different
nonzero delta requests cancellation before replacement.
Pending-cancel replies are waiting states, not cancellation failures. Other
symbols continue processing independently.
The confirmation stream is processed asynchronously: terminal orders leave the
open-order list and confirmed fills update the local position queue. Existing
strategy-owned orders are reconciled once at startup, not canceled on every bar.

Fill Price References
---------------------
Each last_fill_prices entry is seeded once from that symbol's first valid bar
close after startup, before strategy execution. Missing prices remain unset
until a valid bar arrives. Startup seeds are positive; the spacing gate treats
them as sell-side references. Later bars do not change these references: only
confirmed fills replace them, using negative buy prices and positive sell prices.
The backtest driver inherits the same behavior.

Confirmation Flow
-----------------
Momentum execution uses the shared event-driven confirmation owner.
The owner maintains the single Alpaca trade-update stream and fans broker
updates out to all running drivers over a local websocket.

If the owner is not already running, this driver attempts to start it safely in
the background and then waits for the confirmation websocket handshake.
Concurrent driver startups converge on a single owner by retrying the shared
fanout port.

You can still start the owner manually:

    python3 -m MachineTrader.confirm_stream_owner \
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum

If the owner cannot be reached and auto-start does not succeed, this driver
fails fast at startup.
Configure the local fanout URL with ``TRADE_PROXY_URL``. Resolution order is:

1. ``trade_proxy_url`` in merged strategy parameters,
2. ``TRADE_PROXY_URL`` in the selected ``--env-file``,
3. process environment ``TRADE_PROXY_URL``,
4. fallback ``ws://127.0.0.1:8766``.

Examples
--------
Run momentum strategy with symbols, quantities, and ``TRADE_PROXY_URL`` coming
from the env file:

    python3 -m MachineTrader.master_momentum \
        --strategy MachineTrader.strat_cross:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum

Run momentum strategy with CLI symbols overriding ``STRATEGY_SYMBOLS``:

    python3 -m MachineTrader.master_momentum SPY NVDA AAPL \
        --strategy MachineTrader.strat_cross:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum

Override the confirmation fanout URL explicitly via environment:

    TRADE_PROXY_URL=ws://127.0.0.1:9001 \
    python3 -m MachineTrader.master_momentum \
        --strategy MachineTrader.strat_cross:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum

Note: ``--strategy`` module paths must be package-qualified (e.g.
``MachineTrader.strat_trend:call_back``); a bare module name like
``strat_trend`` is not importable when running via
``python3 -m MachineTrader.master_momentum``.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

from MachineTrader.helpers.driver_entrypoint_helpers import (
    build_strategy_functions as _build_shared_strategy_functions,
    build_strategy_params as _build_shared_strategy_params,
    create_common_driver_arg_parser as _create_common_driver_arg_parser,
    run_async_entrypoint as _run_async_entrypoint,
)
from MachineTrader.helpers.parse_args import (
    resolve_symbols_and_quantity_map_from_args as _resolve_symbols_and_quantity_map_from_args,
)
from MachineTrader.helpers.driver_common import (
    NY_TZ,
    default_noop_strategy as _default_noop_strategy,
    load_strategy_callable as _load_strategy_callable,
    merge_strategy_params_with_env as _merge_strategy_params_with_env,
    rounded_print as _rounded_print,
    strategy_dollar_vol_floor as _strategy_dollar_vol_floor,
)
import MachineTrader.helpers.file_handlers as _reporting_helpers
import MachineTrader.helpers.order_management as _order_mgmt
from MachineTrader.helpers.master_driver_core import MasterDriver

__all__ = ["MasterMomentumDriver", "main"]


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


class MasterMomentumDriver(MasterDriver):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_fill_prices: dict[str, float | None] = {
            symbol_key: None for symbol_key in self.required_symbols
        }
        self._momentum_strategy_name = str(
            self.trading_state.strategy_name or self.strategy_params.get("strategy_name", "") or "master_driver"
        ).strip()

    def _record_confirmed_fill_price(
        self,
        symbol: str,
        side: str,
        fill_price: float,
        fill_qty: float,
        order: Any,
    ) -> None:
        symbol_key = self._normalize_symbol(symbol)
        price_value = abs(float(fill_price or 0.0))
        if not symbol_key or price_value <= 0.0:
            return

        fill_side = str(side or "").strip().lower()
        signed_fill_price = -price_value if fill_side == "buy" else price_value
        self.last_fill_prices[symbol_key] = signed_fill_price

    def _compute_take_profit_delta(
        self,
        symbol: str,
        *,
        merged_local_queue: dict[str, list[float]],
        positions_snapshot: dict[str, dict[str, Any]],
        unrealized_by_symbol: dict[str, float],
    ) -> tuple[float, dict[str, Any]]:
        symbol_key = self._normalize_symbol(symbol)
        if not symbol_key:
            return 0.0, {}

        pos_state = positions_snapshot.get(symbol_key, {}) if isinstance(positions_snapshot, dict) else {}
        current_position = float(pos_state.get("qty", 0.0) or 0.0)
        if abs(current_position) <= 1e-9:
            return 0.0, {}

        queue = merged_local_queue.get(symbol_key, []) if isinstance(merged_local_queue, dict) else []
        if not isinstance(queue, list):
            queue = []
        position_queue_prices = [float(value) for value in queue]

        take_profit_threshold = float(self.strategy_params.get("take_profit_threshold", 5.0) or 5.0)
        take_profit_factor = float(self.strategy_params.get("take_profit_factor", 1.0) or 1.0)
        current_volatility = float(
            self.latest_execution_hints.get(symbol_key, {}).get("volatility", pos_state.get("volatility", 0.0) or 0.0)
            or 0.0
        )
        take_profit_level = max(0.0, take_profit_threshold * current_volatility)
        per_share_take_profit_level = max(0.0, take_profit_factor * current_volatility)
        unrealized_pl = float(unrealized_by_symbol.get(symbol_key, pos_state.get("unrealized_pl", 0.0) or 0.0) or 0.0)
        raw_position_pnls = pos_state.get("unrealized_position_pnls", pos_state.get("unrealized_pnls", []))
        unrealized_position_pnls = [
            float(value) for value in (raw_position_pnls or []) if isinstance(value, (int, float))
        ]
        largest_unrealized_position_pnl = float(pos_state.get("largest_unrealized_position_pnl", 0.0) or 0.0)
        best_lot_close_delta = float(pos_state.get("best_lot_close_delta", 0.0) or 0.0)

        hint: dict[str, Any] = {
            "strategy": "master_momentum",
            "take_profit_triggered": False,
            "take_profit_reason": "",
            "take_profit_level": take_profit_level,
            "per_share_take_profit_level": per_share_take_profit_level,
            "selected_unwind_queue_prices": [],
            "largest_unrealized_position_pnl": largest_unrealized_position_pnl,
            "qualifying_take_profit_count": 0,
            "cancel_all_limits": False,
            "reset_limit_calculator": False,
            "order_type": "market",
        }

        qualifying_take_profit_count = sum(1 for value in unrealized_position_pnls if float(value) > per_share_take_profit_level)
        if qualifying_take_profit_count > 0 and best_lot_close_delta != 0.0:
            delta = best_lot_close_delta * float(qualifying_take_profit_count)
            is_unwinding_long = best_lot_close_delta < 0.0
            qualifying_entries: list[float] = []
            for idx, pnl_value in enumerate(unrealized_position_pnls):
                if idx >= len(position_queue_prices):
                    break
                queue_entry = float(position_queue_prices[idx])
                same_side = (queue_entry < 0.0 and is_unwinding_long) or (queue_entry > 0.0 and not is_unwinding_long)
                if same_side and float(pnl_value) > per_share_take_profit_level:
                    qualifying_entries.append(queue_entry)
            hint.update(
                {
                    "take_profit_triggered": True,
                    "take_profit_reason": "per_share",
                    "selected_unwind_queue_prices": qualifying_entries,
                    "qualifying_take_profit_count": int(qualifying_take_profit_count),
                    "largest_unrealized_position_pnl": largest_unrealized_position_pnl,
                    "cancel_all_limits": True,
                    "reset_limit_calculator": True,
                }
            )
            return float(delta), hint

        if abs(current_position) > 0 and unrealized_pl > 0.0 and unrealized_pl > take_profit_level:
            half_position = min(abs(float(current_position)), max(1.0, abs(float(current_position)) / 2.0))
            delta = -half_position if current_position > 0 else half_position
            unwind_count = int(round(abs(float(delta))))
            selected_unwind = []
            if unwind_count > 0:
                if current_position > 0:
                    candidates = [float(value) for value in position_queue_prices if float(value) < 0.0]
                else:
                    candidates = [float(value) for value in position_queue_prices if float(value) > 0.0]
                selected_unwind = candidates[-unwind_count:]
            hint.update(
                {
                    "take_profit_triggered": True,
                    "take_profit_reason": "aggregate",
                    "selected_unwind_queue_prices": selected_unwind,
                    "cancel_all_limits": True,
                    "reset_limit_calculator": True,
                }
            )
            return float(delta), hint

        return 0.0, hint

    async def _run_strategies(self, context):
        for symbol_key in sorted(self.required_symbols):
            if self.last_fill_prices.get(symbol_key) is not None:
                continue
            bar = context.minute_bars.get(symbol_key, {})
            if not isinstance(bar, dict):
                continue
            raw_price = bar.get("c", bar.get("close"))
            try:
                price_value = float(raw_price)
            except (TypeError, ValueError):
                continue
            if math.isfinite(price_value) and price_value > 0.0:
                self.last_fill_prices[symbol_key] = price_value

        context.last_fill_prices = dict(self.last_fill_prices)
        trade_plan = await super()._run_strategies(context)
        positions_snapshot = context.positions if isinstance(context.positions, dict) else {}
        account_snapshot = context.account if isinstance(context.account, dict) else {}
        unrealized_by_symbol = account_snapshot.get("unrealized_pnl_by_symbol", {})
        if not isinstance(unrealized_by_symbol, dict):
            unrealized_by_symbol = {}

        merged_local_queue = {
            self._normalize_symbol(symbol): list(position.get("position_queue_prices", []))
            for symbol, position in positions_snapshot.items()
            if isinstance(position, dict) and isinstance(position.get("position_queue_prices", []), list)
        }
        gated_symbols = []
        for symbol_key in sorted(self.required_symbols):
            volatility_gap = self._calculate_volatility_gap(symbol_key, context)
            self.latest_execution_hints[symbol_key] = {
                **self.latest_execution_hints.get(symbol_key, {}),
                "volatility_gap": volatility_gap,
            }
            tp_delta, tp_hint = self._compute_take_profit_delta(
                symbol_key,
                merged_local_queue=merged_local_queue,
                positions_snapshot=positions_snapshot,
                unrealized_by_symbol=unrealized_by_symbol,
            )
            if abs(float(tp_delta)) > 1e-9:
                trade_plan[symbol_key] = float(tp_delta)
                self.latest_execution_hints[symbol_key] = {
                    **self.latest_execution_hints.get(symbol_key, {}),
                    **tp_hint,
                }
            gate_type = self._apply_volatility_spacing_gate(
                symbol_key,
                trade_plan,
                positions_snapshot,
                context=context,
            )
            if gate_type:
                gated_symbols.append(symbol_key)
        if gated_symbols:
            _order_mgmt.print_trade_gate_summary("volatility_spacing", gated_symbols)
        return trade_plan

    def _calculate_volatility_gap(self, symbol: str, context: Any) -> float:
        symbol_key = self._normalize_symbol(symbol)
        hint = self.latest_execution_hints.get(symbol_key, {}) if isinstance(self.latest_execution_hints, dict) else {}
        if isinstance(hint, dict):
            return_vol = hint.get("return_vol", hint.get("volatility"))
        else:
            return_vol = None

        try:
            return_vol = float(return_vol)
        except (TypeError, ValueError):
            return_vol = 0.0

        try:
            risk_premium = float(
                self.strategy_params.get(
                    "risk_premium",
                    self.strategy_params.get("STRATEGY_RISK_PREMIUM", 1.0),
                )
                or 1.0
            )
        except (TypeError, ValueError):
            risk_premium = 1.0

        bars = getattr(context, "minute_bars", {})
        bar = bars.get(symbol_key, {}) if isinstance(bars, dict) else {}
        stock_price = bar.get("c", bar.get("close")) if isinstance(bar, dict) else None
        if stock_price is None and isinstance(hint, dict):
            stock_price = hint.get("price")
        if stock_price is None:
            stock_price = self.latest_symbol_prices.get(symbol_key, 0.0)
        dollar_vol_floor = _strategy_dollar_vol_floor(self.strategy_params, stock_price, 0.1)

        return max(risk_premium * return_vol, dollar_vol_floor)

    def _apply_volatility_spacing_gate(
        self,
        symbol: str,
        trade_plan: dict[str, float],
        positions_snapshot: dict[str, dict[str, Any]],
        context: Any = None,
    ) -> str | None:
        symbol_key = self._normalize_symbol(symbol)
        delta = float(trade_plan.get(symbol_key, 0.0) or 0.0)
        if not symbol_key or abs(delta) <= 1e-9:
            return

        hint = self.latest_execution_hints.get(symbol_key, {})
        volatility_gap = abs(float(hint.get("volatility_gap", 0.0) or 0.0))

        bars = getattr(context, "minute_bars", {}) if context is not None else {}
        bar = bars.get(symbol_key, {}) if isinstance(bars, dict) else {}
        close_price = bar.get("c", bar.get("close"))
        if close_price is None:
            close_price = hint.get("price")
        if close_price is None:
            close_price = self.latest_symbol_prices.get(symbol_key)
        if close_price is None or volatility_gap <= 0.0:
            return

        last_fill_price = self.last_fill_prices.get(symbol_key)
        if last_fill_price is None:
            return

        close_price = float(close_price)

        if delta > 0.0 and last_fill_price > 0.0:
            opposite_direction_gap = 2.0 * volatility_gap
            required_buy_price = float(last_fill_price) - opposite_direction_gap
            if close_price > required_buy_price:
                trade_plan[symbol_key] = 0.0
                self.latest_execution_hints[symbol_key] = {
                    **hint,
                    "volatility_spacing_blocked": True,
                    "volatility_spacing_reason": "waiting for opposite-direction buy spacing",
                    "required_buy_price": required_buy_price,
                    "last_fill_price": last_fill_price,
                    "volatility_gap": volatility_gap,
                    "opposite_direction_gap": opposite_direction_gap,
                }
                return "volatility_spacing"

        if delta < 0.0 and last_fill_price < 0.0:
            opposite_direction_gap = 2.0 * volatility_gap
            last_buy_fill_price = abs(float(last_fill_price))
            required_sell_price = last_buy_fill_price + opposite_direction_gap
            if close_price < required_sell_price:
                trade_plan[symbol_key] = 0.0
                self.latest_execution_hints[symbol_key] = {
                    **hint,
                    "volatility_spacing_blocked": True,
                    "volatility_spacing_reason": "waiting for opposite-direction sell spacing",
                    "required_sell_price": required_sell_price,
                    "last_fill_price": last_fill_price,
                    "volatility_gap": volatility_gap,
                    "opposite_direction_gap": opposite_direction_gap,
                }
                return "volatility_spacing"

        if delta < 0.0 and last_fill_price > 0.0:
            required_sell_price = float(last_fill_price) + volatility_gap
            if close_price <= required_sell_price:
                trade_plan[symbol_key] = 0.0
                self.latest_execution_hints[symbol_key] = {
                    **hint,
                    "volatility_spacing_blocked": True,
                    "volatility_spacing_reason": "waiting for volatility-spaced sell add",
                    "required_sell_price": required_sell_price,
                    "last_fill_price": last_fill_price,
                    "volatility_gap": volatility_gap,
                }
                return "volatility_spacing"

        if delta > 0.0 and last_fill_price < 0.0:
            last_buy_fill_price = abs(float(last_fill_price))
            required_buy_price = last_buy_fill_price - volatility_gap
            if close_price >= required_buy_price:
                trade_plan[symbol_key] = 0.0
                self.latest_execution_hints[symbol_key] = {
                    **hint,
                    "volatility_spacing_blocked": True,
                    "volatility_spacing_reason": "waiting for volatility-spaced buy add",
                    "required_buy_price": required_buy_price,
                    "last_fill_price": last_fill_price,
                    "volatility_gap": volatility_gap,
                }
                return "volatility_spacing"
        return None

    def _use_bar_driven_execution_mode(self) -> bool:
        return True

    def _heartbeat_display_symbol(self) -> str:
        return self._momentum_strategy_name

    def _heartbeat_open_limit_order_count(self) -> int:
        if self.trading_client is None:
            return 0

        count = 0
        for symbol_key in sorted(self.required_symbols):
            count += int(self._count_open_limit_orders(symbol_key, strategy_label=None) or 0)
        return int(count)

    def _build_message_csv_path(self, message_kind: str) -> Path:
        return _reporting_helpers.build_momentum_message_csv_path(self, message_kind)

    def _append_message_csv(self, minute_text: str, message_text: str, message_kind: str):
        return _reporting_helpers.append_momentum_message_csv(self, minute_text, message_text, message_kind)

    def _emit_heartbeat(
        self,
        *,
        minute_text: str,
        merged_local_queue: dict[str, list[float]],
        unrealized_by_symbol: dict[str, float],
        realized_local_num: float,
        emit_none_price: bool,
    ):
        heartbeat_timestamp_text = self._heartbeat_timestamp_text(emit_none_price)

        broker_message_lookback_seconds = 60.0
        if self._last_heartbeat_emitted_at is not None:
            elapsed_since_last_heartbeat = (datetime.now(NY_TZ) - self._last_heartbeat_emitted_at).total_seconds()
            broker_message_lookback_seconds = max(60.0, elapsed_since_last_heartbeat + 5.0)
        broker_response_message = self._recent_broker_response_messages_text(
            lookback_seconds=broker_message_lookback_seconds
        )
        self._last_broker_response_message = broker_response_message

        position_dollar = 0.0
        for symbol_key in sorted(self.required_symbols):
            queue = merged_local_queue.get(symbol_key, []) if isinstance(merged_local_queue, dict) else []
            if not isinstance(queue, list):
                continue
            net_qty = float(self._signed_queue_to_qty(queue)) if queue else 0.0
            latest_price = self.latest_symbol_prices.get(symbol_key)
            if latest_price is None:
                continue
            position_dollar += float(net_qty) * float(latest_price)

        (
            symbol_unrealized_by_symbol,
            _symbol_realized_by_symbol,
            symbol_total_pnl_by_symbol,
            pnl_unreal_total,
            pnl_real_total,
        ) = _reporting_helpers.compute_momentum_symbol_pnl_maps(
            self,
            unrealized_by_symbol,
        )

        if isinstance(unrealized_by_symbol, dict):
            # Keep heartbeat internals aligned with symbol-summed unrealized values.
            unrealized_by_symbol.clear()
            unrealized_by_symbol.update(symbol_unrealized_by_symbol)

        open_limit_count = self._heartbeat_open_limit_order_count()
        realized_local_num = float(pnl_real_total)

        position_text = self._fmt_optional_number(position_dollar, precision=6)
        pnl_real_text = self._fmt_optional_number(float(pnl_real_total), precision=6)
        pnl_unreal_text = self._fmt_optional_number(float(pnl_unreal_total), precision=6)

        heartbeat_message = (
            f"timestamp={heartbeat_timestamp_text} | "
            f"symbol={self._momentum_strategy_name} | "
            f"position={position_text} | "
            f"pnlReal={pnl_real_text} | "
            f"pnlUnreal={pnl_unreal_text} | "
            f"limit_orders={open_limit_count} | "
            f"broker_message={broker_response_message}"
        )
        heartbeat_message = self._normalize_console_csv_message_fields(heartbeat_message)
        print("💓 ", heartbeat_message, flush=True)

        self._append_message_csv(
            minute_text,
            {
                "timestamp": heartbeat_timestamp_text,
                "symbol": self._momentum_strategy_name,
                "position": position_text,
                "pnlReal": pnl_real_text,
                "pnlUnreal": pnl_unreal_text,
                "limit_orders": int(open_limit_count),
                "broker_message": broker_response_message,
                "message": heartbeat_message,
            },
            "heartbeat",
        )
        _reporting_helpers.append_momentum_total_pnl_and_positions_csv(
            self,
            timestamp_text=heartbeat_timestamp_text,
            merged_local_queue=merged_local_queue,
            symbol_total_pnl_by_symbol=symbol_total_pnl_by_symbol,
        )
        if self._hold_overnight_enabled():
            try:
                self._persist_position_queue_file()
            except Exception as exc:
                print("❌ ", f"Position queue save failed: {exc}")
        print()
        self._last_heartbeat_emitted_at = datetime.now(NY_TZ)
    
    @staticmethod
    def _minute_key_to_datetime(minute_key: tuple[int, int, int, int, int]) -> datetime:
        year, month, day, hour, minute = minute_key
        return datetime(year, month, day, hour, minute)

    @staticmethod
    def _datetime_to_minute_key(dt_value: datetime) -> tuple[int, int, int, int, int]:
        return (dt_value.year, dt_value.month, dt_value.day, dt_value.hour, dt_value.minute)

    def _iter_missing_minute_keys(
        self,
        previous_minute: tuple[int, int, int, int, int],
        current_minute: tuple[int, int, int, int, int],
    ) -> list[tuple[int, int, int, int, int]]:
        start_dt = self._minute_key_to_datetime(previous_minute)
        end_dt = self._minute_key_to_datetime(current_minute)
        if end_dt <= start_dt + timedelta(minutes=1):
            return []

        result: list[tuple[int, int, int, int, int]] = []
        cursor = start_dt + timedelta(minutes=1)
        while cursor < end_dt:
            result.append(self._datetime_to_minute_key(cursor))
            cursor += timedelta(minutes=1)
        return result

async def _main_async():
    parser = _create_common_driver_arg_parser(
        description="Momentum master driver for portfolio strategy orchestration",
        symbols_help="Symbols expected from proxy stream. If not provided, reads STRATEGY_SYMBOLS from env file.",
        limit_spread_help="Volatility multiplier for limit pricing: buy = current price - limit_spread * volatility, sell = current price + limit_spread * volatility (default: 0.01).",
        eod_flatten_help="Liquidate all positions before the end of the trading window. Default: enabled. Use --no-eod-flatten to disable.",
        message_file_help="Optional csv file path where strategy log messages are appended (columns: minute,message).",
    )
    parser.set_defaults(env_file=str(DEFAULT_ENV_FILE))
    args = parser.parse_args()

    symbols, quantity_by_symbol = _resolve_symbols_and_quantity_map_from_args(
        args,
        symbols_key="STRATEGY_SYMBOLS",
        quantities_key="STRATEGY_QUANTITY",
        default_quantity=1.0,
    )
    if not symbols:
        raise ValueError(
            "No symbols provided. Supply symbols as CLI arguments or set STRATEGY_SYMBOLS in the env file. "
            "Example: python3 -m MachineTrader.master_momentum --strategy MachineTrader.strat_cross:call_back"
        )

    strategy_params = _build_shared_strategy_params(args, _merge_strategy_params_with_env)
    strategy_params["quantity_by_symbol"] = dict(quantity_by_symbol)
    strategy_params["strategy_symbols"] = list(symbols)

    strategy_functions, strategy_labels = _build_shared_strategy_functions(
        args,
        load_strategy_callable=_load_strategy_callable,
        default_noop_strategy=_default_noop_strategy,
        print_fn=print,
        no_strategy_prefix="ℹ️ ",
    )

    driver = MasterMomentumDriver(
        symbols=symbols,
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
        runtime_error_help="Master momentum driver exited. Start the proxy server and retry.",
    )


if __name__ == "__main__":
    main()
