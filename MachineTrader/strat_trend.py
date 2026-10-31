"""
strat_trend - An intraday momentum strategy using direct Z-score targets.
==================================================================

Overview
--------
An intraday momentum strategy using the Z-score to set each symbol's target position.
Each minute bar of prices is used to calculate a running Z-score, equal to the deviation from the EMA price divided by the EMA return volatility.
The Z-score indicates whether the price is rich or cheap relative to the EMA price, and is the primary signal for trade decisions.
The strategy sign is 1 when STRATEGY_REVERSE is false and -1 when STRATEGY_REVERSE is true. The target share count is trunc(strategy_sign * zscore * configured quantity / risk premium). Every trade request is the target position minus the current position. A target sign change uses that same rebalance calculation without a separate sign-switch liquidation rule.
Portfolio liquidation (e.g. at STRATEGY_END_TIME when STRATEGY_EOD_FLATTEN is true) is handled exclusively by the master driver, not the strategy module.

This module is signal-only. It calculates target positions and returns trade deltas to the master driver, which owns execution and broker communication.
Strategy parameters are loaded from environment files by the shared driver helpers. The strategy uses MachineTrader.helpers.driver_common for parameter access, logging, per-symbol quantities, and target-position calculations. State CSV output is delegated to MachineTrader.helpers.file_handlers, which owns timestamp handling and file layout.

Trading Logic
-------------
1. Indicator computation - the EMA calculator produces an EMA of return-like
   change plus a return volatility estimate and Z-score for every incoming bar.
2. Target and rebalance intent (before submission gates)
    - Resolve quantity_by_symbol with the shared strategy_quantity_by_symbol helper.
    - Use the shared zscore_target_position helper to calculate
        strategy_sign = 1 when STRATEGY_REVERSE is false, otherwise -1, and
        target = trunc(strategy_sign * zscore * quantity / risk premium).
    - If STRATEGY_POS_CAP (pos_cap) is set, clamp target to [-pos_cap, pos_cap].
    - Return the trade delta equal to the target position minus the current position.
    - A target sign change uses standard rebalancing without a separate sign-switch step.
4. Submission gates for any non-zero delta
     - Z-score must be outside the risk-premium threshold.
         - When STRATEGY_REVERSE is false, require confirmation of at least two
             consecutive outside-range z-scores with the same sign.
         - When STRATEGY_REVERSE is true, require a pullback confirmation: current
             return sign must be opposite to previous return sign.
5. Delta dispatch - record signed trade delta through context.trading_state
    and return the delta to the master driver for order execution.

Examples
--------
Run momentum trend with default .env environment file:

    python3 -m MachineTrader.master_driver SPY \\
        --strategy MachineTrader.strat_trend:call_back


Run momentum trend with custom environment file:

    python3 -m MachineTrader.master_driver SPY \\
        --strategy MachineTrader.strat_trend:call_back \\
        --env-file /tmp/ratchet.env

Backtest one trading day:

    python3 -m MachineTrader.master_backtest \\
        --strategy MachineTrader.strat_trend:call_back \\
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum_trend \\
        --date 2026-09-04

"""

from __future__ import annotations

import math
import MachineTrader.helpers.file_handlers as _file_handlers
from dataclasses import dataclass, field
from typing import Any

from MachineTrader.helpers.calc_ema_class import EMACalculator
from MachineTrader.helpers.timestamp_utils import coerce_market_datetime_ny as _coerce_market_datetime_ny
from MachineTrader.helpers.driver_common import (
    calculate_zscore_target as _calculate_zscore_target,
    cap_target_position as _cap_target_position,
    make_strategy_logger as _make_strategy_logger,
    rounded_print as _rounded_print,
    strategy_dollar_vol_floor as _strategy_dollar_vol_floor,
    strategy_param_bool as _strategy_param_bool,
    strategy_param_float as _strategy_param_float,
    strategy_quantity_by_symbol as _strategy_quantity_by_symbol,
)


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


@dataclass
class MomentumTrendState:
    symbol: str
    alpha: float = 0.99
    vol_floor: float = 0.1
    risk_premium: float = 1.0
    indicators: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.symbol = self.symbol.upper()
        self.emac = EMACalculator()
        self.indicators = {
            "price": None,
            "ema": None,
            "volatility": None,
            "zscore": 0.0,
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
        zscore, ema_price, return_vol = self.emac.calc_zscore_price_return_weighted(
            price_last,
            alpha,
            volume_last,
            dollar_vol_floor,
        )
        self.indicators.update(
            {
                "price_previous": self.indicators.get("price"),
                "price": float(price_last),
                "ema": float(ema_price),
                "volatility": float(return_vol),
                "zscore": float(zscore),
            }
        )
        return True

    def calculate_target(self, context) -> float:
        bar = context.minute_bars.get(self.symbol)
        if not isinstance(bar, dict):
            self.indicators["last_delta"] = 0.0
            return 0.0

        price_last = float(self.indicators["price"])
        ema_price = float(self.indicators["ema"])
        return_vol = float(self.indicators["volatility"])
        zscore = float(self.indicators["zscore"])
        reverse_enabled = _strategy_param_bool(
            context.strategy_params,
            "strategy_reverse",
            False,
            env_key="STRATEGY_REVERSE",
        )
        strategy_log = _make_strategy_logger(
            context.strategy_params,
            context.minute_key,
            timestamp_field="time",
            use_log_dir_name=True,
        )

        risk_premium = _strategy_param_float(
            context.strategy_params,
            "risk_premium",
            self.risk_premium,
            env_key="STRATEGY_RISK_PREMIUM",
        )
        pos_state = context.positions.get(self.symbol, {})
        current_position = float(pos_state.get("qty", 0.0) or 0.0)
        shares_owned = abs(float(current_position))
        quantity = float(_strategy_quantity_by_symbol(context.strategy_params).get(self.symbol, 1.0) or 1.0)
        previous_price = self.indicators.get("price_previous")
        current_return = float(price_last) - float(previous_price) if previous_price is not None else 0.0
        current_return_sign = 1 if current_return > 0 else -1 if current_return < 0 else 0
        previous_return = self.indicators.get("last_return")
        previous_return_value = float(previous_return) if previous_return is not None else 0.0
        previous_return_sign = 1 if previous_return_value > 0 else -1 if previous_return_value < 0 else 0
        signal_sign = 1 if float(zscore) > 0 else -1 if float(zscore) < 0 else 0
        position_sign = 1 if current_position > 0 else -1 if current_position < 0 else 0
        effective_risk_premium = float(risk_premium)
        target = _calculate_zscore_target(
            zscore,
            quantity,
            effective_risk_premium,
            current_position,
            reverse=reverse_enabled,
        )
        pos_cap = _strategy_param_float(
            context.strategy_params,
            "pos_cap",
            0.0,
            env_key="STRATEGY_POS_CAP",
        )
        target_position = _cap_target_position(float(target.target_position), pos_cap)
        position_cap_correction = pos_cap > 0.0 and abs(current_position) > pos_cap
        trunc_zscore = int(math.trunc(float(zscore)))
        trunc_abs_zscore = int(math.trunc(abs(float(zscore))))
        target_sign = 1 if target_position > 0 else -1 if target_position < 0 else 0

        unrealized_pl = float(pos_state.get("unrealized_pl", 0.0) or 0.0)
        pnl_per_share = float(pos_state.get("pnl_per_share", 0.0) or 0.0)

        zscore_outside_range = abs(float(zscore)) > effective_risk_premium
        previous_outside_sign = int(self.indicators.get("outside_range_sign", 0) or 0)
        previous_outside_streak = int(self.indicators.get("outside_range_streak", 0) or 0)
        if zscore_outside_range and signal_sign != 0:
            if signal_sign == previous_outside_sign:
                outside_range_streak = previous_outside_streak + 1
            else:
                outside_range_streak = 1
            outside_range_sign = signal_sign
        else:
            outside_range_streak = 0
            outside_range_sign = 0
        delta = float(target_position) - float(target.current_position)
        no_trade_reason = "position fits zscore"
        pullback_waiting = False
        state_rationale = no_trade_reason

        if delta != 0.0 and not position_cap_correction:
            if not zscore_outside_range:
                no_trade_reason = "z-score not outside risk-premium range"
                strategy_log(
                    "⏸️ ",
                    f"[strat_trend] symbol={self.symbol} no trade: z-score must be outside risk-premium range; "
                    f"zscore={float(zscore):.6f} risk_premium={effective_risk_premium:.6f}",
                )
                delta = 0.0
            elif not reverse_enabled and outside_range_streak < 2:
                no_trade_reason = "waiting for two-bar direction confirmation"
                strategy_log(
                    "⏸️ ",
                    f"[strat_trend] symbol={self.symbol} waiting for direction confirmation before submitting order: "
                    f"outside_range_streak={outside_range_streak} required=2 zscore={float(zscore):.6f} "
                    f"risk_premium={effective_risk_premium:.6f} signal_sign={signal_sign}",
                )
                delta = 0.0
            elif reverse_enabled and (
                current_return_sign == 0
                or previous_return_sign == 0
                or current_return_sign == previous_return_sign
            ):
                pullback_waiting = True
                no_trade_reason = "waiting for pullback"
                strategy_log(
                    "⏸️ ",
                    f"[strat_trend] symbol={self.symbol} waiting for pullback: "
                    f"current_return={current_return:.6f} previous_return={previous_return_value:.6f} "
                    f"current_return_sign={current_return_sign} previous_return_sign={previous_return_sign}",
                )
                delta = 0.0

        self.indicators.update(
            {
                "price": price_last,
                "last_return": float(current_return),
                "last_return_sign": current_return_sign,
                "ema": float(ema_price),
                "volatility": float(return_vol),
                "zscore": float(zscore),
                "configured_quantity": float(quantity),
                "strategy_reverse": bool(reverse_enabled),
                "strategy_sign": int(target.strategy_sign),
                "target": float(target_position),
                "outside_range_streak": int(outside_range_streak),
                "outside_range_sign": int(outside_range_sign),
                "position": current_position,
                "unrealized_pl": unrealized_pl,
                "pnl_per_share": pnl_per_share,
                "risk_premium": float(effective_risk_premium),
                "pos_cap": float(pos_cap),
                "last_delta": delta,
                "pullback_waiting": bool(pullback_waiting),
                "last_rationale": state_rationale if delta != 0.0 else no_trade_reason,
            }
        )

        submit_delta = float(delta)
        if submit_delta != 0.0:
            state_rationale = "signal trade"
            strategy_log(
                "🚀 ",
                f"[strat_trend] symbol={self.symbol} strategy delta: side={'buy' if submit_delta > 0 else 'sell'} qty={abs(float(submit_delta)):.4f}",
            )

            self.indicators["last_rationale"] = state_rationale

        context.trading_state.add_strategy_amount(
            self.symbol,
            submit_delta,
            metadata={
                "strategy": "strat_trend",
                "reason": "target_rebalance" if submit_delta != 0.0 else str(no_trade_reason),
                "order_type": "market",
                "convert_market_to_limit_when_closed": True,
                "minute": context.minute_key,
                "price": price_last,
                "ema": float(ema_price),
                "volatility": float(return_vol),
                "return_vol": float(return_vol),
                "zscore": float(zscore),
                "position": current_position,
                "configured_quantity": float(quantity),
                "strategy_reverse": bool(reverse_enabled),
                "strategy_sign": int(target.strategy_sign),
                "target": float(target_position),
                "unrealized_pl": unrealized_pl,
                "pnl_per_share": pnl_per_share,
                "trunc_zscore": trunc_zscore,
                "trunc_abs_zscore": trunc_abs_zscore,
                "outside_range_streak": int(outside_range_streak),
                "outside_range_sign": int(outside_range_sign),
            },
        )

        return delta

    def on_minute(self, context) -> float:
        if not self.calculate_indicators(context):
            return 0.0
        return self.calculate_target(context)


_STATE_BY_SYMBOL: dict[str, MomentumTrendState] = {}


def _print_symbol_summary(context, symbol_key: str, delta: float, timestamp_text: str) -> None:
    indicators = _STATE_BY_SYMBOL[symbol_key].indicators
    current_position = float(context.positions.get(symbol_key, {}).get("qty", 0.0) or 0.0)
    target_position = float(indicators.get("target", current_position) or 0.0)
    if delta > 0.0:
        share_amount = f"buy {abs(float(delta)):.6f}"
    elif delta < 0.0:
        share_amount = f"sell {abs(float(delta)):.6f}"
    else:
        share_amount = "none"

    print(
        "📊 ",
        f"price_bar_timestamp={timestamp_text} | symbol={symbol_key} | "
        f"price={float(indicators['price']):.6f} | current_position={current_position:.6f} | "
        f"target_position={target_position:.6f} | buy_or_sell_share_amount={share_amount}",
    )


def call_back(context):
    """Master-driver strategy callback.

    Usage:
        --strategy MachineTrader.strat_trend:call_back
    """
    configured_symbols = [
        str(symbol).strip().upper()
        for symbol in context.strategy_params.get("strategy_symbols", [])
        if str(symbol).strip()
    ]
    symbols_to_process = sorted(dict.fromkeys(configured_symbols or context.minute_bars.keys()))
    received_symbols = sorted(_file_handlers.symbols_with_new_price_bars(context.minute_bars))
    first_bar = context.minute_bars.get(received_symbols[0], {}) if received_symbols else {}
    raw_timestamp = first_bar.get("t", first_bar.get("timestamp")) if isinstance(first_bar, dict) else None
    bar_timestamp = _coerce_market_datetime_ny(raw_timestamp, fallback_to_now=False)
    timestamp_text = bar_timestamp.strftime("%Y-%m-%d %H:%M:%S") if bar_timestamp is not None else "NA"
    zscores_by_symbol: dict[str, float | None] = {}
    ema_by_symbol: dict[str, float | None] = {}
    volatility_by_symbol: dict[str, float | None] = {}

    for symbol_key in symbols_to_process:
        if symbol_key not in _STATE_BY_SYMBOL:
            _STATE_BY_SYMBOL[symbol_key] = MomentumTrendState(symbol=symbol_key)
        if symbol_key not in received_symbols or not _STATE_BY_SYMBOL[symbol_key].calculate_indicators(context):
            zscores_by_symbol[symbol_key] = None
            ema_by_symbol[symbol_key] = None
            volatility_by_symbol[symbol_key] = None
            continue
        indicators = _STATE_BY_SYMBOL[symbol_key].indicators
        zscores_by_symbol[symbol_key] = float(indicators["zscore"])
        ema_by_symbol[symbol_key] = float(indicators["ema"])
        volatility_by_symbol[symbol_key] = float(indicators["volatility"])

    _file_handlers.append_strategy_symbol_indicator_csvs(
        context,
        minute_bars=context.minute_bars,
        zscores_by_symbol=zscores_by_symbol,
        symbol_order=symbols_to_process,
        ema_by_symbol=ema_by_symbol,
        volatility_by_symbol=volatility_by_symbol,
    )

    for symbol_key in symbols_to_process:
        if symbol_key in received_symbols:
            delta = float(_STATE_BY_SYMBOL[symbol_key].calculate_target(context) or 0.0)
            _print_symbol_summary(context, symbol_key, delta, timestamp_text)

    return None
