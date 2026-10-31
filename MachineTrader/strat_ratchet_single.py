"""
strat_ratchet - An intraday mean-reversion strategy using the Z-score as a rich/cheap indicator and market orders.
==================================================================

Overview
--------
An intraday mean-reversion strategy using the Z-score as a rich/cheap indicator.
Each minute bar of prices is used to calculate a running Z-score, equal to the deviation from the EMA price divided by the EMA return volatility.
The Z-score indicates whether the price is rich or cheap relative to the EMA price, and is the primary signal for trade decisions.
If the price moves significantly above or below the EMA price, and the Z-score exceeds the risk-premium threshold, then the strategy takes a contrarian position. 
If the Z-score continues to grow, the strategy doubles down and adds to the position (it ratchets up). The strategy sign is 1 when STRATEGY_REVERSE is false and -1 when STRATEGY_REVERSE is true. The notional share count is trunc(strategy_sign * zscore * configured quantity / risk premium). Positive notionals can only raise a same-sign target position and negative notionals can only lower it. If the notional changes sign, the target is the notional so the submitted delta closes the current position and opens the new position. The position can also be exited or trimmed by a take-profit rule.
Portfolio liquidation (e.g. at STRATEGY_END_TIME when STRATEGY_EOD_FLATTEN is true) is handled exclusively by the master driver, not the strategy module.

This module is signal-only. It calculates target positions and returns trade deltas to the master driver, which owns execution and broker communication.
Strategy parameters are loaded from environment files by the shared driver helpers. The strategy uses MachineTrader.helpers.driver_common for parameter access, logging, per-symbol quantities, and target-position calculations. State CSV output is delegated to MachineTrader.helpers.file_handlers, which owns timestamp handling and file layout.

Trading Logic
-------------
1. Indicator computation - the EMA calculator produces an EMA of return-like
   change plus a return volatility estimate and Z-score for every incoming bar.
2. Take-profit rules - checked before new entries.
     - Per-position rule: use driver-provided per-position unrealized snapshot metrics
         and identify all positions whose unrealized PnL exceeds
         take_profit_factor x volatility. Close all qualifying positions by
         returning their closing delta to the master driver.
     - Aggregate rule: if driver-provided unrealized_pl > take_profit_threshold x volatility,
         return a delta to close half the current position.
     - Chaining: after any take-profit delta is filled by the driver, remaining
         lots are re-evaluated on subsequent bars to continue trimming while
         the rule still holds.
3. Entry and unwind intent (before submission gates)
    - Resolve quantity_by_symbol with the shared strategy_quantity_by_symbol helper.
    - Use the shared calculate_zscore_target helper to calculate
        strategy_sign = 1 when STRATEGY_REVERSE is false, otherwise -1, and
        notional = trunc(strategy_sign * zscore * quantity / risk premium).
    - If notional and current position have opposite signs, target notional and
        submit -current position + notional position.
    - Otherwise, for a positive notional, target the greater of current position
        and notional; for a negative notional, target the lesser value.
    - If STRATEGY_POS_CAP (pos_cap) is set, clamp target to [-pos_cap, pos_cap].
    - Submit target position minus current position.
4. Submission gates for any non-zero delta
     - Z-score must be outside the risk-premium threshold.
     - Require a confirmation of at least two consecutive outside-range z-scores with the same sign.
     - Require a pullback confirmation: current return sign must be opposite to previous return sign.
5. Delta dispatch - record signed trade delta through context.trading_state
    and return the delta to the master driver for order execution.

Examples
--------
Run ratchet with default .env environment file:

    python3 -m MachineTrader.master_driver SPY \\
        --strategy MachineTrader.strat_ratchet_single:call_back


Run ratchet with custom environment file:

    python3 -m MachineTrader.master_driver SPY \\
        --strategy MachineTrader.strat_ratchet_single:call_back \\
        --env-file /tmp/ratchet.env

Backtest one trading day:

    python3 -m MachineTrader.master_backtest \\
        --strategy MachineTrader.strat_ratchet_single:call_back \\
        --env-file /tmp/ratchet.env \\
        --date 2026-09-04

"""

from __future__ import annotations

import math
import MachineTrader.helpers.file_handlers as _file_handlers
from dataclasses import dataclass, field
from typing import Any

from MachineTrader.helpers.calc_ema_class import EMACalculator
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
class BollingerState:
    symbol: str
    alpha: float = 0.99
    vol_floor: float = 0.1
    risk_premium: float = 1.0
    take_profit_threshold: float = 5.0
    take_profit_factor: float = 1.0
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

    def on_minute(self, context) -> float:
        bar = context.minute_bars.get(self.symbol)
        if not isinstance(bar, dict):
            self.indicators["last_delta"] = 0.0
            return 0.0

        price_last = float(bar.get("c", bar.get("close", 0.0)) or 0.0)
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

        alpha = _strategy_param_float(context.strategy_params, "alpha", self.alpha)
        dollar_vol_floor = _strategy_dollar_vol_floor(context.strategy_params, price_last, self.vol_floor)
        risk_premium = _strategy_param_float(
            context.strategy_params,
            "risk_premium",
            self.risk_premium,
            env_key="STRATEGY_RISK_PREMIUM",
        )
        take_profit_threshold = _strategy_param_float(
            context.strategy_params,
            "take_profit_threshold",
            self.take_profit_threshold,
        )
        take_profit_factor = _strategy_param_float(
            context.strategy_params,
            "take_profit_factor",
            self.take_profit_factor,
        )

        volume_last = float(bar.get("v", bar.get("volume", 1.0)) or 1.0)
        zscore, ema_price, return_vol = self.emac.calc_zscore_price_return_weighted(
            price_last,
            alpha,
            volume_last,
            dollar_vol_floor,
        )

        pos_state = context.positions.get(self.symbol, {})
        current_position = float(pos_state.get("qty", 0.0) or 0.0)
        shares_owned = abs(float(current_position))
        quantity = float(_strategy_quantity_by_symbol(context.strategy_params).get(self.symbol, 1.0) or 1.0)
        previous_price = self.indicators.get("price")
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
            ratchet=True,
        )
        notional_position = int(target.notional_position)
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

        largest_unrealized_position_pnl = float(pos_state.get("largest_unrealized_position_pnl", 0.0) or 0.0)
        best_lot_close_delta = float(pos_state.get("best_lot_close_delta", 0.0) or 0.0)
        raw_queue_prices = pos_state.get("position_queue_prices", [])
        position_queue_prices = [float(value) for value in raw_queue_prices] if isinstance(raw_queue_prices, list) else []
        raw_position_pnls = pos_state.get("unrealized_position_pnls", [])
        unrealized_position_pnls = [float(value) for value in raw_position_pnls] if isinstance(raw_position_pnls, list) else []

        last_buy_fill_price = next((abs(float(value)) for value in reversed(position_queue_prices) if float(value) < 0.0), None)
        last_sell_fill_price = next((float(value) for value in reversed(position_queue_prices) if float(value) > 0.0), None)

        effective_take_profit_threshold = max(0.0, float(take_profit_threshold))
        effective_take_profit_factor = max(0.0, float(take_profit_factor))
        take_profit_level = effective_take_profit_threshold * float(return_vol)
        per_share_take_profit_level = effective_take_profit_factor * float(return_vol)
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
        delta = 0.0
        selected_unwind_queue_prices: list[float] = []
        take_profit_triggered = False
        take_profit_reason = ""
        no_trade_reason = "position fits zscore"
        take_profit_chain_active = bool(self.indicators.get("take_profit_chain_active", False))
        pullback_waiting = False
        state_rationale = no_trade_reason

        qualifying_take_profit_count = sum(1 for value in unrealized_position_pnls if float(value) > per_share_take_profit_level)

        if qualifying_take_profit_count > 0 and best_lot_close_delta != 0.0:
            take_profit_triggered = True
            take_profit_reason = "per_share"
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
            selected_unwind_queue_prices = qualifying_entries
            take_profit_chain_active = True
            strategy_log(
                "🎯 ",
                f"[strat_ratchet] symbol={self.symbol} per-share take-profit triggered: "
                f"qualifying_positions={qualifying_take_profit_count} "
                f"largest_unrealized_position_pnl={largest_unrealized_position_pnl:.2f} > "
                f"per_share_take_profit_level={per_share_take_profit_level:.2f}",
            )
        elif take_profit_chain_active:
            if shares_owned <= 0:
                take_profit_chain_active = False
                no_trade_reason = "take-profit chain complete"
                strategy_log(
                    "✅ ",
                    f"[strat_ratchet] symbol={self.symbol} take-profit chain complete: no remaining position.",
                )
            elif qualifying_take_profit_count <= 0:
                take_profit_chain_active = False
                no_trade_reason = "take-profit chain complete"
                strategy_log(
                    "✅ ",
                    f"[strat_ratchet] symbol={self.symbol} take-profit chain complete: qualifying_positions=0 at per_share_take_profit_level={per_share_take_profit_level:.2f}",
                )
        elif abs(current_position) > 0 and unrealized_pl > 0.0 and unrealized_pl > take_profit_level:
            take_profit_triggered = True
            take_profit_reason = "aggregate"
            half_position = min(abs(float(current_position)), max(1.0, abs(float(current_position)) / 2.0))
            delta = -half_position if current_position > 0 else half_position
            unwind_count = int(round(abs(float(delta))))
            if unwind_count > 0:
                if current_position > 0:
                    candidates = [float(value) for value in position_queue_prices if float(value) < 0.0]
                else:
                    candidates = [float(value) for value in position_queue_prices if float(value) > 0.0]
                selected_unwind_queue_prices = candidates[-unwind_count:]
            strategy_log(
                "🎯 ",
                f"[strat_ratchet] symbol={self.symbol} take-profit rule triggered: unrealized_pl={unrealized_pl:.2f} > take_profit_level={take_profit_level:.2f}",
            )
        else:
            delta = float(target_position) - float(target.current_position)
            if position_sign != 0 and target_sign != 0 and position_sign != target_sign:
                if current_position > 0:
                    selected_unwind_queue_prices = [float(value) for value in position_queue_prices if float(value) < 0.0]
                else:
                    selected_unwind_queue_prices = [float(value) for value in position_queue_prices if float(value) > 0.0]

        if delta != 0.0 and not take_profit_triggered and not position_cap_correction:
            if not zscore_outside_range:
                no_trade_reason = "z-score not outside risk-premium range"
                strategy_log(
                    "⏸️ ",
                    f"[strat_ratchet] symbol={self.symbol} no trade: z-score must be outside risk-premium range; "
                    f"zscore={float(zscore):.6f} risk_premium={effective_risk_premium:.6f}",
                )
                delta = 0.0
            elif outside_range_streak < 2:
                no_trade_reason = "waiting for two-bar direction confirmation"
                strategy_log(
                    "⏸️ ",
                    f"[strat_ratchet] symbol={self.symbol} waiting for direction confirmation before submitting order: "
                    f"outside_range_streak={outside_range_streak} required=2 zscore={float(zscore):.6f} "
                    f"risk_premium={effective_risk_premium:.6f} signal_sign={signal_sign}",
                )
                delta = 0.0
            elif current_return_sign == 0 or previous_return_sign == 0 or current_return_sign == previous_return_sign:
                pullback_waiting = True
                no_trade_reason = "waiting for pullback"
                strategy_log(
                    "⏸️ ",
                    f"[strat_ratchet] symbol={self.symbol} waiting for pullback: "
                    f"current_return={current_return:.6f} previous_return={previous_return_value:.6f} "
                    f"current_return_sign={current_return_sign} previous_return_sign={previous_return_sign}",
                )
                delta = 0.0

        if delta != 0.0:
            same_direction_add = (current_position > 0.0 and delta > 0.0) or (current_position < 0.0 and delta < 0.0)
            if same_direction_add:
                volatility_gap = abs(float(return_vol))
                if delta < 0.0 and last_sell_fill_price is not None:
                    required_sell_price = float(last_sell_fill_price) + float(volatility_gap)
                    if float(price_last) <= required_sell_price:
                        no_trade_reason = "waiting for volatility-spaced sell add"
                        strategy_log(
                            "⏸️ ",
                            f"[strat_ratchet] symbol={self.symbol} waiting to add short: "
                            f"price={float(price_last):.6f} must be > last_sell_fill_price+volatility "
                            f"({float(last_sell_fill_price):.6f}+{float(volatility_gap):.6f}={float(required_sell_price):.6f}).",
                        )
                        delta = 0.0
                elif delta > 0.0 and last_buy_fill_price is not None:
                    required_buy_price = float(last_buy_fill_price) - float(volatility_gap)
                    if float(price_last) >= required_buy_price:
                        no_trade_reason = "waiting for volatility-spaced buy add"
                        strategy_log(
                            "⏸️ ",
                            f"[strat_ratchet] symbol={self.symbol} waiting to add long: "
                            f"price={float(price_last):.6f} must be < last_buy_fill_price-volatility "
                            f"({float(last_buy_fill_price):.6f}-{float(volatility_gap):.6f}={float(required_buy_price):.6f}).",
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
                "notional_position": int(notional_position),
                "target": float(target_position),
                "outside_range_streak": int(outside_range_streak),
                "outside_range_sign": int(outside_range_sign),
                "position": current_position,
                "unrealized_pl": unrealized_pl,
                "pnl_per_share": pnl_per_share,
                "unrealized_position_pnls": list(unrealized_position_pnls),
                "last_buy_fill_price": float(last_buy_fill_price) if last_buy_fill_price is not None else None,
                "last_sell_fill_price": float(last_sell_fill_price) if last_sell_fill_price is not None else None,
                "selected_unwind_queue_prices": list(selected_unwind_queue_prices),
                "largest_unrealized_position_pnl": largest_unrealized_position_pnl,
                "per_share_take_profit_level": per_share_take_profit_level,
                "qualifying_take_profit_count": int(qualifying_take_profit_count),
                "take_profit_level": take_profit_level,
                "risk_premium": float(effective_risk_premium),
                "pos_cap": float(pos_cap),
                "take_profit_threshold": float(effective_take_profit_threshold),
                "take_profit_factor": float(effective_take_profit_factor),
                "last_delta": delta,
                "pullback_waiting": bool(pullback_waiting),
                "take_profit_chain_active": bool(take_profit_chain_active),
                "last_rationale": state_rationale if delta != 0.0 else no_trade_reason,
            }
        )

        if delta != 0.0:
            submit_delta = float(delta)
            if take_profit_triggered:
                tp_reason_text = f"unrealized_pl={unrealized_pl:.2f} vs take_profit_threshold={take_profit_level:.2f}"
                if take_profit_reason == "per_share":
                    state_rationale = "take-profit per_share"
                    strategy_log(
                        "💰 ",
                        f"[strat_ratchet] symbol={self.symbol} TAKE-PROFIT triggered: closing {qualifying_take_profit_count:.0f} qualifying position(s) because {tp_reason_text}; largest_unrealized_position_pnl={largest_unrealized_position_pnl:.2f} > per_share_take_profit_level={per_share_take_profit_level:.2f} (delta={submit_delta:.0f}).",
                    )
                else:
                    state_rationale = "take-profit aggregate"
                    strategy_log(
                        "💰 ",
                        f"[strat_ratchet] symbol={self.symbol} TAKE-PROFIT triggered: closing half position because {tp_reason_text} (delta={submit_delta:.0f}).",
                    )
            else:
                state_rationale = "signal trade"
                strategy_log(
                    "🚀 ",
                    f"[strat_ratchet] symbol={self.symbol} strategy delta: side={'buy' if submit_delta > 0 else 'sell'} qty={abs(float(submit_delta)):.4f}",
                )

            self.indicators["last_rationale"] = state_rationale

            context.trading_state.add_strategy_amount(
                self.symbol,
                submit_delta,
                metadata={
                    "strategy": "strat_ratchet_single",
                    "reason": "flip_direction" if not take_profit_triggered and position_sign != 0 and target_sign != 0 and position_sign != target_sign else "",
                    "order_type": "market",
                    "convert_market_to_limit_when_closed": True,
                    "take_profit_triggered": bool(take_profit_triggered),
                    "take_profit_reason": take_profit_reason,
                    "cancel_all_limits": bool(take_profit_triggered),
                    "reset_limit_calculator": bool(take_profit_triggered),
                    "minute": context.minute_key,
                    "price": price_last,
                    "ema": float(ema_price),
                    "volatility": float(return_vol),
                    "zscore": float(zscore),
                    "position": current_position,
                    "configured_quantity": float(quantity),
                    "strategy_reverse": bool(reverse_enabled),
                    "strategy_sign": int(target.strategy_sign),
                    "notional_position": int(notional_position),
                    "target": float(target_position),
                    "unrealized_pl": unrealized_pl,
                    "pnl_per_share": pnl_per_share,
                    "unrealized_position_pnls": list(unrealized_position_pnls),
                    "selected_unwind_queue_prices": list(selected_unwind_queue_prices),
                    "largest_unrealized_position_pnl": largest_unrealized_position_pnl,
                    "per_share_take_profit_level": per_share_take_profit_level,
                    "qualifying_take_profit_count": int(qualifying_take_profit_count),
                    "take_profit_level": take_profit_level,
                    "risk_premium": float(effective_risk_premium),
                    "pos_cap": float(pos_cap),
                    "take_profit_threshold": float(effective_take_profit_threshold),
                    "take_profit_factor": float(effective_take_profit_factor),
                    "trunc_zscore": trunc_zscore,
                    "trunc_abs_zscore": trunc_abs_zscore,
                    "outside_range_streak": int(outside_range_streak),
                    "outside_range_sign": int(outside_range_sign),
                    "take_profit_chain_active": bool(take_profit_chain_active),
                },
            )
            self.indicators["take_profit_chain_active"] = bool(take_profit_chain_active)

        if delta == 0.0 and not take_profit_chain_active:
            self.indicators["take_profit_chain_active"] = False

        return delta


_STATE_BY_SYMBOL: dict[str, BollingerState] = {}


def call_back(context):
    """Master-driver strategy callback.

    Usage:
        --strategy MachineTrader.strat_ratchet_single:call_back
    """
    configured_symbols = [
        str(symbol).strip().upper()
        for symbol in context.strategy_params.get("strategy_symbols", [])
        if str(symbol).strip()
    ]
    symbols_to_process = sorted(dict.fromkeys(configured_symbols or context.minute_bars.keys()))
    zscores_by_symbol: dict[str, float] = {}
    ema_by_symbol: dict[str, float] = {}
    volatility_by_symbol: dict[str, float] = {}

    for symbol_key in symbols_to_process:
        if symbol_key not in _STATE_BY_SYMBOL:
            _STATE_BY_SYMBOL[symbol_key] = BollingerState(symbol=symbol_key)
        _STATE_BY_SYMBOL[symbol_key].on_minute(context)
        indicators = _STATE_BY_SYMBOL[symbol_key].indicators
        zscores_by_symbol[symbol_key] = float(indicators.get("zscore", 0.0) or 0.0)
        ema_by_symbol[symbol_key] = float(indicators.get("ema", 0.0) or 0.0)
        volatility_by_symbol[symbol_key] = float(indicators.get("volatility", 0.0) or 0.0)

    _file_handlers.append_strategy_symbol_indicator_csvs(
        context,
        minute_bars=context.minute_bars,
        zscores_by_symbol=zscores_by_symbol,
        symbol_order=symbols_to_process,
        ema_by_symbol=ema_by_symbol,
        volatility_by_symbol=volatility_by_symbol,
    )

    return None
