"""
strat_sharpema - Portfolio momentum strategy driven by EMA Sharpe ratios.
========================================================================

Overview
--------
A portfolio-level momentum strategy that scores each configured symbol using
the EMA Sharpe ratio returned by ``calc_sharpema()``. The strategy converts
that signal into a target share count by scaling it with the configured
quantity and risk-premium factor, then returns the delta needed to reach that
target position.

This module is signal-only. It depends on the master_momentum for execution and
has no direct broker connection. Shared master driver helpers own state-file
output.

Trading Logic
-------------
1. Indicator computation - for each symbol, ``calc_sharpema()`` updates the
    EMA return and return volatility, and calculates ``sharpema = ema_return /
    return_vol``.
2. Driver-owned EOD flatten - end-of-day liquidation is handled by the shared
    master driver helpers at STRATEGY_END_TIME; this strategy only emits
    rebalance intents.
3. Position targeting - the strategy maps each symbol to its configured
    quantity and calculates the target share count as:
    ``trunc(strategy_sign * sharpema * quantity / risk_premium)`` where
    ``strategy_sign`` is -1 when ``STRATEGY_REVERSE`` is true, otherwise 1.
   If STRATEGY_POS_CAP (pos_cap) is set, target_shares is clamped to
   [-pos_cap, pos_cap].
4. Rebalancing - each minute the current position is compared with the target
   position, and the resulting delta is submitted as a market-order intent.
5. Continuous calculation - sharpema values and rebalance deltas keep updating before
   STRATEGY_START_TIME and after STRATEGY_END_TIME as long as price bars keep
   arriving; the shared master driver is responsible for gating execution to
   the configured trading window.

Examples
--------
Run momentum with a custom environment file:

    python3 -m MachineTrader.master_momentum \\
        --strategy MachineTrader.strat_sharpema:call_back \\
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum

Run momentum with a custom symbol list and per-symbol quantities:

    python3 -m MachineTrader.master_momentum SPY \\
        --strategy MachineTrader.strat_sharpema:call_back \\
        --strategy-symbols AAPL,MSFT,TSLA \\
        --strategy-param quantity_by_symbol='{"AAPL":2,"MSFT":1,"TSLA":1}'

Run momentum with a custom risk premium:

    python3 -m MachineTrader.master_momentum SPY \\
        --strategy MachineTrader.strat_sharpema:call_back \\
        --strategy-param risk_premium=2.0

Backtest one trading day:

    python3 -m MachineTrader.master_backtest \\
        --strategy MachineTrader.strat_sharpema:call_back \\
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum \\
        --date 2026-09-04

"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import MachineTrader.helpers.file_handlers as _file_handlers
from MachineTrader.helpers.calc_ema_class import EMACalculator
from MachineTrader.helpers.driver_common import (
    calculate_zscore_target as _calculate_zscore_target,
    cap_target_position as _cap_target_position,
    rounded_print as _rounded_print,
    strategy_dollar_vol_floor as _strategy_dollar_vol_floor,
    strategy_param_bool as _strategy_param_bool,
    strategy_param_float as _strategy_param_float,
    strategy_quantity_by_symbol as _strategy_quantity_by_symbol,
)


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


@dataclass
class MomentumState:
    symbol: str
    alpha: float = 0.99
    vol_floor: float = 0.1
    indicators: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.symbol = self.symbol.upper()
        self.emac = EMACalculator()
        self.indicators = {
            "price": None,
            "ema_return": None,
            "volatility": None,
            "sharpema": 0.0,
            "position": 0.0,
            "target": 0.0,
            "last_delta": 0.0,
        }

    def calculate_indicators(self, context) -> bool:
        bar = context.minute_bars.get(self.symbol)
        if not isinstance(bar, dict):
            self.indicators["last_delta"] = 0.0
            return False

        raw_price = bar.get("c", bar.get("close"))
        if raw_price is None:
            self.indicators["last_delta"] = 0.0
            return False
        price_last = float(raw_price)
        volume_last = float(bar.get("v", bar.get("volume", 1.0)) or 1.0)
        alpha = _strategy_param_float(context.strategy_params, "alpha", self.alpha)
        dollar_vol_floor = _strategy_dollar_vol_floor(context.strategy_params, price_last, self.vol_floor)

        sharpema, ema_return, return_vol = self.emac.calc_sharpema(
            price_last,
            alpha,
            volume_last,
            dollar_vol_floor,
        )
        self.indicators.update(
            {
                "price": float(price_last),
                "ema_return": float(ema_return),
                "volatility": float(return_vol),
                "sharpema": float(sharpema),
            }
        )
        return True

    def calculate_target(self, context) -> float:
        price_last = float(self.indicators["price"])
        ema_return = float(self.indicators["ema_return"])
        return_vol = float(self.indicators["volatility"])
        sharpema = float(self.indicators["sharpema"])

        qty_map = _strategy_quantity_by_symbol(context.strategy_params)
        quantity = float(qty_map.get(self.symbol, 1.0) or 1.0)
        risk_premium_raw = _strategy_param_float(
            context.strategy_params,
            "risk_premium",
            1.0,
            env_key="STRATEGY_RISK_PREMIUM",
        )
        risk_premium = float(risk_premium_raw) if float(risk_premium_raw) != 0.0 else 1.0
        current_position = float(context.positions.get(self.symbol, {}).get("qty", 0.0) or 0.0)
        reverse_enabled = _strategy_param_bool(
            context.strategy_params,
            "strategy_reverse",
            False,
            env_key="STRATEGY_REVERSE",
        )
        target = _calculate_zscore_target(
            sharpema,
            quantity,
            risk_premium,
            current_position,
            reverse=reverse_enabled,
        )
        target_position = float(target.target_position)
        pos_cap = _strategy_param_float(
            context.strategy_params,
            "pos_cap",
            0.0,
            env_key="STRATEGY_POS_CAP",
        )
        target_position = _cap_target_position(target_position, pos_cap)
        delta = target_position - float(target.current_position)
        rebalance_reason = "sharpema_target_rebalance"

        self.indicators.update(
            {
                "price": float(price_last),
                "ema_return": float(ema_return),
                "volatility": float(return_vol),
                "sharpema": float(sharpema),
                "position": float(current_position),
                "target": float(target_position),
                "last_delta": float(delta),
            }
        )

        context.trading_state.add_strategy_amount(
            self.symbol,
            float(delta),
            metadata={
                "strategy": "strat_sharpema",
                "reason": str(rebalance_reason),
                "order_type": "market",
                "convert_market_to_limit_when_closed": True,
                "minute": context.minute_key,
                "price": float(price_last),
                "ema_return": float(ema_return),
                "volatility": float(return_vol),
                "return_vol": float(return_vol),
                "sharpema": float(sharpema),
                "zscore": float(sharpema),
                "position": float(current_position),
                "target": float(target_position),
                "configured_quantity": float(quantity),
                "risk_premium": float(risk_premium),
                "pos_cap": float(pos_cap),
                "scaled_signal": float(target.scaled_signal),
                "trunc_sharpema": int(math.trunc(float(sharpema))),
            },
        )

        return float(delta)

    def on_minute(self, context) -> float:
        if not self.calculate_indicators(context):
            return 0.0
        return self.calculate_target(context)


_STATE_BY_SYMBOL: dict[str, MomentumState] = {}


def _strategy_name(context) -> str:
    return str(
        getattr(context.trading_state, "strategy_name", "")
        or context.strategy_params.get("strategy_name", "")
        or "master_driver"
    ).strip()


def _minute_text_from_context(context) -> str:
    minute_key = getattr(context, "minute_key", None)
    if isinstance(minute_key, tuple) and len(minute_key) == 5:
        year, month, day, hour, minute = minute_key
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d} {int(hour):02d}:{int(minute):02d}:00"
    return "unknown"


def _print_requested_shares_state_message(context, requested_shares_by_symbol: dict[str, float], submitted_orders: int):
    non_zero = [
        f"{symbol}={float(delta):+.0f}"
        for symbol, delta in sorted(requested_shares_by_symbol.items())
        if abs(float(delta)) > 1e-9
    ]
    requested_text = " ".join(non_zero) if non_zero else "none"
    print(
        "📊 ",
        f"symbol={_strategy_name(context)} | requested_shares={requested_text} | order={int(submitted_orders)}",
    )


def call_back(context):
    """Master-driver strategy callback.

    Usage:
        --strategy MachineTrader.strat_sharpema:call_back
    """
    sharpema_by_symbol: dict[str, float | None] = {}
    ema_by_symbol: dict[str, float | None] = {}
    volatility_by_symbol: dict[str, float | None] = {}
    requested_shares_by_symbol: dict[str, float] = {}
    submitted_orders = 0

    configured_symbols_raw = context.strategy_params.get("strategy_symbols", []) if isinstance(context.strategy_params, dict) else []
    configured_symbols = [str(symbol).strip().upper() for symbol in configured_symbols_raw if str(symbol).strip()]
    symbols_to_process = sorted(dict.fromkeys(configured_symbols)) if configured_symbols else sorted(context.minute_bars.keys())
    received_symbols = sorted(_file_handlers.symbols_with_new_price_bars(context.minute_bars))
    missing_symbols = [symbol for symbol in symbols_to_process if symbol not in received_symbols]
    print(
        "🧪 ",
        f"Minute batch debug: strategy={_strategy_name(context)} minute={_minute_text_from_context(context)} "
        f"symbols={len(received_symbols)}/{len(symbols_to_process)} "
        f"missing={missing_symbols if missing_symbols else 'none'}",
    )

    for symbol in symbols_to_process:
        symbol_key = str(symbol).upper()
        if symbol_key not in _STATE_BY_SYMBOL:
            _STATE_BY_SYMBOL[symbol_key] = MomentumState(symbol=symbol_key)
        if symbol_key not in received_symbols or not _STATE_BY_SYMBOL[symbol_key].calculate_indicators(context):
            sharpema_by_symbol[symbol_key] = None
            ema_by_symbol[symbol_key] = None
            volatility_by_symbol[symbol_key] = None
            continue
        indicators = _STATE_BY_SYMBOL[symbol_key].indicators
        sharpema_by_symbol[symbol_key] = float(indicators["sharpema"])
        ema_by_symbol[symbol_key] = float(indicators["ema_return"])
        volatility_by_symbol[symbol_key] = float(indicators["volatility"])

    _file_handlers.append_strategy_symbol_indicator_csvs(
        context,
        minute_bars=context.minute_bars,
        zscores_by_symbol=sharpema_by_symbol,
        symbol_order=symbols_to_process,
        ema_by_symbol=ema_by_symbol,
        volatility_by_symbol=volatility_by_symbol,
    )

    for symbol_key in symbols_to_process:
        if symbol_key not in received_symbols:
            requested_shares_by_symbol[symbol_key] = 0.0
            continue
        delta = float(_STATE_BY_SYMBOL[symbol_key].calculate_target(context) or 0.0)
        requested_shares_by_symbol[symbol_key] = delta
        if abs(delta) > 1e-9:
            submitted_orders += 1

    _print_requested_shares_state_message(context, requested_shares_by_symbol, submitted_orders)
    return None
