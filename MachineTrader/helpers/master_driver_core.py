"""
Master driver for running intraday trading strategies using the AlpacaSDK.


framework 

orchestrating bar processing, broker state refresh,
strategy execution, and trade submission.

High-level flow per minute:
1) Validate proxy connectivity and symbol coverage before starting.
2) Receive proxy bar events and process each with AlpacAPI.process_bar().
3) Once a full minute of bars is available for required symbols:
   - refresh account + position state from Alpaca
   - call strategy functions
    - submit or replace orders through the shared order-management helpers
    - retain pending orders while their signed strategy delta is unchanged
    - cancel stale symbol orders only when the strategy delta changes
    - consume confirmations asynchronously and apply fills to local queues
4) Wait for next minute bars.

Open strategy orders are reconciled once at startup; they are not automatically
canceled when each new bar arrives. Order IDs remain tracked until cancellation,
rejection, or fill is confirmed by the shared trade-update stream.

Strategy function contract:
- Input: StrategyContext
- Output: one of the following
  - dict[str, int | float]      (symbol -> signed trade amount)
  - list[TradeInstruction]
  - list[dict] with keys symbol/qty (or amount)
  - None for no trade

Signed trade amount convention:
- positive: buy quantity
- negative: sell quantity

Example usage:
- Single strategy callback:
    python3 -m MachineTrader.master_driver SPY --strategy strat_bollinger:call_back

- Single Bollinger strategy with extra parameters:
    python3 -m MachineTrader.master_driver SPY \
        --strategy strat_bollinger:call_back \
        --start-time 07:00 \
        --end-time 18:00 \
        --alpha 0.9 \
        --vol-floor 0.5 \
        --limit-spread 0.05 \
        --risk-premium 1.0 \
        --take-profit-threshold 5.0

- Single ratchet Bollinger strategy:
    python3 -m MachineTrader.master_driver SPY \
        --strategy strat_ratchet_single:call_back \
        --start-time 07:00 \
        --end-time 18:00 \
        --alpha 0.9 \
        --vol-floor 0.5

- Run strategy for multiple symbols:
    python3 -m MachineTrader.master_driver SPY NVDA \
        --strategy strat_bollinger:call_back

- Bundle-based strategy selection:
    python3 -m MachineTrader.master_driver SPY NVDA --strategy-bundle core

- Bundle plus explicit extra strategy:
    python3 -m MachineTrader.master_driver SPY \
        --strategy-bundle bollinger \
        --strategy strat_tanaka:call_back

- Custom proxy URL and environment file:
    python3 -m MachineTrader.master_driver SPY \
        --strategy-bundle tanaka \
        --data-proxy-url ws://localhost:8765 \
        --env-file /path/to/.env

- Configure EOD flatten via environment variable:
    export STRATEGY_EOD_FLATTEN=true
    python3 -m MachineTrader.master_driver SPY \
        --strategy strat_ratchet_single:call_back

- Configure EOD flatten at an exact end time via env file:
    cat > /tmp/strategy.env << 'EOF'
    STRATEGY_EOD_FLATTEN=true
    STRATEGY_END_TIME=15:45:00
    EOF
    python3 -m MachineTrader.master_driver SPY \
        --strategy strat_ratchet_single:call_back \
        --env-file /tmp/strategy.env
"""

from __future__ import annotations

import argparse
import asyncio
import builtins as _builtins
import csv
import importlib
import inspect
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import websockets
from alpaca.trading.enums import OrderSide, TimeInForce

DEFAULT_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

try:
    from MachineTrader.helpers.driver_entrypoint_helpers import run_async_entrypoint as _run_async_entrypoint
    from MachineTrader.helpers.args import resolve_confirmation_proxy_url as _resolve_confirmation_proxy_url
    from MachineTrader.helpers.driver_common import (
        NY_TZ,
        StrategyContext,
        TradeInstruction,
        build_bar_timestamp_skew_warning as _build_bar_timestamp_skew_warning,
        build_client_order_id as _build_client_order_id,
        build_position_queue_file_name as _build_position_queue_file_name,
        default_noop_strategy as _default_noop_strategy,
        event_datetime_ny as _event_datetime_ny,
        event_minute_key as _event_minute_key,
        event_timing_ny as _event_timing_ny,
        event_symbol as _event_symbol,
        fill_missing_minute_bars as _fill_missing_minute_bars,
        is_bar_event as _is_bar_event,
        safe_float as _safe_float,
        derive_strategy_report_name as _derive_strategy_report_name,
        resolve_csv_path as _resolve_csv_path,
        fmt_optional_number as _fmt_optional_number,
        minute_session_status as _minute_session_status,
        resolve_eod_flatten_timing as _resolve_eod_flatten_timing,
        merge_trade_plan as _merge_trade_plan,
        normalize_strategy_output as _normalize_strategy_output,
        load_strategy_callable as _load_strategy_callable,
        merge_strategy_params_with_env as _merge_strategy_params_with_env,
        minute_to_str as _minute_to_str,
        normalize_order_status as _normalize_order_status,
        normalize_symbol as _normalize_symbol,
        parse_hhmm_or_default as _parse_hhmm_or_default,
        parse_bool_env as _parse_bool_env,
        format_timestamp_ny as _format_timestamp_ny,
        rounded_print as _rounded_print,
        round_message_numbers as _round_message_numbers,
        resolve_symbols_from_env as _resolve_symbols_from_env,
        sanitize_strategy_label as _sanitize_strategy_label,
        strategy_from_client_order_id as _strategy_from_client_order_id,
    )
    from . import confirmation_stream as _confirmation_stream
    from . import driver_state_helpers as _state_helpers
    import MachineTrader.helpers.broker_orders as _broker_orders
    import MachineTrader.helpers.calc_pnls as _calc_pnls
    import MachineTrader.helpers.file_handlers as _reporting_helpers
    import MachineTrader.helpers.api_parsing as _api_parsing
    import MachineTrader.helpers.api_responses as _api_responses
    import MachineTrader.helpers.liquidation_limit as _liquidation_limit
    from . import order_management as _order_mgmt
    from .common_driver import CommonDriver
    from MachineTrader.helpers.alpacasdk import AlpacAPI, Trading
except ImportError:
    from MachineTrader.helpers.driver_entrypoint_helpers import run_async_entrypoint as _run_async_entrypoint
    from MachineTrader.helpers.args import resolve_confirmation_proxy_url as _resolve_confirmation_proxy_url
    from MachineTrader.helpers.driver_common import (
        NY_TZ,
        StrategyContext,
        TradeInstruction,
        build_bar_timestamp_skew_warning as _build_bar_timestamp_skew_warning,
        build_client_order_id as _build_client_order_id,
        build_position_queue_file_name as _build_position_queue_file_name,
        default_noop_strategy as _default_noop_strategy,
        event_datetime_ny as _event_datetime_ny,
        event_minute_key as _event_minute_key,
        event_timing_ny as _event_timing_ny,
        event_symbol as _event_symbol,
        fill_missing_minute_bars as _fill_missing_minute_bars,
        is_bar_event as _is_bar_event,
        safe_float as _safe_float,
        derive_strategy_report_name as _derive_strategy_report_name,
        resolve_csv_path as _resolve_csv_path,
        fmt_optional_number as _fmt_optional_number,
        minute_session_status as _minute_session_status,
        resolve_eod_flatten_timing as _resolve_eod_flatten_timing,
        merge_trade_plan as _merge_trade_plan,
        normalize_strategy_output as _normalize_strategy_output,
        load_strategy_callable as _load_strategy_callable,
        merge_strategy_params_with_env as _merge_strategy_params_with_env,
        minute_to_str as _minute_to_str,
        normalize_order_status as _normalize_order_status,
        normalize_symbol as _normalize_symbol,
        parse_hhmm_or_default as _parse_hhmm_or_default,
        parse_bool_env as _parse_bool_env,
        format_timestamp_ny as _format_timestamp_ny,
        rounded_print as _rounded_print,
        round_message_numbers as _round_message_numbers,
        resolve_symbols_from_env as _resolve_symbols_from_env,
        sanitize_strategy_label as _sanitize_strategy_label,
        strategy_from_client_order_id as _strategy_from_client_order_id,
    )
    import MachineTrader.helpers.confirmation_stream as _confirmation_stream
    import MachineTrader.helpers.driver_state_helpers as _state_helpers
    import MachineTrader.helpers.broker_orders as _broker_orders
    import MachineTrader.helpers.calc_pnls as _calc_pnls
    import MachineTrader.helpers.file_handlers as _reporting_helpers
    import MachineTrader.helpers.api_parsing as _api_parsing
    import MachineTrader.helpers.api_responses as _api_responses
    import MachineTrader.helpers.liquidation_limit as _liquidation_limit
    import MachineTrader.helpers.order_management as _order_mgmt
    from MachineTrader.helpers.common_driver import CommonDriver
    from MachineTrader.helpers.alpacasdk import AlpacAPI, Trading


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


class MasterDriver(CommonDriver):
    """Orchestrates proxy bars, broker state refresh, strategy callbacks, and order flow."""

    def __init__(
        self,
        symbols: list[str],
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
        if not symbols:
            raise ValueError("At least one symbol is required.")

        self.symbols = []
        for raw_symbol in symbols:
            normalized = self._normalize_symbol(raw_symbol)
            if normalized:
                self.symbols.append(normalized)
        if not self.symbols:
            raise ValueError("At least one valid symbol is required.")
        self.required_symbols = set(self.symbols)
        if len(strategy_functions) != 1:
            raise ValueError("MasterDriver single-queue mode requires exactly one strategy function.")
        self.strategy_functions = strategy_functions
        self.strategy_labels = strategy_labels or [getattr(fn, "__name__", "strategy") for fn in strategy_functions]
        self.strategy_params = dict(strategy_params or {})
        self.base_strategy_params = dict(self.strategy_params)
        self._bollinger_default_limit = any("bollinger" in str(label).lower() for label in self.strategy_labels)
        self.data_proxy_url = data_proxy_url or os.getenv("DATA_PROXY_URL", "ws://localhost:8765")
        self.env_file = env_file
        self.confirmation_proxy_url = _resolve_confirmation_proxy_url(
            env_file=self.env_file,
            params=self.strategy_params,
        )

        self.preflight_timeout = preflight_timeout
        self.preflight_wait_for_bars = preflight_wait_for_bars
        self.preflight_connect_only = preflight_connect_only
        self.cancel_stale_order_seconds = max(0.0, float(cancel_stale_order_seconds))
        self.order_fill_timeout = order_fill_timeout
        self.order_fill_poll_seconds = order_fill_poll_seconds

        self.alpaca_api = self._create_alpaca_api()
        self.trading_client = None
        self.trading_state = Trading(symbol=self.symbols[0], alpaca_api=self.alpaca_api)
        configured_strategy_name = str(self.strategy_params.get("strategy_name", "") or "").strip()
        self.trading_state.strategy_name = configured_strategy_name or "master_driver"

        self.current_minute_key: tuple[int, int, int, int, int] | None = None
        # The minute _process_minute is working on; current_minute_key may already have advanced.
        self._processing_minute_key: tuple[int, int, int, int, int] | None = None
        self.current_minute_bars: dict[str, dict] = {}
        self.current_minute_processed: bool = False
        self._minute_process_chain_task: asyncio.Task | None = None
        self._last_known_bar_by_symbol: dict[str, dict] = {}
        self.latest_symbol_prices: dict[str, float] = {}
        self.latest_symbol_timestamps: dict[str, str] = {}
        self.last_proxy_bar_received_at: datetime | None = None
        self.proxy_bar_stale_seconds: float = max(30.0, float(os.getenv("PROXY_BAR_STALE_SECONDS", "120")))
        # Startup grace: wait up to 65 seconds for the first bar after stream
        # connection before warning that market-hours bars are missing.
        self.proxy_bar_startup_grace_seconds: float = max(65.0, float(os.getenv("PROXY_BAR_STARTUP_GRACE_SECONDS", "65")))
        self._proxy_stream_connected_at: datetime | None = None
        self._proxy_bar_stale_warning_active: bool = False
        self._no_bar_timeout_message_active: bool = False
        self._post_open_limit_cleanup_day: str | None = None
        self.latest_execution_hints: dict[str, dict[str, Any]] = {}
        self.limit_price_reset_symbols: set[str] = set()
        self.alpaca_api.limit_price_reset_symbols = self.limit_price_reset_symbols
        self._processed_closed_order_ids: set[str] = set()
        self._session_submitted_order_ids: set[str] = set()
        self._processed_session_fill_confirmations: set[str] = set()
        self._selected_unwind_queue_prices_by_order_id: dict[str, list[float]] = {}
        self._position_queue: dict[str, list[float]] = {}
        self._local_realized_pnl_total: float = 0.0
        self._local_realized_pnl_by_symbol: dict[str, float] = {}
        self._position_record_open: dict[str, float] = {}
        self._position_record_closed: set[str] = set(self.required_symbols)
        self._daily_symbol_stats: dict[str, dict[str, float | None]] = {}
        self._eod_report_written_days: set[str] = set()
        self._submitted_order_ids_by_symbol: dict[str, set[str]] = {}
        self._submitted_order_types_by_symbol: dict[str, set[str]] = {}
        self._submitted_order_count_by_symbol: dict[str, int] = {}
        self._working_balance_by_symbol: dict[str, float] = {symbol_key: 0.0 for symbol_key in self.required_symbols}
        self._filled_qty_accounted_by_order_id: dict[str, float] = {}
        self._last_submit_rejection: dict[str, Any] | None = None
        self._daily_total_pnl_high: float | None = None
        self._daily_total_pnl_low: float | None = None
        self._daily_pnl_high_by_symbol: dict[str, float] = {}
        self._daily_pnl_low_by_symbol: dict[str, float] = {}
        self._heartbeat_stale_bar_seconds: float = 62.0
        self._last_heartbeat_emitted_at: datetime | None = None
        self._last_broker_response_message: str = "none"
        self._broker_response_messages_recent: list[tuple[datetime, str]] = []
        self._broker_order_updates_by_id: dict[str, dict[str, Any]] = {}
        self._broker_order_update_events_by_id: dict[str, asyncio.Event] = {}
        self._tracked_open_order_ids: dict[str, dict[str, Any]] = {}
        self._last_delta_by_symbol: dict[str, float] = {symbol_key: 0.0 for symbol_key in self.required_symbols}
        self._open_orders_reconciled: bool = False
        self._confirmation_listener_connected: bool = False
        self._confirmation_stream_active: bool = False
        self._last_confirmation_payload_at: datetime | None = None
        self._spawned_confirmation_owner_pid: int | None = None
        self._stale_proxy_error_log_minute_by_key: dict[str, str] = {}
        self._logged_bar_timestamp_keys: set[str] = set()
        self._trade_blotter_started_at = datetime.now(NY_TZ).strftime("%Y%m%d_%H%M%S")
        self._eod_trigger_day: str | None = None
        _reporting_helpers.initialize_trade_blotter_tracking(self)

    def _handle_filled_order_recovery(self, order: Any, *, warning_message: str | None = None) -> bool:
        broker_payload = _reporting_helpers.order_to_broker_payload(order)
        if not isinstance(broker_payload, dict):
            return False

        status_text = self._normalize_order_status(
            broker_payload.get("status") or broker_payload.get("order_status")
        )
        event_text = self._normalize_order_status(broker_payload.get("event"))
        is_fill_progress = (
            _api_responses.status_in_group(status_text, "fill_progress")
            or _api_responses.event_in_group(event_text, "fill_progress")
        )
        if not is_fill_progress:
            return False

        self._ingest_broker_order_update(broker_payload, apply_fill_updates=True)
        if warning_message:
            print("⚠️ ", warning_message)
        return True

    @staticmethod
    def _cancel_error_indicates_filled_state(exc: Exception) -> bool:
        exc_text = str(exc or "")
        exc_text_lower = exc_text.lower()
        return (
            'already in "filled" state' in exc_text_lower
            or ("42210000" in exc_text_lower and "filled" in exc_text_lower)
        )

    def _recover_filled_order_by_id(
        self,
        order_id: str,
        *,
        success_warning: str,
        failure_warning: str,
    ) -> bool:
        if self.trading_client is None:
            print("⚠️ ", failure_warning)
            return False

        order_key = str(order_id or "").strip()
        if not order_key:
            print("⚠️ ", failure_warning)
            return False

        try:
            order_snapshot = self.trading_client.get_order_by_id(order_id=order_key)
        except Exception:
            order_snapshot = None

        recovered = False
        if order_snapshot is not None:
            recovered = self._handle_filled_order_recovery(order_snapshot, warning_message=success_warning)
        if not recovered:
            print("⚠️ ", failure_warning)
        return bool(recovered)

    def _cancel_stale_tracked_open_orders_between_bars(self, stale_seconds: float = 60.0) -> int:
        if self.trading_client is None:
            return 0

        max_age_seconds = max(1.0, float(stale_seconds))
        now_ny = datetime.now(NY_TZ)
        canceled_count = 0
        confirm_warn_after_seconds = max(1.0, float(os.getenv("MARKET_ORDER_CONFIRM_WARN_SECONDS", "8") or 8.0))

        for order_id, meta in list(self._tracked_open_order_ids.items()):
            submitted_at = meta.get("submitted_at") if isinstance(meta, dict) else None
            if not isinstance(submitted_at, datetime):
                continue

            age_seconds = max(0.0, (now_ny - submitted_at).total_seconds())
            if age_seconds < confirm_warn_after_seconds:
                continue

            latest_update = self._latest_broker_order_update(order_id)
            status_text = ""
            event_text = ""
            if isinstance(latest_update, dict):
                status_text = self._normalize_order_status(latest_update.get("status") or latest_update.get("order_status"))
                event_text = self._normalize_order_status(latest_update.get("event"))

            is_terminal = (
                _api_responses.status_in_group(status_text, "terminal")
                or _api_responses.event_in_group(event_text, "cancel_terminal")
                or _api_responses.event_in_group(event_text, "fill")
            )
            if is_terminal:
                self._drop_tracked_order_id(order_id)
                continue

            if age_seconds < max_age_seconds:
                continue

            if meta.get("cancel_requested"):
                continue
            self._cancel_tracked_order(order_id)
            if meta.get("cancel_requested"):
                canceled_count += 1

        return int(canceled_count)

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        return _safe_float(value, default)

    def _add_working_balance(self, symbol: str, delta_qty: float):
        symbol_key = self._normalize_symbol(symbol)
        if symbol_key not in self.required_symbols:
            return
        delta_value = float(delta_qty or 0.0)
        if abs(delta_value) <= 1e-9:
            return
        current = float(self._working_balance_by_symbol.get(symbol_key, 0.0) or 0.0)
        updated = current + delta_value
        if abs(updated) <= 1e-9:
            updated = 0.0
        self._working_balance_by_symbol[symbol_key] = float(updated)

    def _working_balance(self, symbol: str) -> float:
        symbol_key = self._normalize_symbol(symbol)
        if symbol_key not in self.required_symbols:
            return 0.0
        return float(self._working_balance_by_symbol.get(symbol_key, 0.0) or 0.0)

    async def _execute_pending_working_balances(self) -> None:
        """Deprecated: order-balance resubmission is disabled.

        Master drivers execute only strategy-generated per-bar deltas.
        """
        return

    async def _order_retry_loop(self, retry_interval_seconds: float = 30.0) -> None:
        """Deprecated: order-balance retry loop is disabled."""
        del retry_interval_seconds
        while True:
            await asyncio.sleep(3600)

    @staticmethod
    def _derive_strategy_report_name(strategy_name: str, suffix: str) -> str:
        return _reporting_helpers.derive_strategy_report_name(strategy_name, suffix)

    def _resolve_csv_path(self, raw_path: str, default_name: str) -> Path:
        return _reporting_helpers.resolve_csv_path(raw_path, default_name)

    def _hold_overnight_enabled(self) -> bool:
        raw_eod_flatten = self.strategy_params.get("eod_flatten", True)
        parsed_eod_flatten = _parse_bool_env(raw_eod_flatten)
        if parsed_eod_flatten is not None:
            return not bool(parsed_eod_flatten)
        return not bool(raw_eod_flatten)

    def _position_queue_file_name(self) -> str:
        strategy_name = str(self.trading_state.strategy_name or self.strategy_params.get("strategy_name", "") or "").strip()
        return _reporting_helpers.build_position_queue_file_name(strategy_name)

    def _legacy_position_queue_file_name(self) -> str:
        return _reporting_helpers.build_legacy_position_queue_path(self).name

    def _build_position_queue_path(self) -> Path:
        return _reporting_helpers.build_position_queue_path(self)

    def _apply_queue_payload(self, payload: dict[str, Any]):
        if not isinstance(payload, dict):
            return

        loaded_position_queue: dict[str, list[float]] = {}
        raw_position_queue = payload.get("position_queue")
        if not isinstance(raw_position_queue, dict):
            raw_position_queue = {}

        for symbol_key, values in raw_position_queue.items():
            normalized_symbol = self._normalize_symbol(symbol_key)
            if (
                not normalized_symbol
                or normalized_symbol not in self.required_symbols
                or not isinstance(values, list)
            ):
                continue
            loaded_position_queue[normalized_symbol] = [float(v) for v in values]

        self._position_queue = loaded_position_queue
        persisted_realized_total = self._safe_float(payload.get("local_realized_pnl_total"), default=0.0)
        loaded_realized_by_symbol: dict[str, float] = {}
        for symbol_key, value in (payload.get("local_realized_pnl_by_symbol") or {}).items():
            normalized_symbol = self._normalize_symbol(symbol_key)
            if not normalized_symbol or normalized_symbol not in self.required_symbols:
                continue
            loaded_realized_by_symbol[normalized_symbol] = self._safe_float(value, default=0.0)

        if (not loaded_realized_by_symbol) and abs(float(persisted_realized_total)) > 1e-9 and len(self.required_symbols) == 1:
            single_symbol = next(iter(sorted(self.required_symbols)))
            loaded_realized_by_symbol[single_symbol] = float(persisted_realized_total)
            print(
                "ℹ️ ",
                "Legacy realized PnL total loaded without per-symbol breakdown; "
                f"attributed to single required symbol {single_symbol}.",
            )

        self._local_realized_pnl_by_symbol = loaded_realized_by_symbol
        self._local_realized_pnl_total = float(
            sum(
                float(loaded_realized_by_symbol.get(symbol_key, 0.0) or 0.0)
                for symbol_key in sorted(self.required_symbols)
            )
        )

        if hasattr(self, "_pair_position_queue_prices"):
            raw_pair_queue = payload.get("pair_position_queue_prices")
            if isinstance(raw_pair_queue, list):
                setattr(self, "_pair_position_queue_prices", [float(v) for v in raw_pair_queue])

    def _should_restore_queue_payload(
        self,
        payload: dict[str, Any],
        *,
        now_ny: datetime | None = None,
    ) -> bool:
        if self._hold_overnight_enabled():
            return True

        now_value = now_ny or datetime.now(NY_TZ)
        updated_at_raw = str(payload.get("updated_at", "") or "").strip()
        if not updated_at_raw:
            return False
        try:
            updated_at = datetime.fromisoformat(updated_at_raw.replace("Z", "+00:00"))
        except ValueError:
            return False
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=NY_TZ)
        if updated_at.astimezone(NY_TZ).date() != now_value.date():
            return False

        minute_key = (now_value.year, now_value.month, now_value.day, now_value.hour, now_value.minute)
        session_status, _, _ = self._minute_session_status(minute_key)
        return session_status != "after_end"

    def _load_or_create_position_queue_file(self):
        queue_path = self._build_position_queue_path()
        legacy_queue_path = _reporting_helpers.build_legacy_position_queue_path(self)
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        source_path = queue_path if queue_path.exists() else legacy_queue_path
        if source_path.exists():
            try:
                payload = _reporting_helpers.load_json_payload(source_path)
                if payload is None:
                    raise ValueError("Position queue payload must be a JSON object")
                if not self._should_restore_queue_payload(payload):
                    self._apply_queue_payload({})
                    self._persist_position_queue_file()
                    print("ℹ️ ", f"Discarded stale position queue from {source_path}; EOD flatten is enabled.")
                    return
                self._apply_queue_payload(payload)
                if source_path == legacy_queue_path and source_path != queue_path:
                    self._persist_position_queue_file()
                print("📥 ", f"Loaded position queue from {source_path}")
                return
            except Exception as exc:
                print("⚠️ ", f"Position queue load failed at {source_path}: {exc}. Recreating file.")

        self._persist_position_queue_file()

    def _persist_position_queue_file(self):
        queue_path = self._build_position_queue_path()
        queue_path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._queue_payload()
        _reporting_helpers.save_json_payload(queue_path, payload)

    def _warn_if_broker_positions_exist_without_local_queue(self, positions_snapshot: dict[str, dict[str, Any]] | None):
        if not isinstance(positions_snapshot, dict) or not positions_snapshot:
            return

        local_queue_by_symbol = getattr(self, "_position_queue", None)
        if not isinstance(local_queue_by_symbol, dict):
            local_queue_by_symbol = {}

        missing_symbols: list[str] = []
        for symbol_key in sorted(self.required_symbols):
            current_queue = local_queue_by_symbol.get(symbol_key, [])
            if isinstance(current_queue, list) and current_queue:
                continue

            position_snapshot = positions_snapshot.get(symbol_key, {})
            if not isinstance(position_snapshot, dict):
                continue

            qty = float(position_snapshot.get("qty", 0.0) or 0.0)
            if abs(qty) <= 1e-9:
                continue

            missing_symbols.append(symbol_key)

        if missing_symbols:
            print(
                "⚠️ ",
                f"Local position queue is empty for broker-held symbols={missing_symbols}; keeping local queue as source of truth.",
            )

    def _log_price_bar_timestamp_once(self, bar_time_ny: datetime, wall_time_ny: datetime):
        bar_time_text = bar_time_ny.strftime("%Y-%m-%d %H:%M:%S")
        log_key = bar_time_text
        if log_key in self._logged_bar_timestamp_keys:
            return
        self._logged_bar_timestamp_keys.add(log_key)
        print(
            "🕒 ",
            f"bar_timestamp={bar_time_text} clock_time={wall_time_ny.strftime('%Y-%m-%d %H:%M:%S')}",
        )

    def _is_trading_window_open(self, minute_key: tuple[int, int, int, int, int]) -> bool:
        _, _, _, hh, mm = minute_key
        minute_text = f"{hh:02d}:{mm:02d}"
        minute_time = self._parse_hhmm_or_default(minute_text, "00:00")
        start_text = str(self.strategy_params.get("start_time", "09:30") or "09:30")
        end_text = str(self.strategy_params.get("end_time", "16:00") or "16:00")
        start_time = self._parse_hhmm_or_default(start_text, "09:30")
        end_time = self._parse_hhmm_or_default(end_text, "16:00")
        return start_time <= minute_time < end_time

    def _is_before_strategy_start(self, minute_key: tuple[int, int, int, int, int] | None = None) -> bool:
        key = minute_key or self.current_minute_key
        if key is None:
            now_ny = datetime.now(NY_TZ)
            key = (now_ny.year, now_ny.month, now_ny.day, now_ny.hour, now_ny.minute)
        session_status, _, _ = self._minute_session_status(key)
        return session_status == "before_start"

    def _is_confirmation_relevant_order_id(self, order_id: str) -> bool:
        order_key = str(order_id or "").strip()
        if not order_key:
            return False

        if order_key in self._session_submitted_order_ids:
            return True
        if order_key in self._tracked_open_order_ids:
            return True
        return False

    def _process_owned_order_confirmation(
        self,
        *,
        order_id: str,
        broker_payload: dict[str, Any],
        status_text: str,
        event_text: str,
        apply_fill_updates: bool,
    ) -> None:
        _reporting_helpers.record_broker_order_update(self, broker_payload)

        message_text = _reporting_helpers.broker_message_from_payload(broker_payload)
        event_time = _api_parsing.parse_broker_event_time(
            broker_payload.get("updated_at")
            or broker_payload.get("filled_at")
            or broker_payload.get("timestamp")
            or broker_payload.get("submitted_at")
            or broker_payload.get("created_at"),
            timezone=NY_TZ,
        )
        if message_text:
            self._append_broker_response_message(message_text, event_time=event_time)

        is_terminal_or_done = (
            _api_responses.status_in_group(status_text, "terminal")
            or _api_responses.event_in_group(event_text, "cancel_terminal")
            or _api_responses.event_in_group(event_text, "fill")
        )
        is_fill_progress = (
            _api_responses.status_in_group(status_text, "fill_progress")
            or _api_responses.event_in_group(event_text, "fill_progress")
        )
        if apply_fill_updates and is_fill_progress:
            self._apply_confirmed_fill_to_working_balance(broker_payload)
        if is_terminal_or_done:
            self._drop_tracked_order_id(order_id)

    def _ingest_broker_order_update(self, order: Any, *, apply_fill_updates: bool = True):
        broker_payload = _reporting_helpers.order_to_broker_payload(order)
        if not isinstance(broker_payload, dict):
            return

        order_id = str(
            broker_payload.get("id", "")
            or broker_payload.get("order_id", "")
            or broker_payload.get("client_order_id", "")
            or ""
        ).strip()
        if not order_id:
            return

        self._broker_order_updates_by_id[order_id] = dict(broker_payload)
        update_event = self._broker_order_update_events_by_id.get(order_id)
        if update_event is None:
            update_event = asyncio.Event()
            self._broker_order_update_events_by_id[order_id] = update_event
        update_event.set()

        if not self._is_confirmation_relevant_order_id(order_id):
            return

        status_text = self._normalize_order_status(
            broker_payload.get("status") or broker_payload.get("order_status")
        )
        event_text = self._normalize_order_status(broker_payload.get("event"))

        self._process_owned_order_confirmation(
            order_id=order_id,
            broker_payload=broker_payload,
            status_text=status_text,
            event_text=event_text,
            apply_fill_updates=apply_fill_updates,
        )

    async def _handle_confirmation_fanout_payload(self, payload: dict[str, Any]):
        self._confirmation_stream_active = True
        self._last_confirmation_payload_at = datetime.now(NY_TZ)
        self._ingest_broker_order_update(payload, apply_fill_updates=True)

    def _append_broker_response_message(self, message_text: str, *, event_time: datetime | None = None):
        return _reporting_helpers.append_broker_response_message(self, message_text, event_time=event_time, timezone=NY_TZ)

    def _recent_broker_response_messages_text(
        self,
        lookback_seconds: float = 60.0,
        *,
        warning_only: bool = True,
    ) -> str:
        return _reporting_helpers.recent_broker_response_messages_text(
            self,
            lookback_seconds=lookback_seconds,
            timezone=NY_TZ,
            warning_only=warning_only,
        )

    async def _confirmation_listener_loop(self):
        self._confirmation_listener_connected = True
        await _confirmation_stream.consume_confirmation_fanout(
            self.confirmation_proxy_url,
            self._handle_confirmation_fanout_payload,
            print_fn=print,
            env_file=self.env_file,
        )

    def _update_daily_symbol_stats(self, bars_for_minute: dict[str, dict], session_status: str):
        for symbol_key in sorted(self.required_symbols):
            bar = bars_for_minute.get(symbol_key, {})
            if not isinstance(bar, dict):
                continue

            open_px = self._safe_float(bar.get("o", bar.get("open")), default=0.0)
            high_px = self._safe_float(bar.get("h", bar.get("high")), default=0.0)
            low_px = self._safe_float(bar.get("l", bar.get("low")), default=0.0)
            close_px = self._safe_float(bar.get("c", bar.get("close")), default=0.0)

            stats = self._daily_symbol_stats.setdefault(
                symbol_key,
                {
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": None,
                    "session_open": None,
                    "session_high": None,
                    "session_low": None,
                    "session_close": None,
                },
            )

            if open_px > 0.0 and stats.get("open") is None:
                stats["open"] = open_px

            if close_px > 0.0:
                stats["close"] = close_px

            if high_px > 0.0:
                prior_high = stats.get("high")
                stats["high"] = high_px if prior_high is None else max(float(prior_high), high_px)

            if low_px > 0.0:
                prior_low = stats.get("low")
                stats["low"] = low_px if prior_low is None else min(float(prior_low), low_px)

            if session_status == "in_session":
                if open_px > 0.0 and stats.get("session_open") is None:
                    stats["session_open"] = open_px
                if close_px > 0.0:
                    stats["session_close"] = close_px
                if high_px > 0.0:
                    prior_session_high = stats.get("session_high")
                    stats["session_high"] = high_px if prior_session_high is None else max(float(prior_session_high), high_px)
                if low_px > 0.0:
                    prior_session_low = stats.get("session_low")
                    stats["session_low"] = low_px if prior_session_low is None else min(float(prior_session_low), low_px)

    def _build_eod_report_path(self) -> Path:
        return _reporting_helpers.build_eod_report_path(self)

    def _collect_submitted_orders_by_id(self) -> dict[str, Any]:
        start_of_day = datetime.now(NY_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        return _broker_orders.collect_orders_by_id_for_statuses(
            self.trading_client,
            statuses=(_broker_orders.QueryOrderStatus.OPEN, _broker_orders.QueryOrderStatus.CLOSED),
            after=start_of_day,
            symbols=self.symbols,
            limit=500,
            on_error=lambda error_key, message: self._print_error_with_stale_proxy_throttle(
                f"eod_report_{error_key}_orders_acceptance_stats",
                f"EOD report: {message}",
            ),
            error_key_prefix="unable_fetch",
        )

    def _collect_open_submitted_orders_by_id(self) -> dict[str, Any]:
        start_of_day = datetime.now(NY_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
        return _broker_orders.collect_orders_by_id_for_statuses(
            self.trading_client,
            statuses=(_broker_orders.QueryOrderStatus.OPEN,),
            after=start_of_day,
            symbols=self.symbols,
            limit=500,
            on_error=lambda error_key, message: self._print_error_with_stale_proxy_throttle(
                f"open_orders_{error_key}",
                f"Open-orders sync: {message}",
            ),
            error_key_prefix="unable_fetch",
        )

    def _collect_submitted_order_statuses_by_id(self) -> dict[str, str]:
        known_orders_by_id = self._collect_submitted_orders_by_id()
        return _broker_orders.build_order_status_map(
            known_orders_by_id,
            normalize_status=self._normalize_order_status,
        )

    def _collect_accepted_order_counts_by_symbol(self, known_status_by_id: dict[str, str] | None = None) -> dict[str, int]:
        if known_status_by_id is None:
            known_status_by_id = self._collect_submitted_order_statuses_by_id()
        return _broker_orders.count_submitted_orders_by_symbol(
            required_symbols=self.required_symbols,
            submitted_order_ids_by_symbol=self._submitted_order_ids_by_symbol,
            known_status_by_id=known_status_by_id,
            exclude_statuses={"rejected"},
            require_nonempty_status=True,
        )

    def _collect_cancelled_order_counts_by_symbol(self, known_status_by_id: dict[str, str] | None = None) -> dict[str, int]:
        if known_status_by_id is None:
            known_status_by_id = self._collect_submitted_order_statuses_by_id()
        return _broker_orders.count_submitted_orders_by_symbol(
            required_symbols=self.required_symbols,
            submitted_order_ids_by_symbol=self._submitted_order_ids_by_symbol,
            known_status_by_id=known_status_by_id,
            include_statuses={"canceled", "cancelled"},
        )

    def _collect_rejected_order_counts_by_symbol(self, known_status_by_id: dict[str, str] | None = None) -> dict[str, int]:
        if known_status_by_id is None:
            known_status_by_id = self._collect_submitted_order_statuses_by_id()
        return _broker_orders.count_submitted_orders_by_symbol(
            required_symbols=self.required_symbols,
            submitted_order_ids_by_symbol=self._submitted_order_ids_by_symbol,
            known_status_by_id=known_status_by_id,
            include_statuses={"rejected"},
        )

    def _update_intraday_pnl_extremes(self, account_snapshot: dict[str, Any]):
        (
            self._daily_total_pnl_high,
            self._daily_total_pnl_low,
            self._daily_pnl_high_by_symbol,
            self._daily_pnl_low_by_symbol,
        ) = _calc_pnls.update_intraday_pnl_extremes_from_account(
            account_snapshot,
            required_symbols=self.required_symbols,
            safe_float=self._safe_float,
            daily_total_pnl_high=self._daily_total_pnl_high,
            daily_total_pnl_low=self._daily_total_pnl_low,
            daily_pnl_high_by_symbol=self._daily_pnl_high_by_symbol,
            daily_pnl_low_by_symbol=self._daily_pnl_low_by_symbol,
        )

    def _write_eod_report_if_needed(
        self,
        minute_key: tuple[int, int, int, int, int],
        account_snapshot: dict[str, Any],
        positions_snapshot: dict[str, dict[str, Any]],
    ):
        return _reporting_helpers.write_eod_report_if_needed(self, minute_key, account_snapshot, positions_snapshot)

    def _reset_daily_trackers_if_new_day(self, minute_key: tuple[int, int, int, int, int]):
        y, m, d, _, _ = minute_key
        today_key = f"{y:04d}-{m:02d}-{d:02d}"
        if getattr(self, "_current_tracking_day", None) == today_key:
            return

        self._current_tracking_day = today_key
        self._daily_symbol_stats = {}
        self._submitted_order_ids_by_symbol = {}
        self._submitted_order_types_by_symbol = {}
        self._submitted_order_count_by_symbol = {}
        self._daily_total_pnl_high = None
        self._daily_total_pnl_low = None
        self._daily_pnl_high_by_symbol = {}
        self._daily_pnl_low_by_symbol = {}
        self._logged_bar_timestamp_keys = set()
        _reporting_helpers.initialize_trade_blotter_tracking(self)

    def _eod_flatten_enabled(self) -> bool:
        raw_value = self.strategy_params.get("eod_flatten", True)
        parsed_value = _parse_bool_env(raw_value)
        return bool(parsed_value) if parsed_value is not None else bool(raw_value)

    def _claim_eod_trigger(self, minute_key: tuple[int, int, int, int, int]) -> bool:
        day_key = f"{minute_key[0]:04d}-{minute_key[1]:02d}-{minute_key[2]:02d}"
        if self._eod_trigger_day == day_key:
            return False
        self._eod_trigger_day = day_key
        return True

    async def _submit_eod_liquidation_before_strategy(
        self,
        minute_key: tuple[int, int, int, int, int],
        end_text: str,
        positions_snapshot: dict[str, dict[str, Any]],
        *,
        market_is_open_now: bool,
    ) -> bool:
        if not self._eod_flatten_enabled():
            return False

        if not market_is_open_now:
            limit_spread_raw = self.strategy_params.get("limit_spread", None)
            try:
                limit_spread_value = float(limit_spread_raw) if limit_spread_raw is not None else None
            except (TypeError, ValueError):
                limit_spread_value = None

            bar_poll_raw = self.strategy_params.get(
                "liquidation_bar_poll_seconds",
                self.strategy_params.get("bar_poll_seconds", 1.0),
            )
            try:
                bar_poll_seconds = max(0.2, float(bar_poll_raw))
            except (TypeError, ValueError):
                bar_poll_seconds = 1.0

            print(
                "📊 ",
                f"EOD flatten enabled; market is closed after STRATEGY_END_TIME={end_text}. "
                "Using the shared limit-order liquidation loop with local queue positions.",
            )
            await asyncio.to_thread(
                _liquidation_limit.liquidate_positions_with_limit_loop,
                env_file=str(self.env_file or ""),
                limit_spread=limit_spread_value,
                bar_poll_seconds=bar_poll_seconds,
                data_proxy_url=self.data_proxy_url,
                symbols=sorted(self.required_symbols),
                alpaca_sdk=self.alpaca_api,
                trading_client=self.trading_client,
                data_client=getattr(self.alpaca_api, "data_client", None),
                position_qty_provider=self._local_position_qty_snapshot,
                on_order_submitted=self._track_shared_liquidation_order,
                update_position_file_on_complete=False,
                print_fn=print,
            )
            self._working_balance_by_symbol = {symbol_key: 0.0 for symbol_key in self.required_symbols}
            return True

        print(
            "📊 ",
            f"EOD flatten enabled; canceling limit orders and liquidating portfolio "
            f"before passing the after-end bar to strategies; STRATEGY_END_TIME={end_text}.",
        )
        for symbol_key in sorted(self.required_symbols):
            self._cancel_all_limit_orders(symbol_key, strategy_label=None, reason="eod")

        submitted_any = False
        for symbol_key in sorted(self.required_symbols):
            current_qty = float(positions_snapshot.get(symbol_key, {}).get("qty", 0.0) or 0.0)
            if abs(current_qty) <= 1e-9:
                continue
            self.latest_execution_hints.setdefault(symbol_key, {})["eod_flatten"] = True
            self.latest_execution_hints[symbol_key]["order_type"] = "market"
            await self._execute_symbol_delta(
                symbol=symbol_key,
                delta_qty=float(-current_qty),
                current_qty=current_qty,
            )
            submitted_any = True
        return submitted_any

    def _local_position_qty_snapshot(self) -> dict[str, float]:
        merged_local_queue = self._merge_position_queue()
        return {
            symbol_key: float(self._signed_queue_to_qty(merged_local_queue.get(symbol_key, [])))
            for symbol_key in sorted(self.required_symbols)
        }

    def _track_shared_liquidation_order(self, order: Any) -> None:
        order_id = str(getattr(order, "id", "") or "").strip()
        symbol_key = self._normalize_symbol(getattr(order, "symbol", ""))
        if not order_id or not symbol_key:
            return
        self._track_submitted_order_id(
            order_id=order_id,
            symbol=symbol_key,
            side=self._normalize_order_status(getattr(order, "side", "")),
            order_type=self._normalize_order_status(getattr(order, "type", "limit")),
            qty=float(getattr(order, "qty", 0.0) or 0.0),
        )
        self._session_submitted_order_ids.add(order_id)

    async def _trigger_wall_clock_eod_if_needed(self, now_ny: datetime | None = None) -> bool:
        now_value = now_ny or datetime.now(NY_TZ)
        minute_key = (
            now_value.year,
            now_value.month,
            now_value.day,
            now_value.hour,
            now_value.minute,
        )
        session_status, _, end_text = self._minute_session_status(minute_key)
        if session_status != "after_end":
            return False

        if not self._eod_flatten_enabled():
            return False

        day_key = now_value.date().isoformat()
        if self._eod_trigger_day == day_key:
            return False

        last_bar_at = self.last_proxy_bar_received_at
        if last_bar_at is None:
            last_bar_at = self._proxy_stream_connected_at
        if last_bar_at is None or (now_value - last_bar_at).total_seconds() < 65.0:
            return False

        print(
            "⏰ ",
            f"No price bar received for 65 seconds after STRATEGY_END_TIME={end_text}; "
            "using wall clock to trigger shared EOD liquidation processing.",
        )
        await self._process_minute(minute_key, {})
        return True

    def _mark_limit_price_reset(self, symbol: str):
        symbol_key = self._normalize_symbol(symbol)
        if symbol_key:
            self.limit_price_reset_symbols.add(symbol_key)

    @staticmethod
    def _sanitize_strategy_label(label: str) -> str:
        return _sanitize_strategy_label(label)

    def _build_client_order_id(self, strategy_label: str, symbol: str) -> str:
        return _build_client_order_id(strategy_label, symbol)

    @staticmethod
    def _strategy_from_client_order_id(client_order_id: str) -> str:
        return _strategy_from_client_order_id(client_order_id)

    def _compute_realized_pnl_from_local_signed_queue(self) -> float:
        return _state_helpers.compute_realized_pnl_from_local_signed_queue(self)

    @staticmethod
    def _signed_queue_to_qty(queue: list[float]) -> float:
        return _state_helpers.signed_queue_to_qty(queue)

    @staticmethod
    def _signed_queue_unrealized_components(queue: list[float], current_price: float) -> list[float]:
        return _state_helpers.signed_queue_unrealized_components(queue, current_price)

    def _merge_position_queue(self) -> dict[str, list[float]]:
        return _state_helpers.merge_position_queue(self)

    def _compute_unrealized_pnl_from_local_signed_queue(
        self,
        local_queue_by_symbol: dict[str, list[float]] | None = None,
    ) -> tuple[dict[str, float], float]:
        return _state_helpers.compute_unrealized_pnl_from_local_signed_queue(self, local_queue_by_symbol)

    def _compute_positions_from_local_signed_queue(
        self,
        local_queue_by_symbol: dict[str, list[float]] | None = None,
        unrealized_by_symbol: dict[str, float] | None = None,
    ) -> dict[str, dict[str, Any]]:
        return _state_helpers.compute_positions_from_local_signed_queue(self, local_queue_by_symbol, unrealized_by_symbol)

    @staticmethod
    def _queue_avg_entry_price(queue: list[float]) -> float:
        return _state_helpers.queue_avg_entry_price(queue)

    @staticmethod
    def _signed_qty_from_alpaca_position(pos: Any) -> float:
        return _state_helpers.signed_qty_from_alpaca_position(pos)

    def _update_position_records_from_snapshot(self, positions: dict[str, dict[str, Any]]):
        return _state_helpers.update_position_records_from_snapshot(self, positions)

    def _compare_position_records_with_alpaca(self):
        return _state_helpers.compare_position_records_with_alpaca(self)

    def _strategy_order_keys(self) -> set[str]:
        return _order_mgmt.strategy_order_keys(self)

    def _cancel_strategy_limit_orders_after_market_open(self, force_cleanup: bool = False):
        return _order_mgmt.cancel_strategy_limit_orders_after_market_open(self, force_cleanup=force_cleanup)

    def _heartbeat_primary_symbol(self) -> str:
        if self.symbols:
            return str(self.symbols[0])
        return ""

    def _heartbeat_display_symbol(self) -> str:
        return self._heartbeat_primary_symbol()

    def _timestamp_from_bar_or_now(self, symbol_key: str | None = None) -> str:
        symbol_key = str(symbol_key or "").strip() or self._heartbeat_primary_symbol()
        raw_ts = str(self.latest_symbol_timestamps.get(symbol_key, "") or "").strip()
        return _format_timestamp_ny(raw_ts)

    def _heartbeat_timestamp_text(self, emit_none_price: bool) -> str:
        if emit_none_price:
            return _format_timestamp_ny(None)
        # Stamp per-minute rows with the bar minute being processed, not the latest
        # bar seen; a late-flushed minute would otherwise take the next minute's label.
        minute_key = self._processing_minute_key
        if minute_key is not None:
            year, month, day, hour, minute = minute_key
            return f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:00"
        return self._timestamp_from_bar_or_now()

    def _is_proxy_bar_stale(self) -> bool:
        last_bar = self.last_proxy_bar_received_at
        if last_bar is None:
            return True
        return (datetime.now(NY_TZ) - last_bar).total_seconds() >= self._heartbeat_stale_bar_seconds

    def _print_error_with_stale_proxy_throttle(self, error_key: str, message: str):
        key = str(error_key or "unknown_error")
        if not self._is_proxy_bar_stale():
            print("❌ ", message)
            return

        minute_bucket = datetime.now(NY_TZ).strftime("%Y-%m-%d %H:%M")
        last_bucket = self._stale_proxy_error_log_minute_by_key.get(key)
        if last_bucket == minute_bucket:
            return
        self._stale_proxy_error_log_minute_by_key[key] = minute_bucket
        print("❌ ", message)

    def _heartbeat_signed_open_limit_order_count(self) -> int:
        if self.trading_client is None:
            return 0
        try:
            return _broker_orders.signed_open_limit_order_count(
                self.trading_client,
                symbols=self.symbols,
                normalize_status=self._normalize_order_status,
            )
        except Exception:
            return 0

    def _heartbeat_stock_price_text(self, use_live_prices: bool) -> str:
        if not use_live_prices:
            return "None"

        if len(self.symbols) == 1:
            symbol_key = self.symbols[0]
            price = self.latest_symbol_prices.get(symbol_key)
            return "None" if price is None else self._fmt_optional_number(price, precision=6)

        parts: list[str] = []
        for symbol_key in sorted(self.required_symbols):
            price = self.latest_symbol_prices.get(symbol_key)
            price_text = "None" if price is None else self._fmt_optional_number(price, precision=6)
            parts.append(f"{symbol_key}={price_text}")
        return "; ".join(parts) if parts else "None"

    def _emit_heartbeat(
        self,
        *,
        minute_text: str,
        merged_local_queue: dict[str, list[float]],
        unrealized_by_symbol: dict[str, float],
        realized_local_num: float,
        emit_none_price: bool,
    ):
        self._reload_strategy_params_from_env()
        stock_symbol = self._heartbeat_primary_symbol()
        display_symbol = self._heartbeat_display_symbol()
        stock_price_text = self._heartbeat_stock_price_text(use_live_prices=not emit_none_price)
        heartbeat_timestamp_text = self._heartbeat_timestamp_text(emit_none_price)
        broker_message_lookback_seconds = 60.0
        if self._last_heartbeat_emitted_at is not None:
            elapsed_since_last_heartbeat = (datetime.now(NY_TZ) - self._last_heartbeat_emitted_at).total_seconds()
            broker_message_lookback_seconds = max(60.0, elapsed_since_last_heartbeat + 5.0)
        broker_response_message = self._recent_broker_response_messages_text(
            lookback_seconds=broker_message_lookback_seconds
        )
        self._last_broker_response_message = broker_response_message

        open_limit_count = self._heartbeat_signed_open_limit_order_count()
        position_shares_num = _calc_pnls.queue_symbol_position_shares(
            merged_local_queue,
            symbol=stock_symbol,
            signed_queue_to_qty=self._signed_queue_to_qty,
        )

        (
            symbol_unrealized_by_symbol,
            _symbol_realized_by_symbol,
            _symbol_total_by_symbol,
            pnl_unreal_total,
            pnl_real_total,
        ) = _reporting_helpers.compute_symbol_pnl_maps(
            required_symbols=self.required_symbols,
            unrealized_by_symbol=unrealized_by_symbol,
            realized_by_symbol=getattr(self, "_local_realized_pnl_by_symbol", {}),
        )
        if isinstance(unrealized_by_symbol, dict):
            unrealized_by_symbol.clear()
            unrealized_by_symbol.update(symbol_unrealized_by_symbol)

        realized_local_num = float(pnl_real_total)
        position_shares_text = self._fmt_optional_number(position_shares_num, precision=6)
        pnl_real_text = self._fmt_optional_number(float(pnl_real_total), precision=6)
        pnl_unreal_text = self._fmt_optional_number(float(pnl_unreal_total), precision=6)

        heartbeat_message = (
            f"timestamp={heartbeat_timestamp_text} | "
            f"symbol={display_symbol} | "
            f"shares={position_shares_text} | "
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
                "shares": position_shares_text,
                "price": stock_price_text,
                "pnlReal": pnl_real_text,
                "pnlUnreal": pnl_unreal_text,
                "limit_orders": int(open_limit_count),
                "broker_message": broker_response_message,
                "message": heartbeat_message,
            },
            "heartbeat",
        )
        try:
            self._persist_position_queue_file()
        except Exception as exc:
            print("❌ ", f"Position queue save failed: {exc}")
        print()
        self._last_heartbeat_emitted_at = datetime.now(NY_TZ)

    async def _heartbeat_loop(self, interval_seconds: float = 60.0):
        interval_seconds = max(1.0, float(interval_seconds))
        while True:
            try:
                await self._trigger_wall_clock_eod_if_needed()
                no_price_bar = self._warn_if_no_proxy_bar_timeout_once()
                if not no_price_bar:
                    self._cancel_strategy_limit_orders_after_market_open()
            except Exception as exc:
                error_time = self._timestamp_from_bar_or_now()
                error_message = f"heartbeat_error time={error_time} | error={exc}"
                self._print_error_with_stale_proxy_throttle(
                    "heartbeat_loop_error",
                    f"Heartbeat loop error: {exc}",
                )
                try:
                    self._append_message_csv(error_time, error_message, "heartbeat")
                except Exception as csv_exc:
                    self._print_error_with_stale_proxy_throttle(
                        "heartbeat_csv_write_error",
                        f"Heartbeat csv write error: {csv_exc}",
                    )

            await asyncio.sleep(1.0)

    def _warn_if_no_proxy_bar_timeout_once(self) -> bool:
        now = datetime.now(NY_TZ)
        stream_connected_at = self._proxy_stream_connected_at
        if stream_connected_at is None:
            self._no_bar_timeout_message_active = False
            return False

        threshold_seconds = max(65.0, float(self.proxy_bar_startup_grace_seconds))
        last_bar = self.last_proxy_bar_received_at

        if last_bar is None:
            age_seconds = max(0.0, (now - stream_connected_at).total_seconds())
            if age_seconds < threshold_seconds:
                self._no_bar_timeout_message_active = False
                return False
            if not self._no_bar_timeout_message_active:
                connected_text = stream_connected_at.strftime("%Y-%m-%d %H:%M:%S %Z")
                print(
                    "⚠️ ",
                    "No price bar was received since proxy stream connection "
                    f"time={connected_text} wait_seconds={age_seconds:.1f}; waiting for next bar.",
                )
                self._no_bar_timeout_message_active = True
            return True

        age_seconds = max(0.0, (now - last_bar).total_seconds())
        if age_seconds < threshold_seconds:
            self._no_bar_timeout_message_active = False
            return False

        if not self._no_bar_timeout_message_active:
            last_bar_text = last_bar.strftime("%Y-%m-%d %H:%M:%S %Z")
            print(
                "⚠️ ",
                "No price bar was received since last bar "
                f"time={last_bar_text} wait_seconds={age_seconds:.1f}; waiting for next bar.",
            )
            self._no_bar_timeout_message_active = True
        return True

    def _warn_if_proxy_bar_stale_during_market_hours(self):
        if self.trading_client is None:
            return

        market_is_open = self._is_market_open_now()
        if not market_is_open:
            self._proxy_bar_stale_warning_active = False
            return

        now = datetime.now(NY_TZ)
        stream_connected_at = self._proxy_stream_connected_at
        if stream_connected_at is None:
            # Do not warn before the proxy websocket stream is actually connected.
            return

        last_bar = self.last_proxy_bar_received_at
        if last_bar is None:
            connected_age = max(0.0, (now - stream_connected_at).total_seconds())
            if connected_age < self.proxy_bar_startup_grace_seconds:
                return
            if not self._proxy_bar_stale_warning_active:
                print("WARNING: Proxy is not providing bars during market hours.")
                print("⚠️")
                self._proxy_bar_stale_warning_active = True
            return

        age_seconds = max(0.0, (now - last_bar).total_seconds())
        if age_seconds > self.proxy_bar_stale_seconds:
            if not self._proxy_bar_stale_warning_active:
                print("WARNING: Proxy is not providing bars during market hours.")
                print("⚠️")
                print(
                    f"last_bar_received={last_bar.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                    f"age_seconds={age_seconds:.1f} threshold_seconds={self.proxy_bar_stale_seconds:.1f}"
                )
                self._proxy_bar_stale_warning_active = True
        else:
            self._proxy_bar_stale_warning_active = False

    def _merge_trade_plan(self, aggregate: dict[str, float], incoming: dict[str, float]):
        return _merge_trade_plan(aggregate, incoming, self.required_symbols)

    def _print_startup_configuration(self):
        """Print configured strategies and runtime parameters at startup."""
        strategy_names = self.strategy_labels or ["none"]
        print("🧩 ", f"Startup strategy_name={', '.join(str(name) for name in strategy_names)}")
        if self.strategy_params:
            ordered_items = sorted(self.strategy_params.items(), key=lambda item: str(item[0]))
            formatted_items: list[str] = []
            for key, value in ordered_items:
                if str(key) == "alpha":
                    try:
                        formatted_value = f"{float(value):.4f}"
                    except (TypeError, ValueError):
                        formatted_value = str(value)
                else:
                    formatted_value = str(value)
                formatted_items.append(f"{key}={formatted_value}")
            params_text = ", ".join(formatted_items)
            # Use raw print here so alpha retains 4-decimal precision.
            _builtins.print("🧾 ", f"Startup strategy_params: {params_text}")
        else:
            print("🧾 ", "Startup strategy_params: none")

        position_queue_snapshot = getattr(self, "_position_queue", {})
        if isinstance(position_queue_snapshot, dict):
            queue_text = str(position_queue_snapshot)
        else:
            queue_text = "{}"
        _builtins.print("📦 ", f"Startup position_queue: {queue_text}")
        print()

    def _build_message_csv_path(self, message_kind: str) -> Path:
        return _reporting_helpers.build_message_csv_path(self, message_kind)

    def _print_heartbeat_csv_path(self):
        return _reporting_helpers.print_heartbeat_csv_path(self)

    def _append_message_csv(self, minute_text: str, message_text: str, message_kind: str):
        return _reporting_helpers.append_message_csv(self, minute_text, message_text, message_kind)

    @staticmethod
    def _normalize_console_csv_message_fields(message_text: str) -> str:
        return _reporting_helpers.normalize_console_csv_message_fields(message_text)

    @staticmethod
    def _fmt_optional_number(value: Any, precision: int = 6) -> str:
        return _fmt_optional_number(value, precision)

    def _extract_symbol_indicators(self, symbol: str) -> dict[str, Any]:
        symbol_key = self._normalize_symbol(symbol)
        indicator_snapshot: dict[str, Any] = {
            "zscore": None,
            "ema": None,
            "volatility": None,
            "target": None,
            "entry_target": None,
            "reference_price": None,
            "market_open_waiting": None,
            "market_open_time": None,
            "direction_confirmation_streak": None,
            "direction_confirmation_sign": None,
            "direction_confirmation_waiting": None,
            "last_direction_sign": None,
            "outside_range_streak": None,
            "outside_range_sign": None,
            "pending_order_waiting": None,
            "pending_order_side": None,
            "pending_order_target_position": None,
            "pullback_waiting": None,
            "last_return": None,
            "last_return_sign": None,
        }

        hint = self.latest_execution_hints.get(symbol_key, {})
        if isinstance(hint, dict):
            indicator_snapshot["zscore"] = hint.get("zscore")
            indicator_snapshot["ema"] = hint.get("ema")
            indicator_snapshot["volatility"] = hint.get("volatility")
            indicator_snapshot["target"] = hint.get("target")
            indicator_snapshot["entry_target"] = hint.get("entry_target")
            indicator_snapshot["reference_price"] = hint.get("reference_price")
            indicator_snapshot["market_open_waiting"] = hint.get("market_open_waiting")
            indicator_snapshot["market_open_time"] = hint.get("market_open_time")
            indicator_snapshot["direction_confirmation_streak"] = hint.get("direction_confirmation_streak")
            indicator_snapshot["direction_confirmation_sign"] = hint.get("direction_confirmation_sign")
            indicator_snapshot["direction_confirmation_waiting"] = hint.get("direction_confirmation_waiting")
            indicator_snapshot["last_direction_sign"] = hint.get("last_direction_sign")
            indicator_snapshot["outside_range_streak"] = hint.get("outside_range_streak")
            indicator_snapshot["outside_range_sign"] = hint.get("outside_range_sign")
            indicator_snapshot["pending_order_waiting"] = hint.get("pending_order_waiting")
            indicator_snapshot["pending_order_side"] = hint.get("pending_order_side")
            indicator_snapshot["pending_order_target_position"] = hint.get("pending_order_target_position")
            indicator_snapshot["pullback_waiting"] = hint.get("pullback_waiting")
            indicator_snapshot["last_return"] = hint.get("last_return")
            indicator_snapshot["last_return_sign"] = hint.get("last_return_sign")

        if all(indicator_snapshot.get(k) is not None for k in ("zscore", "ema", "volatility")):
            return indicator_snapshot

        for fn in self.strategy_functions:
            module_name = str(getattr(fn, "__module__", "") or "").strip()
            if not module_name:
                continue
            try:
                module = importlib.import_module(module_name)
            except Exception:
                continue

            state_by_symbol = getattr(module, "_STATE_BY_SYMBOL", None)
            if not isinstance(state_by_symbol, dict):
                continue
            state = state_by_symbol.get(symbol_key)
            if state is None:
                continue

            indicators = getattr(state, "indicators", None)
            if not isinstance(indicators, dict):
                continue

            if indicator_snapshot.get("zscore") is None:
                indicator_snapshot["zscore"] = indicators.get("zscore")
            if indicator_snapshot.get("ema") is None:
                indicator_snapshot["ema"] = indicators.get("ema")
            if indicator_snapshot.get("volatility") is None:
                indicator_snapshot["volatility"] = indicators.get("volatility")
            if indicator_snapshot.get("target") is None:
                indicator_snapshot["target"] = indicators.get("target")
            if indicator_snapshot.get("entry_target") is None:
                indicator_snapshot["entry_target"] = indicators.get("entry_target")
            if indicator_snapshot.get("reference_price") is None:
                indicator_snapshot["reference_price"] = indicators.get("reference_price")
            if indicator_snapshot.get("market_open_waiting") is None:
                indicator_snapshot["market_open_waiting"] = indicators.get("market_open_waiting")
            if indicator_snapshot.get("market_open_time") is None:
                indicator_snapshot["market_open_time"] = indicators.get("market_open_time")
            if indicator_snapshot.get("direction_confirmation_streak") is None:
                indicator_snapshot["direction_confirmation_streak"] = indicators.get("direction_confirmation_streak")
            if indicator_snapshot.get("direction_confirmation_sign") is None:
                indicator_snapshot["direction_confirmation_sign"] = indicators.get("direction_confirmation_sign")
            if indicator_snapshot.get("direction_confirmation_waiting") is None:
                indicator_snapshot["direction_confirmation_waiting"] = indicators.get("direction_confirmation_waiting")
            if indicator_snapshot.get("last_direction_sign") is None:
                indicator_snapshot["last_direction_sign"] = indicators.get("last_direction_sign")
            if indicator_snapshot.get("outside_range_streak") is None:
                indicator_snapshot["outside_range_streak"] = indicators.get("outside_range_streak")
            if indicator_snapshot.get("outside_range_sign") is None:
                indicator_snapshot["outside_range_sign"] = indicators.get("outside_range_sign")
            if indicator_snapshot.get("pending_order_waiting") is None:
                indicator_snapshot["pending_order_waiting"] = indicators.get("pending_order_waiting")
            if indicator_snapshot.get("pending_order_side") is None:
                indicator_snapshot["pending_order_side"] = indicators.get("pending_order_side")
            if indicator_snapshot.get("pending_order_target_position") is None:
                indicator_snapshot["pending_order_target_position"] = indicators.get("pending_order_target_position")
            if indicator_snapshot.get("pullback_waiting") is None:
                indicator_snapshot["pullback_waiting"] = indicators.get("pullback_waiting")
            if indicator_snapshot.get("last_return") is None:
                indicator_snapshot["last_return"] = indicators.get("last_return")
            if indicator_snapshot.get("last_return_sign") is None:
                indicator_snapshot["last_return_sign"] = indicators.get("last_return_sign")

            if all(indicator_snapshot.get(k) is not None for k in ("zscore", "ema", "volatility")):
                break

        return indicator_snapshot

    def _create_alpaca_api(self):
        # Overridden by the backtest driver to inject a simulated broker.
        return AlpacAPI()

    def initialize_clients(self):
        self.trading_client, _ = self.alpaca_api.create_trade_clients(env_file=self.env_file)
        strategy_name = str(self.trading_state.strategy_name or self.strategy_params.get("strategy_name", "") or "master_driver").strip()
        output_dir = str(
            self.strategy_params.get("log_dir_name")
            or self.strategy_params.get("LOG_DIR_NAME")
            or self.strategy_params.get("data_dir_name")
            or self.strategy_params.get("DATA_DIR_NAME")
            or ""
        ).strip()
        _reporting_helpers.sync_strategy_daily_file_names(
            self.alpaca_api,
            strategy_name,
            output_dir,
            NY_TZ,
        )

    @staticmethod
    def _is_bar_event(event: dict[str, Any]) -> bool:
        return _is_bar_event(event)

    @staticmethod
    def _normalize_symbol(value: Any) -> str:
        return _normalize_symbol(value)

    @classmethod
    def _event_symbol(cls, event: dict[str, Any]) -> str:
        return _event_symbol(event)

    @staticmethod
    def _event_datetime_ny(event: dict[str, Any], wall_time_ny: datetime | None = None) -> datetime:
        return _event_datetime_ny(event, wall_time_ny=wall_time_ny)

    @staticmethod
    def _event_timing_ny(
        event: dict[str, Any],
        wall_time_ny: datetime | None = None,
    ) -> tuple[datetime, tuple[int, int, int, int, int], float]:
        return _event_timing_ny(event, wall_time_ny=wall_time_ny)

    @staticmethod
    def _event_minute_key(event: dict[str, Any]) -> tuple[int, int, int, int, int]:
        return _event_minute_key(event)

    @staticmethod
    def _minute_to_str(minute_key: tuple[int, int, int, int, int]) -> str:
        return _minute_to_str(minute_key)

    @staticmethod
    def _parse_hhmm_or_default(raw_value: Any, default_hhmm: str):
        return _parse_hhmm_or_default(raw_value, default_hhmm)

    @staticmethod
    def _optional_ws_float_env(name: str, default: float | None) -> float | None:
        raw_value = str(os.getenv(name, "")).strip()
        if not raw_value:
            return default

        lowered = raw_value.lower()
        if lowered in {"none", "off", "false", "disable", "disabled"}:
            return None

        try:
            parsed = float(raw_value)
        except ValueError:
            return default

        if parsed <= 0.0:
            return None
        return parsed

    def _proxy_ws_connect_kwargs(
        self,
        *,
        open_timeout: float | None = None,
        close_timeout: float | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if open_timeout is not None:
            kwargs["open_timeout"] = float(open_timeout)

        resolved_close_timeout = self._optional_ws_float_env("PROXY_WS_CLOSE_TIMEOUT", close_timeout)
        if resolved_close_timeout is not None:
            kwargs["close_timeout"] = float(resolved_close_timeout)

        kwargs["ping_interval"] = self._optional_ws_float_env("PROXY_WS_PING_INTERVAL", None)
        kwargs["ping_timeout"] = self._optional_ws_float_env("PROXY_WS_PING_TIMEOUT", None)
        return kwargs

    def _minute_session_status(self, minute_key: tuple[int, int, int, int, int]) -> tuple[str, str, str]:
        return _minute_session_status(minute_key, self.strategy_params)

    async def preflight_proxy(self):
        """Ensure proxy is reachable and publishing bar events for all required symbols."""
        print("ℹ️ ", f"Preflight: connecting to proxy {self.data_proxy_url}")

        seen_symbols: set[str] = set()
        saw_any_bar = False
        started = datetime.now(NY_TZ)
        no_bar_warning_wait_seconds = max(float(self.preflight_wait_for_bars), 60.0)

        try:
            async with websockets.connect(
                self.data_proxy_url,
                **self._proxy_ws_connect_kwargs(
                    open_timeout=self.preflight_timeout,
                    close_timeout=self.preflight_timeout,
                ),
            ) as ws:
                print("✅ ", "Preflight: websocket connected")

                if self.preflight_connect_only:
                    print("ℹ️ ", "Preflight: connect-only mode enabled; skipping symbol coverage check")
                    return

                while True:
                    elapsed = (datetime.now(NY_TZ) - started).total_seconds()
                    timeout_window = self.preflight_wait_for_bars if saw_any_bar else no_bar_warning_wait_seconds
                    if elapsed > timeout_window:
                        missing = sorted(self.required_symbols - seen_symbols)
                        if not missing:
                            print("✅ ", 
                                "Preflight: all required symbols present "
                                f"{sorted(self.required_symbols)}"
                            )
                            return

                        if saw_any_bar:
                            print(
                                "⚠️ ",
                                "Preflight warning: missing symbols "
                                f"{missing} after {self.preflight_wait_for_bars:.1f}s while receiving bar traffic. "
                                "Continuing and waiting for data in the live stream."
                            )
                            return

                        print("⚠️ ", 
                            "Preflight warning: websocket is reachable but no bar events were observed "
                            f"within {timeout_window:.1f}s. Continuing in connect-only mode. "
                            "If this is unexpected, confirm proxy symbol subscriptions and market activity."
                        )
                        return

                    remaining = max(0.1, timeout_window - elapsed)
                    recv_timeout = min(1.0, remaining)
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=recv_timeout)
                    except asyncio.TimeoutError:
                        # Keep waiting until total preflight window expires.
                        continue

                    data = json.loads(message)
                    events = data if isinstance(data, list) else [data]

                    for event in events:
                        if not isinstance(event, dict):
                            continue
                        if not self._is_bar_event(event):
                            continue
                        saw_any_bar = True
                        sym = self._event_symbol(event)
                        if sym in self.required_symbols:
                            seen_symbols.add(sym)

                    if seen_symbols >= self.required_symbols:
                        print("✅ ", 
                            "Preflight: all required symbols present "
                            f"{sorted(self.required_symbols)}"
                        )
                        return
        except Exception as exc:
            exc_text = str(exc)
            low_text = exc_text.lower()
            if any(token in low_text for token in ["connect call failed", "connection refused", "errno 61", "cannot connect"]):
                print(
                    "⚠️ ",
                    f"Preflight warning: proxy server is not reachable at {self.data_proxy_url}. "
                    "Continuing and waiting for data/reconnect in the live stream."
                )
                return
            print(
                "⚠️ ",
                f"Preflight warning: proxy server is not healthy at {self.data_proxy_url}. {exc}. "
                "Continuing and waiting for data/reconnect in the live stream."
            )
            return

    async def preflight_confirmation_fanout(self):
        """Verify confirmation fanout liveness at startup and return bool."""
        print("ℹ️ ", f"Preflight: connecting to confirmation fanout {self.confirmation_proxy_url}")
        try:
            await _confirmation_stream.verify_confirmation_fanout(
                self.confirmation_proxy_url,
                open_timeout=self.preflight_timeout,
                read_timeout=max(1.0, float(self.preflight_timeout)),
            )
            print("✅ ", f"Preflight: confirmation fanout reachable at {self.confirmation_proxy_url}")
            return True
        except Exception as exc:
            print(
                "⚠️ ",
                f"Startup warning: confirmation stream is not active at {self.confirmation_proxy_url}: {exc}",
            )
            print(
                "ℹ️ ",
                "Attempting to auto-start the shared confirmation owner.",
            )

            owner_process = _confirmation_stream.spawn_confirmation_owner_process(
                env_file=self.env_file,
                listen_url=self.confirmation_proxy_url,
            )
            self._spawned_confirmation_owner_pid = int(owner_process.pid) if owner_process.pid else None
            if self._spawned_confirmation_owner_pid is not None:
                print(
                    "🚀 ",
                    f"Spawned confirmation owner pid={self._spawned_confirmation_owner_pid} "
                    f"for {self.confirmation_proxy_url}",
                )

            deadline = asyncio.get_running_loop().time() + max(5.0, float(self.preflight_timeout))
            last_exc = exc
            while asyncio.get_running_loop().time() < deadline:
                try:
                    await _confirmation_stream.verify_confirmation_fanout(
                        self.confirmation_proxy_url,
                        open_timeout=min(2.0, max(0.5, float(self.preflight_timeout))),
                        read_timeout=min(2.0, max(0.5, float(self.preflight_timeout))),
                    )
                    print(
                        "✅ ",
                        f"Preflight: confirmation fanout reachable at {self.confirmation_proxy_url} after auto-start",
                    )
                    return True
                except Exception as retry_exc:
                    last_exc = retry_exc
                    await asyncio.sleep(0.5)

            print(
                "⚠️ ",
                "Startup warning: confirmation stream is not active. "
                f"Auto-start failed at {self.confirmation_proxy_url}: {last_exc}. "
                "Order confirmations may be delayed or unavailable until the stream is restored.",
            )
            return False

    def _refresh_broker_state(self) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        account_snapshot, positions_snapshot = _state_helpers.refresh_broker_state(self)
        return account_snapshot, positions_snapshot

    def _normalize_strategy_output(self, output: Any) -> list[TradeInstruction]:
        return _normalize_strategy_output(output)

    async def _run_strategies(self, context: StrategyContext) -> dict[str, float]:
        aggregate: dict[str, float] = {}

        # Drop any stale accumulated deltas from previous loops.
        stale_amounts = context.trading_state.consume_strategy_amounts()
        if stale_amounts:
            print("🔔 ", f"Clearing stale strategy amounts before run: {stale_amounts}")
        context.trading_state.consume_strategy_events()

        for fn in self.strategy_functions:
            try:
                raw_output = fn(context)
                if inspect.isawaitable(raw_output):
                    raw_output = await raw_output
            except Exception as _strat_exc:
                fn_name = getattr(fn, "__name__", str(fn))
                print("⚠️ ", f"Strategy callback '{fn_name}' raised an exception: {_strat_exc}")
                raw_output = None

            instructions = self._normalize_strategy_output(raw_output)
            for instruction in instructions:
                if instruction.symbol not in self.required_symbols:
                    continue
                aggregate[instruction.symbol] = aggregate.get(instruction.symbol, 0.0) + float(instruction.qty)

            accumulated = context.trading_state.consume_strategy_amounts()
            if accumulated:
                self._merge_trade_plan(aggregate, accumulated)

            events = context.trading_state.consume_strategy_events()
            for event in events:
                symbol = str(event.get("symbol", "")).upper()
                if symbol in self.required_symbols:
                    metadata = event.get("metadata") or {}
                    if isinstance(metadata, dict):
                        self.latest_execution_hints[symbol] = metadata

        return aggregate

    @staticmethod
    def _normalize_order_status(raw_status: Any) -> str:
        return _normalize_order_status(raw_status)

    def _cancel_opposite_limit_orders(self, symbol: str, incoming_side: OrderSide, strategy_label: str | None = None) -> int:
        return _order_mgmt.cancel_opposite_limit_orders(self, symbol, incoming_side, strategy_label)

    def _cancel_all_limit_orders(
        self,
        symbol: str,
        strategy_label: str | None = None,
        reason: str | None = None,
    ) -> int:
        return _order_mgmt.cancel_all_limit_orders(self, symbol, strategy_label, reason)

    def _cancel_all_open_orders(
        self,
        symbol: str,
        strategy_label: str | None = None,
        reason: str | None = None,
    ) -> int:
        return _order_mgmt.cancel_all_open_orders(self, symbol, strategy_label, reason)

    def _count_open_limit_orders(self, symbol: str, strategy_label: str | None = None) -> int:
        return _order_mgmt.count_open_limit_orders(self, symbol, strategy_label)

    def _use_bar_driven_execution_mode(self) -> bool:
        return True

    def _cancel_tracked_order(self, order_id: str) -> bool:
        return _order_mgmt.cancel_tracked_order(self, order_id)

    def _reconcile_open_orders_once(self):
        if self.trading_client is None or self._open_orders_reconciled:
            return 0
        tracked_count = _order_mgmt.track_strategy_open_orders(self)
        self._open_orders_reconciled = True
        return tracked_count

    def _list_open_limit_orders(self, symbol: str, strategy_label: str | None = None) -> list[str]:
        return _order_mgmt.list_open_limit_orders(self, symbol, strategy_label)

    def _list_open_limit_orders_by_strategy(self) -> dict[str, dict[str, list[float]]]:
        return _order_mgmt.list_open_limit_orders_by_strategy(self)

    @staticmethod
    def _categorize_order_status(raw_status: Any) -> str:
        return _order_mgmt.categorize_order_status(raw_status)

    def _resolve_order_preference(self, symbol: str, side: OrderSide) -> tuple[str, float | None]:
        return _order_mgmt.resolve_order_preference(self, symbol, side)

    def _is_market_open_now(self) -> bool:
        return _order_mgmt.is_market_open_now(self)

    def _print_market_order_closed_warning(self, symbol: str, side: OrderSide, qty: float | None, stage: str):
        return _order_mgmt.print_market_order_closed_warning(self, symbol, side, qty, stage)

    def _rebuild_limit_price_from_live_inputs(self, symbol: str, side: OrderSide) -> float | None:
        return _order_mgmt.rebuild_limit_price_from_live_inputs(self, symbol, side)

    def _enforce_limit_spacing(self, symbol: str, side: OrderSide, proposed_limit_price: float) -> float:
        return _order_mgmt.enforce_limit_spacing(self, symbol, side, proposed_limit_price)

    def _submit_order(self, symbol: str, side: OrderSide, qty: float, order_type: str, limit_price: float | None = None) -> str:
        if self._is_before_strategy_start():
            start_text = str(self.strategy_params.get("start_time", "09:30") or "09:30")
            print(
                "🕒 ",
                f"Order gate: skipping submit before STRATEGY_START_TIME={start_text} "
                f"for symbol={symbol} side={self._normalize_order_status(side)} qty={float(qty):.4f}",
            )
            return ""
        order_id = _order_mgmt.submit_order(self, symbol, side, qty, order_type, limit_price)
        if order_id:
            self._track_submitted_order_id(
                order_id=order_id,
                symbol=str(symbol or ""),
                side=self._normalize_order_status(side),
                order_type=str(order_type or "").strip().lower(),
                qty=float(qty or 0.0),
            )
        else:
            self._record_submit_failure(symbol, side, qty, order_type, limit_price)
        return order_id

    def _record_submit_failure(self, symbol, side, qty, order_type, limit_price):
        symbol_key = self._normalize_symbol(symbol)
        attempt = getattr(self.alpaca_api, "last_submit_attempt", None)
        # The SDK resets this per call; ignore it when it belongs to a different symbol.
        if not isinstance(attempt, dict) or str(attempt.get("symbol", "")).upper() != symbol_key:
            attempt = {}
        rejection = getattr(self, "_last_submit_rejection", None)
        if not isinstance(rejection, dict) or str(rejection.get("symbol", "")).upper() != symbol_key:
            rejection = None
        reason = str(attempt.get("reason", "") or "").strip()
        if not reason and isinstance(rejection, dict):
            reason = str(rejection.get("message", "") or "").strip()
        _reporting_helpers.record_trade_submit_failure(
            self,
            symbol=symbol_key,
            side_text=self._normalize_order_status(side),
            requested_qty=float(qty or 0.0),
            order_type=str(order_type or "").strip().lower(),
            limit_price=limit_price,
            shares_available=attempt.get("shares_available"),
            reason=reason,
            rejection=rejection,
        )

    def _apply_confirmed_fill_to_working_balance(self, order: Any) -> float:
        return _order_mgmt.apply_confirmed_fill_to_working_balance(self, order)

    async def _wait_for_fill(self, order_id: str) -> bool:
        return await _order_mgmt.wait_for_fill(self, order_id)

    async def _wait_for_limit_cancellations(
        self,
        symbol: str,
        strategy_label: str | None = None,
        timeout_seconds: float = 30.0,
        poll_interval_seconds: float = 0.2,
    ) -> bool:
        return await _order_mgmt.wait_for_limit_cancellations(
            self,
            symbol=symbol,
            strategy_label=strategy_label,
            timeout_seconds=timeout_seconds,
            poll_interval_seconds=poll_interval_seconds,
        )

    async def _wait_for_market_order_resolution(self, order_id: str) -> tuple[bool, int]:
        return await _order_mgmt.wait_for_market_order_resolution(self, order_id)

    async def _execute_per_share_take_profit_loop(self, symbol: str, delta_qty: float, hint: dict[str, Any]):
        return await _order_mgmt.execute_per_share_take_profit_loop(self, symbol, delta_qty, hint)

    async def _execute_symbol_delta(self, symbol: str, delta_qty: float, current_qty: float):
        return await _order_mgmt.execute_symbol_delta(self, symbol, delta_qty, current_qty)

    async def _execute_bar_deltas(
        self,
        execution_deltas_by_symbol: dict[str, float],
        positions_snapshot: dict[str, dict],
    ):
        return await _order_mgmt.execute_bar_deltas(self, execution_deltas_by_symbol, positions_snapshot)

    async def _process_minute(self, minute_key: tuple[int, int, int, int, int], bars_for_minute: dict[str, dict]):
        # Carry forward each symbol's last known bar when this minute's bar is missing; use NA when none exists.
        bars_for_minute = _fill_missing_minute_bars(bars_for_minute, self.required_symbols, self._last_known_bar_by_symbol)
        self._processing_minute_key = minute_key
        self._reload_strategy_params_from_env()
        self._reset_daily_trackers_if_new_day(minute_key)
        hold_overnight_enabled = self._hold_overnight_enabled()
        bar_session_status, start_text, end_text = self._minute_session_status(minute_key)
        session_status = bar_session_status

        idle_mode = session_status != "in_session"
        market_is_open_now = self._is_market_open_now()

        # Sync non-fill broker status updates (submit/cancel/reject) before
        # minute-level calculations. Fill mutations are stream-only.
        _reporting_helpers.sync_trade_blotter_broker_updates(self)

        self._reconcile_open_orders_once()

        self.alpaca_api.latest_minute_bars = bars_for_minute
        self._update_daily_symbol_stats(bars_for_minute, session_status)

        # Broker state refresh — wrapped so that any API error (rate-limit, connection
        # timeout, rejection aftermath) never prevents the strategy from running and
        # writing to the state file.
        merged_local_queue: dict[str, list[float]] = {}
        unrealized_by_symbol: dict[str, float] = {}
        total_unrealized_local: float = 0.0
        realized_local_num: float = 0.0
        account_snapshot: dict[str, Any] = {}
        positions_snapshot: dict[str, dict[str, Any]] = {}
        try:
            account_snapshot, positions_snapshot = self._refresh_broker_state()
            self._warn_if_broker_positions_exist_without_local_queue(positions_snapshot)
            merged_local_queue = self._merge_position_queue()
            unrealized_by_symbol, total_unrealized_local = self._compute_unrealized_pnl_from_local_signed_queue(merged_local_queue)
            realized_local_num = self._compute_realized_pnl_from_local_signed_queue()
            account_snapshot["unrealized_pnl_by_symbol"] = dict(unrealized_by_symbol)
            account_snapshot["unrealized_pnl_total"] = float(total_unrealized_local)
            account_snapshot["realized_pnl_local"] = float(realized_local_num)
            positions_snapshot = self._compute_positions_from_local_signed_queue(merged_local_queue, unrealized_by_symbol)
            self._update_intraday_pnl_extremes(account_snapshot)
            if session_status == "after_end":
                self._write_eod_report_if_needed(minute_key, account_snapshot, positions_snapshot)
        except Exception as _broker_state_exc:
            print(
                "⚠️ ",
                f"Broker state refresh failed at minute={self._minute_to_str(minute_key)}: {_broker_state_exc}. "
                "Strategy will run with cached/empty broker state to ensure the state file is updated.",
            )
            _cached_account = getattr(self.alpaca_api, "account_snapshot", None)
            if isinstance(_cached_account, dict) and _cached_account:
                account_snapshot = dict(_cached_account)
            _cached_positions = getattr(self.alpaca_api, "positions_snapshot", None)
            if isinstance(_cached_positions, dict) and _cached_positions:
                positions_snapshot = dict(_cached_positions)
            self._warn_if_broker_positions_exist_without_local_queue(positions_snapshot)
            merged_local_queue = self._merge_position_queue()
            unrealized_by_symbol, total_unrealized_local = self._compute_unrealized_pnl_from_local_signed_queue(merged_local_queue)
            realized_local_num = self._compute_realized_pnl_from_local_signed_queue()
            account_snapshot["unrealized_pnl_by_symbol"] = dict(unrealized_by_symbol)
            account_snapshot["unrealized_pnl_total"] = float(total_unrealized_local)
            account_snapshot["realized_pnl_local"] = float(realized_local_num)
            positions_snapshot = self._compute_positions_from_local_signed_queue(merged_local_queue, unrealized_by_symbol)
            self._update_intraday_pnl_extremes(account_snapshot)
            if session_status == "after_end":
                self._write_eod_report_if_needed(minute_key, account_snapshot, positions_snapshot)

        if session_status == "after_end" and self._claim_eod_trigger(minute_key):
            await self._submit_eod_liquidation_before_strategy(
                minute_key,
                end_text,
                positions_snapshot,
                market_is_open_now=market_is_open_now,
            )

        strategy_params_for_context = dict(self.strategy_params)
        strategy_params_for_context["idle_mode"] = bool(idle_mode)
        strategy_params_for_context["idle_reason"] = session_status if idle_mode else "in_session"
        strategy_params_for_context["eod_flatten"] = False
        if hold_overnight_enabled:
            strategy_params_for_context["hold_overnight"] = True

        # Build effective positions for strategy context from local signed queue only.
        # Do not include pending working balances; each bar should yield a fresh
        # strategy decision and submission plan.
        effective_positions_snapshot: dict[str, dict] = {}
        for _sym_key, _pos_data in positions_snapshot.items():
            _eff = dict(_pos_data)
            effective_positions_snapshot[_sym_key] = _eff
        for _sym_key in sorted(self.required_symbols):
            if _sym_key not in effective_positions_snapshot:
                effective_positions_snapshot[_sym_key] = {"qty": 0.0}

        context = StrategyContext(
            minute_key=minute_key,
            minute_bars=bars_for_minute,
            account=account_snapshot,
            positions=effective_positions_snapshot,
            alpaca_api=self.alpaca_api,
            trading_state=self.trading_state,
            strategy_params=strategy_params_for_context,
        )

        trade_plan = await self._run_strategies(context)

        minute_logs_emitted = False

        def _emit_minute_logs_once():
            nonlocal minute_logs_emitted
            if minute_logs_emitted:
                return
            self._emit_heartbeat(
                minute_text=self._minute_to_str(minute_key),
                merged_local_queue=merged_local_queue,
                unrealized_by_symbol=unrealized_by_symbol,
                realized_local_num=realized_local_num,
                emit_none_price=False,
            )
            minute_logs_emitted = True

        execution_deltas_by_symbol: dict[str, float] = {}

        if session_status == "before_start":
            if trade_plan:
                pending_symbols = [
                    str(symbol)
                    for symbol, delta_qty in trade_plan.items()
                    if abs(float(delta_qty or 0.0)) > 1e-9
                ]
                _order_mgmt.print_trade_gate_summary("before_start", pending_symbols)
        elif session_status == "in_session":
            # Use price-bar timestamp as the sole trading-window gate.
            if bar_session_status != "in_session":
                gated_symbols = [
                    str(symbol)
                    for symbol, delta_qty in trade_plan.items()
                    if abs(float(delta_qty or 0.0)) > 1e-9
                ]
                _order_mgmt.print_trade_gate_summary("bar_timestamp_out_of_window", gated_symbols)
                _emit_minute_logs_once()
                return

            for symbol, delta_qty in trade_plan.items():
                symbol_key = self._normalize_symbol(symbol)
                execution_deltas_by_symbol[symbol_key] = float(
                    execution_deltas_by_symbol.get(symbol_key, 0.0) + float(delta_qty or 0.0)
                )

        # Minute-level strategy messages are emitted by strategy modules.

        if session_status != "in_session":
            if session_status == "before_start":
                print(
                    "🕒 ",
                    f"Outside trading window: before STRATEGY_START_TIME={start_text}; "
                    "skipping order execution while continuing indicator updates.",
                )
                _emit_minute_logs_once()
                return
            elif session_status == "after_end":
                dropped_trade_signals = {
                    str(symbol_key): float(delta_qty)
                    for symbol_key, delta_qty in (trade_plan or {}).items()
                    if abs(float(delta_qty or 0.0)) > 1e-9
                }
                trade_plan = {}
                if dropped_trade_signals:
                    _order_mgmt.print_trade_gate_summary("after_end_time", dropped_trade_signals)

                if not self._eod_flatten_enabled():
                    print(
                        "🕒 ",
                        f"Outside trading window: after STRATEGY_END_TIME={end_text}; "
                        "skipping order execution while continuing indicator updates.",
                    )
                _emit_minute_logs_once()
                return
            elif not market_is_open_now:
                print(
                    "🌙 ",
                    "Closed-market limit mode active: running strategies and repricing limits on each new bar.",
                )
            else:
                gated_symbols = [
                    str(symbol)
                    for symbol, delta_qty in (trade_plan or {}).items()
                    if abs(float(delta_qty or 0.0)) > 1e-9
                ]
                _order_mgmt.print_trade_gate_summary("outside_trading_window", gated_symbols)
                _emit_minute_logs_once()
                return

        await self._execute_bar_deltas(execution_deltas_by_symbol, positions_snapshot)

        _emit_minute_logs_once()

    def _enqueue_minute_processing(self, minute_key: tuple[int, int, int, int, int], bars_for_minute: dict[str, dict]):
        """Queue minute processing in-order without blocking bar-event ingestion."""
        previous_task = self._minute_process_chain_task
        minute_key_snapshot = tuple(minute_key)
        bars_snapshot = dict(bars_for_minute or {})

        async def _run_after_previous():
            if previous_task is not None:
                try:
                    await previous_task
                except asyncio.CancelledError:
                    return
                except KeyboardInterrupt:
                    return
                except Exception:
                    pass
            try:
                await self._process_minute(minute_key_snapshot, bars_snapshot)
            except asyncio.CancelledError:
                return
            except KeyboardInterrupt:
                return

        self._minute_process_chain_task = asyncio.create_task(_run_after_previous())

    async def handle_bar_event(self, event: dict[str, Any]):
        """Per-event callback loop for process_bar(), minute grouping, and orchestration."""
        if not self._is_bar_event(event):
            return

        symbol = self._event_symbol(event)
        if symbol not in self.required_symbols:
            return

        wall_time_ny = datetime.now(NY_TZ)
        self.last_proxy_bar_received_at = wall_time_ny
        self._no_bar_timeout_message_active = False
        bar_time_ny, minute_key, bar_wall_diff_seconds = self._event_timing_ny(event, wall_time_ny=wall_time_ny)
        self._log_price_bar_timestamp_once(bar_time_ny, wall_time_ny)
        skew_warn_threshold = self._safe_float(
            self.strategy_params.get(
                "bar_timestamp_skew_warn_seconds",
                os.getenv("BAR_TIMESTAMP_SKEW_WARN_SECONDS", "120"),
            ),
            default=120.0,
        )
        if skew_warn_threshold < 0.0:
            skew_warn_threshold = 0.0
        skew_warning = _build_bar_timestamp_skew_warning(
            symbol,
            bar_time_ny=bar_time_ny,
            wall_time_ny=wall_time_ny,
            skew_seconds=bar_wall_diff_seconds,
            threshold_seconds=float(skew_warn_threshold),
        )
        if skew_warning:
            print("⚠️ ", skew_warning)

        close_value = event.get("c", event.get("close"))
        if close_value is not None:
            self.latest_symbol_prices[symbol] = float(close_value)
            self.latest_symbol_timestamps[symbol] = bar_time_ny.strftime("%Y-%m-%d %H:%M:%S")

        # Keep API-owned latest bar state updated, but do not fail minute processing
        # if downstream payload shape triggers rare recursion issues.
        try:
            self.alpaca_api.process_bar(event)
        except RecursionError as exc:
            print(
                "⚠️ ",
                f"Bar-state recursion guard: symbol={symbol} error={exc}. Continuing with driver cache state.",
            )

        def _emit_minute_batch_debug(minute_key_value: tuple[int, int, int, int, int], mode: str, bars_payload: dict[str, dict[str, Any]]):
            collected_symbols = sorted(
                {
                    self._normalize_symbol(sym)
                    for sym in (bars_payload or {}).keys()
                    if self._normalize_symbol(sym)
                }
            )
            expected_symbols = sorted(self.required_symbols)
            print(
                "🧪 ",
                f"Minute batch debug: minute={self._minute_to_str(minute_key_value)} mode={mode} "
                f"symbols={len(collected_symbols)}/{len(expected_symbols)} "
                f"collected={collected_symbols}",
            )

        bar_session_status, _, _ = self._minute_session_status(minute_key)
        bar_day_key = f"{minute_key[0]:04d}-{minute_key[1]:02d}-{minute_key[2]:02d}"
        if (
            bar_session_status == "after_end"
            and self._eod_flatten_enabled()
            and self._eod_trigger_day != bar_day_key
        ):
            self.current_minute_key = minute_key
            self.current_minute_bars = {symbol: event}
            self.current_minute_processed = True
            bars_for_minute = dict(self.current_minute_bars)
            _emit_minute_batch_debug(minute_key, "after_end_immediate", bars_for_minute)
            await self._process_minute(minute_key, bars_for_minute)
            return

        if self.current_minute_key is None:
            self.current_minute_key = minute_key
            self.current_minute_processed = False
            self.current_minute_bars = {}

        if minute_key != self.current_minute_key:
            if not self.current_minute_processed and self.current_minute_key is not None:
                pending_bars = dict(self.current_minute_bars)
                _emit_minute_batch_debug(self.current_minute_key, "rollover_batch", pending_bars)
                self._enqueue_minute_processing(self.current_minute_key, pending_bars)
                self.current_minute_processed = True

            self.current_minute_key = minute_key
            self.current_minute_bars = {}
            self.current_minute_processed = False

        self.current_minute_bars[symbol] = event
        if self.current_minute_processed:
            return

        collected_symbol_keys = {
            self._normalize_symbol(sym)
            for sym in self.current_minute_bars.keys()
            if self._normalize_symbol(sym)
        }
        if collected_symbol_keys >= self.required_symbols:
            bars_for_minute = dict(self.current_minute_bars)
            _emit_minute_batch_debug(self.current_minute_key, "full_batch", bars_for_minute)
            self._enqueue_minute_processing(self.current_minute_key, bars_for_minute)
            self.current_minute_processed = True

    async def run(self):
        self.initialize_clients()
        self._load_or_create_position_queue_file()
        self._print_startup_configuration()
        self._print_heartbeat_csv_path()
        confirm_stream_ok = await self.preflight_confirmation_fanout()
        if not confirm_stream_ok:
            print(
                "⚠️ ",
                "Proceeding without active confirmation stream. "
                "Tracked order-ID stale cancellation remains enabled.",
            )
        await self.preflight_proxy()

        print("✅ ", f"Driver started. Listening on {self.data_proxy_url} for symbols={self.symbols}")
        print("✅ ", f"Driver confirmation listener targeting {self.confirmation_proxy_url}")
        confirmation_task = asyncio.create_task(self._confirmation_listener_loop())
        heartbeat_interval = float(
            self.strategy_params.get(
                "heartbeat_interval",
                os.getenv("STRATEGY_HEARTBEAT_INTERVAL", os.getenv("HEARTBEAT_INTERVAL", "60")),
            )
            or 60.0
        )
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(interval_seconds=heartbeat_interval))

        try:
            while True:
                try:
                    async with websockets.connect(
                        self.data_proxy_url,
                        **self._proxy_ws_connect_kwargs(),
                    ) as ws:
                        self._proxy_stream_connected_at = datetime.now(NY_TZ)
                        self._proxy_bar_stale_warning_active = False
                        print("🔌 ", "Connected to proxy stream")
                        async for message in ws:
                            try:
                                data = json.loads(message)
                            except Exception as exc:
                                print("⚠️ ", f"Skipping malformed proxy payload: {exc}")
                                continue
                            events = data if isinstance(data, list) else [data]
                            for event in events:
                                if isinstance(event, dict):
                                    try:
                                        await self.handle_bar_event(event)
                                    except RecursionError as exc:
                                        event_type = event.get("T", event.get("type", "unknown"))
                                        symbol = event.get("S", event.get("symbol", "unknown"))
                                        print(
                                            "⚠️ ",
                                            f"Bar recursion guard: type={event_type} symbol={symbol} error={exc}",
                                        )
                                        continue
                                    except Exception as exc:
                                        event_type = event.get("T", event.get("type", "unknown"))
                                        symbol = event.get("S", event.get("symbol", "unknown"))
                                        print(
                                            "⚠️ ",
                                            f"Skipping bad event: type={event_type} symbol={symbol} error={exc}",
                                        )
                                        continue
                    self._proxy_stream_connected_at = None
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._proxy_stream_connected_at = None
                    print("🔄 ", f"Proxy stream error: {exc}. Reconnecting in 5s...")
                    await asyncio.sleep(5)
        finally:
            confirmation_task.cancel()
            heartbeat_task.cancel()
            if self._minute_process_chain_task is not None:
                self._minute_process_chain_task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(confirmation_task, heartbeat_task, return_exceptions=True),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                print("⚠️ ", "Shutdown timeout while waiting for background tasks; forcing exit.")

            if self._minute_process_chain_task is not None:
                try:
                    await asyncio.wait_for(self._minute_process_chain_task, timeout=2.0)
                except asyncio.CancelledError:
                    pass
                except KeyboardInterrupt:
                    pass
                except Exception:
                    pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Master driver for strategy orchestration")
    parser.add_argument("symbols", nargs="*", help="Symbols expected from proxy stream. If not provided, reads STRATEGY_SYMBOL from env file.")
    parser.add_argument(
        "--strategy",
        action="append",
        default=[],
        help="Strategy function spec in module:function format, for example strat_bollinger_limit:call_back or strat_ratchet_single:call_back. Repeat flag for multiple strategies.",
    )
    parser.add_argument(
        "--strategy-bundle",
        action="append",
        default=[],
        help="Named strategy bundle from strategy_registry.py (for example: core, bollinger, tanaka).",
    )
    parser.add_argument("--data-proxy-url", default=os.getenv("DATA_PROXY_URL", "ws://localhost:8765"))
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE))
    parser.add_argument("--preflight-timeout", type=float, default=10.0)
    parser.add_argument("--preflight-bars-timeout", type=float, default=60.0)
    parser.add_argument(
        "--preflight-connect-only",
        action="store_true",
        help="Only verify websocket connectivity during preflight; do not require immediate bar events.",
    )
    parser.add_argument("--order-fill-timeout", type=float, default=30.0)
    parser.add_argument("--order-fill-poll", type=float, default=0.5)
    parser.add_argument("--alpha", type=float, default=0.1, help="EMA decay parameter (0 < alpha <= 1) for Bollinger strategies.")
    parser.add_argument("--vol-floor", type=float, default=0.05, help="Minimum dollar volatility floor used in Z-score calculations.")
    parser.add_argument("--risk-premium", type=float, default=1.0, help="Risk premium used for Bollinger threshold and limit price adjustment.")
    parser.add_argument(
        "--limit-spread",
        type=float,
        default=1.0,
        help="Absolute dollar spread for limit pricing: buy = current price - limit_spread, sell = current price + limit_spread (default: 1.0).",
    )
    parser.add_argument(
        "--take-profit-threshold",
        type=float,
        default=5.0,
        help="Take-profit multiplier for EMA Bollinger strategy (unrealized_pl > take_profit_threshold * volatility triggers half-position take-profit liquidation).",
    )
    parser.add_argument(
        "--take-profit-factor",
        type=float,
        default=2.0,
        help="Per-share take-profit multiplier for EMA Bollinger strategy (unrealized_pl/abs(position) > take_profit_factor * volatility triggers one-share liquidation).",
    )
    parser.add_argument(
        "--start-time",
        type=str,
        default="09:30",
        help="Strategy trading-window start time in HH:MM (America/New_York). Default: 09:30.",
    )
    parser.add_argument(
        "--end-time",
        type=str,
        default="16:00",
        help="Strategy trading-window end time in HH:MM (America/New_York). Default: 16:00.",
    )
    parser.add_argument(
        "--cancel-stale-order-seconds",
        type=float,
        default=10.0,
        help="Auto-cancel active pending market order after this many seconds (0 disables).",
    )
    parser.add_argument(
        "--eod-flatten",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Liquidate all positions before the end of the trading window. Default: enabled. Use --no-eod-flatten to disable.",
    )
    parser.add_argument(
        "--hold-overnight",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Retain positions overnight without end-of-day liquidation. Default: disabled.",
    )
    parser.add_argument(
        "--suppress-console-messages",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Suppress strategy console print messages. Default: disabled.",
    )
    parser.add_argument(
        "--message-file",
        type=str,
        default="",
        help="Optional csv file path where strategy log messages are appended (columns: minute,message).",
    )
    parser.add_argument(
        "--eod-report-file",
        type=str,
        default="",
        help="Optional csv file path for end-of-day summary rows.",
    )
    parser.add_argument(
        "--strategy-reverse",
        action=argparse.BooleanOptionalAction,
        default=None,
           help="Strategy-owned reverse flag passed through as strategy_reverse. "
               "Strategies may flip target sign when enabled via CLI or STRATEGY_REVERSE.",
    )
    return parser.parse_args()


async def _main_async():
    args = _parse_args()

    # Resolve symbols: CLI first, then env file
    symbols = list(args.symbols) if args.symbols else _resolve_symbols_from_env(args.env_file)
    if not symbols:
        raise ValueError(
            "No symbols provided. Supply symbols as CLI arguments or set STRATEGY_SYMBOLS in the env file. "
            "Example: python3 -m MachineTrader.master_driver SPY NVDA"
        )

    strategy_params = {
        "alpha": args.alpha,
        "vol_floor": args.vol_floor,
        "limit_spread": args.limit_spread,
        "risk_premium": args.risk_premium,
        "take_profit_threshold": args.take_profit_threshold,
        "take_profit_factor": args.take_profit_factor,
        "start_time": args.start_time,
        "end_time": args.end_time,
        "eod_flatten": args.eod_flatten,
        "hold_overnight": args.hold_overnight,
        "suppress_console_messages": args.suppress_console_messages,
        "message_file": args.message_file,
        "eod_report_file": args.eod_report_file,
        "strategy_reverse": bool(args.strategy_reverse) if args.strategy_reverse is not None else False,
    }
    strategy_params = _merge_strategy_params_with_env(strategy_params, args.env_file)
    if args.strategy_reverse is not None:
        strategy_params["strategy_reverse"] = bool(args.strategy_reverse)
    strategy_params["strategy_symbols"] = list(symbols)

    strategy_functions: list[Callable[[StrategyContext], Any]] = []
    strategy_specs: list[str] = []

    if args.strategy_bundle:
        registry = importlib.import_module("strategy_registry")
        bundle_specs = registry.get_bundle_specs(args.strategy_bundle)
        strategy_specs.extend(bundle_specs)

    if args.strategy:
        strategy_specs.extend(args.strategy)

    # Preserve first-seen order while removing duplicates.
    deduped_specs: list[str] = []
    for spec in strategy_specs:
        if spec not in deduped_specs:
            deduped_specs.append(spec)

    if deduped_specs:
        for spec in deduped_specs:
            strategy_functions.append(_load_strategy_callable(spec))
    else:
        strategy_functions = [_default_noop_strategy]
        print("ℹ️ ", "No strategy configured. Running with no-op strategy.")

    driver = MasterDriver(
        symbols=symbols,
        strategy_functions=strategy_functions,
        strategy_labels=deduped_specs if deduped_specs else ["noop"],
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
        runtime_error_help="Master driver exited. Start the proxy server and retry.",
    )


if __name__ == "__main__":
    main()
