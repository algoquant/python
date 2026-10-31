"""
strat_ratchet - Portfolio momentum ratchet strategy driven by EMA z-scores.
==================================================================

Overview
--------
A portfolio-level momentum strategy that scores each configured symbol using an
EMA-based z-score. The z-score is derived from the latest bar price relative to
an exponentially weighted moving average and return volatility. The strategy
converts that signal into a target share count by scaling the z-score with a
configured quantity and a risk-premium factor, then submits market-order deltas
that rebalance the portfolio toward the target position.

This module is signal-only. It depends on the master_momentum for execution and
has no direct broker connection. Shared master driver helpers own state-file
output.

Trading Logic
-------------
The strategy runs once per minute, per symbol, in this order:

1. Read the latest bar and derive inputs:
    - price from c/close,
    - volume from v/volume,
    - alpha and vol_floor percentage from strategy params,
    - dollar_vol_floor = price * vol_floor / 100 for this symbol.
2. Update indicators from the EMA engine:
    - call calc_zscore_price_diff_emm(price, alpha, volume, dollar_vol_floor),
    - produce zscore, EMA price, and return volatility for this minute.
3. Resolve sizing and state inputs:
    - quantity from STRATEGY_QUANTITY / quantity_by_symbol,
    - risk_premium from STRATEGY_RISK_PREMIUM,
    - reverse flag from STRATEGY_REVERSE (strategy_sign = 1 if false, -1 if true),
    - current broker position from context.positions.
4. Convert signal to a ratcheted target position:
    - notional = trunc(strategy_sign * zscore * quantity / risk_premium),
    - if notional has switched sign compared to the previous value:
        target position = current notional
    - if notional has not switched sign and notional > 0:
        target position = Max(current notional, previous target)
    - if notional has not switched sign and notional < 0:
        target position = Min(current notional, previous target)
    - if STRATEGY_POS_CAP (pos_cap) is set, clamp target_position to
      [-pos_cap, pos_cap].
5. Compute target rebalance delta:
    - delta = target_position - current_position.
6. Update in-memory indicators for logging/reporting:
    - price, ema, volatility, zscore, position, target, notional, last_delta.
7. Publish the signed delta and current execution metadata every minute:
    - zero deltas publish metadata without creating a trade request,
    - include execution metadata (reason, prices, risk values, targets).

Notes
-----
- Driver-owned EOD flatten remains outside this strategy. The shared master
  driver handles end-of-day liquidation at STRATEGY_END_TIME.
- The master driver, not this strategy, gates trade submission before
  STRATEGY_START_TIME and after STRATEGY_END_TIME.
- This module is signal-only: it does not place broker orders directly.

Examples
--------
Run momentum with a custom environment file:

    python3 -m MachineTrader.master_momentum \\
        --strategy MachineTrader.strat_ratchet:call_back \\
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum_ratchet

Run momentum with a custom symbol list and per-symbol quantities:

    python3 -m MachineTrader.master_momentum SPY \\
        --strategy MachineTrader.strat_ratchet:call_back \\
        --strategy-symbols AAPL,MSFT,TSLA \\
        --strategy-param quantity_by_symbol='{"AAPL":2,"MSFT":1,"TSLA":1}'

Run momentum with a custom risk premium:

    python3 -m MachineTrader.master_momentum SPY \\
        --strategy MachineTrader.strat_ratchet:call_back \\
        --strategy-param risk_premium=2.0

Backtest one trading day:

    python3 -m MachineTrader.master_backtest \\
        --strategy MachineTrader.strat_ratchet:call_back \\
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum_ratchet \\
        --date 2026-09-04

"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import MachineTrader.helpers.file_handlers as _file_handlers
from MachineTrader.helpers.calc_ema_class import EMACalculator
from MachineTrader.helpers.driver_common import (
    cap_target_position as _cap_target_position,
    rounded_print as _rounded_print,
    strategy_dollar_vol_floor as _strategy_dollar_vol_floor,
    strategy_param_bool as _strategy_param_bool,
    strategy_quantity_by_symbol as _strategy_quantity_by_symbol,
    strategy_param_float as _strategy_param_float,
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
            "ema": None,
            "volatility": None,
            "zscore": 0.0,
            "position": 0.0,
            "target": 0.0,
            "notional": 0.0,
            "notional_position": 0.0,
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

        zscore, ema_price, return_vol = self.emac.calc_zscore_price_diff_emm(
            price_last,
            alpha,
            volume_last,
            dollar_vol_floor,
        )
        self.indicators.update(
            {
                "price": float(price_last),
                "ema": float(ema_price),
                "volatility": float(return_vol),
                "zscore": float(zscore),
            }
        )
        return True

    def calculate_target(self, context) -> float:
        price_last = float(self.indicators["price"])
        ema_price = float(self.indicators["ema"])
        return_vol = float(self.indicators["volatility"])
        zscore = float(self.indicators["zscore"])

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
        strategy_sign = -1 if reverse_enabled else 1

        scaled_signal = (float(strategy_sign) * float(zscore) * float(quantity)) / float(risk_premium)
        notional = int(math.trunc(scaled_signal))

        prev_notional_raw = self.indicators.get("notional", self.indicators.get("notional_position", 0.0))
        prev_notional = float(prev_notional_raw) if prev_notional_raw is not None else 0.0
        prev_target_raw = self.indicators.get("target", 0.0)
        prev_target = float(prev_target_raw) if prev_target_raw is not None else 0.0

        sign_switched = (prev_notional > 0 and notional < 0) or (prev_notional < 0 and notional > 0)
        if sign_switched:
            target_position = float(notional)
        elif notional > 0:
            target_position = max(float(notional), float(prev_target))
        elif notional < 0:
            target_position = min(float(notional), float(prev_target))
        else:
            target_position = float(prev_target)

        pos_cap = _strategy_param_float(
            context.strategy_params,
            "pos_cap",
            0.0,
            env_key="STRATEGY_POS_CAP",
        )
        target_position = _cap_target_position(target_position, pos_cap)
        delta = float(target_position) - float(current_position)
        ratchet_reason = "ratchet_target_rebalance"

        self.indicators.update(
            {
                "price": float(price_last),
                "ema": float(ema_price),
                "volatility": float(return_vol),
                "zscore": float(zscore),
                "position": float(current_position),
                "target": float(target_position),
                "notional": float(notional),
                "notional_position": float(notional),
                "last_delta": float(delta),
            }
        )

        context.trading_state.add_strategy_amount(
            self.symbol,
            float(delta),
            metadata={
                "strategy": "strat_ratchet",
                "reason": str(ratchet_reason),
                "order_type": "market",
                "convert_market_to_limit_when_closed": True,
                "minute": context.minute_key,
                "price": float(price_last),
                "ema": float(ema_price),
                "volatility": float(return_vol),
                "return_vol": float(return_vol),
                "zscore": float(zscore),
                "position": float(current_position),
                "target": float(target_position),
                "notional_position": float(notional),
                "notional": float(notional),
                "strategy_reverse": bool(reverse_enabled),
                "strategy_sign": int(strategy_sign),
                "configured_quantity": float(quantity),
                "risk_premium": float(risk_premium),
                "pos_cap": float(pos_cap),
                "scaled_signal": float(scaled_signal),
                "trunc_zscore": int(math.trunc(float(zscore))),
            },
        )

        return float(delta)

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
        --strategy MachineTrader.strat_ratchet:call_back
    """
    zscores_by_symbol: dict[str, float | None] = {}
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
        if symbol_key not in received_symbols:
            requested_shares_by_symbol[symbol_key] = 0.0
            continue
        delta = float(_STATE_BY_SYMBOL[symbol_key].calculate_target(context) or 0.0)
        requested_shares_by_symbol[symbol_key] = delta
        if abs(delta) > 1e-9:
            submitted_orders += 1

    _print_requested_shares_state_message(context, requested_shares_by_symbol, submitted_orders)
    return None
