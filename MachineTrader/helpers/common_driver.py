"""Behavior shared by live, momentum, backtest, and pairs drivers.

This module is intentionally small during the first driver migration step.
Execution and position accounting remain in ``MasterDriver`` until each slice
can be moved and validated independently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from MachineTrader.helpers.driver_common import merge_strategy_params_with_env
from MachineTrader.helpers.driver_common import read_env_file_if_changed
from MachineTrader.helpers.driver_common import NY_TZ
from MachineTrader.helpers.parse_args import resolve_symbol_quantity_map_from_env


class CommonDriver:
    """Base behavior shared by all driver variants."""

    def _reload_strategy_params_from_env(self) -> None:
        """Reload environment-backed strategy parameters when the env file changes."""
        env_file = getattr(self, "env_file", None)
        if not env_file:
            return

        previous_signature = getattr(self, "_env_file_signature", None)
        _env_values, signature = read_env_file_if_changed(env_file, previous_signature)
        self._env_file_signature = signature
        if _env_values is None:
            return
        # An unreadable env file (e.g. mid atomic rewrite) must not reset live params.
        if signature == (-1, -1):
            return

        old_params = dict(getattr(self, "strategy_params", {}) or {})
        base_params = dict(old_params)
        env_params = merge_strategy_params_with_env({}, self.env_file)
        for key, value in env_params.items():
            if value not in (None, ""):
                base_params[key] = None
        reloaded = merge_strategy_params_with_env(base_params, self.env_file)
        if reloaded != old_params:
            self.strategy_params = reloaded
            changed_keys = sorted(set(old_params) | set(reloaded))
            changed_fields: list[tuple[str, Any, Any]] = []
            for key in changed_keys:
                old_value = old_params.get(key)
                new_value = reloaded.get(key)
                if old_value != new_value:
                    changed_fields.append((key, old_value, new_value))

            print("♻️ ", f"Env-file reload applied strategy params from {self.env_file}:")
            for key, old_value, new_value in changed_fields:
                print("   ", f"{key}: old={old_value}")
                print("   ", f"{key}: new={new_value}")
                updated_values = {key: new_value for key, _, new_value in changed_fields}
                print("♻️ ", f"Updated parameters: {updated_values}")
            print()

        current_params = self.strategy_params
        current_quantity_map = current_params.get("quantity_by_symbol")
        if not isinstance(current_quantity_map, dict):
            return
        try:
            _env_symbols, env_quantity_map = resolve_symbol_quantity_map_from_env(self.env_file)
        except ValueError as exc:
            print("⚠️ ", f"Unable to reload STRATEGY_QUANTITY from {self.env_file}: {exc}")
            return

        updated_quantity_map = dict(current_quantity_map)
        active_symbols = set(getattr(self, "required_symbols", set()))
        if not active_symbols:
            active_symbols = {str(symbol).strip().upper() for symbol in getattr(self, "symbols", [])}
        for symbol in active_symbols:
            if symbol in env_quantity_map:
                updated_quantity_map[symbol] = env_quantity_map[symbol]
        if updated_quantity_map != current_quantity_map:
            current_params["quantity_by_symbol"] = updated_quantity_map
            print("♻️ ", f"Env-file reload applied STRATEGY_QUANTITY from {self.env_file}:")
            print("   ", f"quantity_by_symbol: old={current_quantity_map}")
            print("   ", f"quantity_by_symbol: new={updated_quantity_map}")
            print("♻️ ", f"Updated parameters: {{'quantity_by_symbol': {updated_quantity_map}}}")
            print()

    def _queue_payload(self) -> dict[str, Any]:
        """Serialize the local position queues and realized PnL for persistence."""
        normalize_symbol = self._normalize_symbol
        required_symbols = getattr(self, "required_symbols", set())
        realized_by_symbol = {
            normalize_symbol(symbol_key): float(value or 0.0)
            for symbol_key, value in (getattr(self, "_local_realized_pnl_by_symbol", {}) or {}).items()
            if normalize_symbol(symbol_key)
        }
        realized_total = float(
            sum(float(realized_by_symbol.get(symbol_key, 0.0) or 0.0) for symbol_key in sorted(required_symbols))
        )
        payload: dict[str, Any] = {
            "updated_at": datetime.now(NY_TZ).isoformat(),
            "symbols": list(getattr(self, "symbols", [])),
            "position_queue": {
                normalize_symbol(symbol_key): [float(value) for value in values]
                for symbol_key, values in (getattr(self, "_position_queue", {}) or {}).items()
                if normalize_symbol(symbol_key) and isinstance(values, list)
            },
            "local_realized_pnl_total": realized_total,
            "local_realized_pnl_by_symbol": realized_by_symbol,
        }
        if hasattr(self, "_pair_position_queue_prices"):
            pair_queue = getattr(self, "_pair_position_queue_prices", [])
            if isinstance(pair_queue, list):
                payload["pair_position_queue_prices"] = [float(value) for value in pair_queue]
        return payload

    def _track_submitted_order_id(
        self,
        *,
        order_id: str,
        symbol: str,
        side: str,
        order_type: str,
        qty: float,
    ) -> None:
        """Track a submitted order by broker ID until its terminal event."""
        order_key = str(order_id or "").strip()
        symbol_key = self._normalize_symbol(symbol)
        if not order_key or not symbol_key:
            return
        self._tracked_open_order_ids[order_key] = {
            "symbol": symbol_key,
            "side": str(side or "").strip().lower(),
            "order_type": str(order_type or "").strip().lower(),
            "qty": float(qty or 0.0),
            "delta": float(qty or 0.0) * (1.0 if str(side or "").strip().lower() == "buy" else -1.0),
            "submitted_at": datetime.now(NY_TZ),
        }
        last_delta_by_symbol = getattr(self, "_last_delta_by_symbol", None)
        if not isinstance(last_delta_by_symbol, dict):
            last_delta_by_symbol = {}
            self._last_delta_by_symbol = last_delta_by_symbol
        last_delta_by_symbol[symbol_key] = self._tracked_open_order_ids[order_key]["delta"]

    def _drop_tracked_order_id(self, order_id: str) -> None:
        """Stop tracking an order after a terminal broker event."""
        order_key = str(order_id or "").strip()
        if order_key:
            self._tracked_open_order_ids.pop(order_key, None)

    def _tracked_open_order_for_symbol(self, symbol: str) -> tuple[str, dict[str, Any]] | None:
        """Return one in-flight order for symbol, if any."""
        tracked_orders = self._tracked_open_orders_for_symbol(symbol)
        return tracked_orders[0] if tracked_orders else None

    def _tracked_open_orders_for_symbol(self, symbol: str) -> list[tuple[str, dict[str, Any]]]:
        """Return all in-flight orders for symbol."""
        symbol_key = self._normalize_symbol(symbol)
        tracked_orders: list[tuple[str, dict[str, Any]]] = []
        for order_id, metadata in self._tracked_open_order_ids.items():
            if not isinstance(metadata, dict):
                continue
            if self._normalize_symbol(metadata.get("symbol")) == symbol_key:
                tracked_orders.append((str(order_id), dict(metadata)))
        return tracked_orders

    def _latest_broker_order_update(self, order_id: str) -> dict[str, Any] | None:
        """Return the latest broker payload for an order, if one was received."""
        order_key = str(order_id or "").strip()
        if not order_key:
            return None
        payload = self._broker_order_updates_by_id.get(order_key)
        return dict(payload) if isinstance(payload, dict) else None