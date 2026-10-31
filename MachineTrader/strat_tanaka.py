"""strat_tanaka - Intraday Tanaka reference-price strategy for master_driver
===============================================================================

Overview
--------
A signal-only intraday strategy that compares current price with a daily
reference price and targets either a long or short inventory of fixed size.
Indicators (EMA/volatility) are recomputed each minute for diagnostics,
while trade intent is derived from price vs reference level.

This module does not talk to the broker directly. It emits signed deltas via
context.trading_state.add_strategy_amount(), and MachineTrader/master_driver.py
handles order submission and broker coordination.

Conventions
-----------
1. Window gate - bars outside [start_time, end_time) continue updating
    indicators but do not submit trade orders.
2. Message handling - strategy logs can be written to message_file and respect
    log_dir_name / LOG_DIR_NAME for relative file paths.
3. Portfolio liquidation - handled exclusively by the master driver at
    STRATEGY_END_TIME if STRATEGY_EOD_FLATTEN is true.

Trading Logic
-------------
1. Warmup window - from 09:30 until start_time, the strategy does not trade and
    only accumulates VWAP diagnostics.
2. Indicator computation - each minute uses
    calc_zscore_price_return_weighted() with alpha fixed at 0.999.
3. Reference price behavior:
        - If bars are available before start_time, reference_price tracks ema_price
            during [09:30, start_time), then freezes for trading.
        - If the first available bar for the day arrives at/after start_time,
            reference_price is initialized once from that bar's VWAP and then frozen.
4. Window gate - bars outside [start_time, end_time) still update indicators,
    but no trade orders are submitted.
5. Ratchet-style submission gates - trade intent is derived from z-score and
    current position, then gated by:
        - z-score outside risk-premium threshold
        - two-bar outside-range confirmation
        - pullback confirmation from return-sign flip
6. Position cap - clamp each proposed target to
    [-STRATEGY_POS_CAP, STRATEGY_POS_CAP] when STRATEGY_POS_CAP is greater than
    zero, then recompute delta from the capped target.

Examples
--------
Run tanaka with default .env environment file:
     python3 -m MachineTrader.master_driver SPY \\
          --strategy MachineTrader.strat_tanaka:call_back


Run tanaka with custom environment file:

    python3 -m MachineTrader.master_driver SPY \\
        --strategy MachineTrader.strat_tanaka:call_back \\
        --env-file /tmp/tanaka.env

Backtest one trading day:

    python3 -m MachineTrader.master_backtest \\
        --strategy MachineTrader.strat_tanaka:call_back \\
        --env-file /tmp/tanaka.env \\
        --date 2026-09-04

"""

from __future__ import annotations

import math
import os
import csv
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import MachineTrader.helpers.file_handlers as _file_handlers
from MachineTrader.helpers.calc_ema_class import EMACalculator
from MachineTrader.helpers.driver_common import (
    NY_TZ as _NY_TZ,
    cap_target_position as _cap_target_position,
    derive_strategy_report_name as _derive_strategy_report_name,
    fmt_optional_number as _fmt_optional_number,
    hhmm_to_minutes as _hhmm_to_minutes,
    make_strategy_logger as _make_strategy_logger,
    minute_to_str as _minute_to_str,
    minutes_to_hhmm as _minutes_to_hhmm,
    resolve_close_minutes as _resolve_close_minutes,
    resolve_csv_path as _resolve_csv_path,
    rounded_print as _rounded_print,
    strategy_dollar_vol_floor as _strategy_dollar_vol_floor,
    strategy_param_float as _strategy_param_float,
    strategy_param_int as _strategy_param_int,
    strategy_param_text as _strategy_param_text,
)
from MachineTrader.helpers.timestamp_utils import coerce_market_datetime_ny


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


@dataclass
class TanakaState:
    symbol: str
    target_size: int = 1
    alpha: float = 0.999
    vol_floor: float = 0.01
    risk_premium: float = 1.0
    start_time: str | None = None
    end_time: str | None = None
    reference_price: float | None = None
    reference_day: tuple[int, int, int] | None = None
    reference_vwap_sum: float = 0.0
    reference_vwap_count: int = 0
    indicators: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.symbol = self.symbol.upper()
        self.emac = EMACalculator()
        self.indicators = {
            "price": None,
            "ema": None,
            "volatility": None,
            "reference_price": None,
            "market_open_waiting": False,
            "market_open_time": None,
            "reference_vwap_count": 0,
            "zscore": None,
            "outside_range_streak": 0,
            "outside_range_sign": 0,
            "last_return": 0.0,
            "last_return_sign": 0,
            "pullback_waiting": False,
            "position": 0.0,
            "target": 0.0,
            "target_size": 1.0,
            "last_delta": 0.0,
        }

    def on_minute(self, context):
        bar = context.minute_bars.get(self.symbol)
        if not isinstance(bar, dict):
            return 0.0

        bar_year, bar_month, bar_day, bar_hour, bar_minute = context.minute_key
        _bar_date = date(bar_year, bar_month, bar_day)
        bar_minutes = bar_hour * 60 + bar_minute

        market_open_anchor_minutes = 9 * 60 + 30

        start_time_str = _strategy_param_text(context.strategy_params, "start_time", self.start_time)
        market_close_time_str = _strategy_param_text(context.strategy_params, "market_close_time", "")
        market_open_time_str = _strategy_param_text(context.strategy_params, "market_open_time", "09:30")
        end_time_str = _strategy_param_text(context.strategy_params, "end_time", self.end_time)

        start_minutes = _hhmm_to_minutes(start_time_str) if start_time_str else market_open_anchor_minutes
        start_minutes = max(start_minutes, market_open_anchor_minutes)
        start_time_str = _minutes_to_hhmm(start_minutes)
        market_open_minutes = _hhmm_to_minutes(market_open_time_str) if market_open_time_str else market_open_anchor_minutes
        market_open_time_str = _minutes_to_hhmm(market_open_minutes)
        end_minutes = _hhmm_to_minutes(end_time_str) if end_time_str else None
        market_close_minutes = _hhmm_to_minutes(market_close_time_str) if market_close_time_str else None

        close_minutes = _resolve_close_minutes(end_minutes, market_close_minutes)
        close_time_str = _minutes_to_hhmm(close_minutes)

        price_last = float(bar.get("c", bar.get("close", 0.0)) or 0.0)
        vwap_last = float(bar.get("vw", bar.get("vwap", price_last)) or price_last)

        strategy_log = _make_strategy_logger(
            context.strategy_params,
            context.minute_key,
            timestamp_field="time",
            use_log_dir_name=True,
        )

        market_is_open = start_minutes <= bar_minutes < close_minutes
        allow_trade_submissions = market_is_open

        alpha = 0.999
        dollar_vol_floor = _strategy_dollar_vol_floor(context.strategy_params, price_last, self.vol_floor)
        target_size = _strategy_param_int(context.strategy_params, "target_size", self.target_size)
        risk_premium = _strategy_param_float(context.strategy_params, "risk_premium", self.risk_premium)
        pos_cap = _strategy_param_float(
            context.strategy_params,
            "pos_cap",
            0.0,
            env_key="STRATEGY_POS_CAP",
        )

        volume_last = float(bar.get("v", bar.get("volume", 1.0)) or 1.0)
        zscore, ema_price, return_vol = self.emac.calc_zscore_price_return_weighted(
            price_last,
            alpha,
            volume_last,
            dollar_vol_floor,
        )

        day_key = (bar_year, bar_month, bar_day)
        if day_key != self.reference_day:
            self.reference_day = day_key
            self.reference_price = None
            self.reference_vwap_sum = 0.0
            self.reference_vwap_count = 0
            self.indicators["outside_range_streak"] = 0
            self.indicators["outside_range_sign"] = 0
            self.indicators["last_return"] = 0.0
            self.indicators["last_return_sign"] = 0
            self.indicators["pullback_waiting"] = False

        # Pre-start warmup: from 09:30 until strategy start, only accumulate VWAP diagnostics.
        if market_open_minutes <= bar_minutes < start_minutes:
            self.reference_vwap_sum += float(vwap_last)
            self.reference_vwap_count += 1

        if bar_minutes < market_open_minutes:
            strategy_log(
                "🛌 ",
                f"[strat_tanaka] symbol={self.symbol} idle before market open {market_open_time_str}; indicators only: "
                f"price={float(price_last):.6f} ema_price={float(ema_price):.6f} zscore={float(zscore):.6f} volatility={float(return_vol):.6f}. "
                "No trade orders before market open.",
            )
            self.indicators.update(
                {
                    "price": price_last,
                    "ema": float(ema_price),
                    "volatility": float(return_vol),
                    "zscore": float(zscore),
                    "market_open_waiting": True,
                    "market_open_time": str(market_open_time_str),
                    "reference_vwap_count": int(self.reference_vwap_count),
                    "last_delta": 0.0,
                }
            )
            return 0.0

        # Keep reference anchored to the final EMA before start_time.
        if bar_minutes < start_minutes:
            self.reference_price = float(ema_price)
        elif self.reference_price is None:
            # Fallback when first seen bar is already at/after start_time.
            self.reference_price = float(vwap_last)
            strategy_log(
                "🧭 ",
                f"[strat_tanaka] symbol={self.symbol} initialized reference_price from first available VWAP at/after start_time: "
                f"reference={float(self.reference_price):.6f}",
            )

        reference_price = float(self.reference_price)

        strategy_log(
            "📊 ",
            f"[strat_tanaka] symbol={self.symbol} price={float(price_last):.6f} "
            f"reference={float(reference_price):.6f} ema_price={float(ema_price):.6f} "
            f"zscore={float(zscore):.6f} volatility={float(return_vol):.6f}",
        )

        if not allow_trade_submissions:
            if market_open_minutes <= bar_minutes < start_minutes:
                gate_reason = f"VWAP warmup only (09:30 to start_time {start_time_str})"
            elif bar_minutes < market_open_minutes:
                gate_reason = f"waiting for market open at {market_open_time_str}"
            else:
                gate_reason = f"outside trading window {start_time_str}-{close_time_str}"
            strategy_log(
                "🛌 ",
                f"[strat_tanaka] symbol={self.symbol} {gate_reason}; "
                f"indicators only: price={float(price_last):.6f} reference={float(reference_price):.6f} ema_price={float(ema_price):.6f} "
                f"zscore={float(zscore):.6f} volatility={float(return_vol):.6f}. No trade orders outside the trading window.",
            )
            self.indicators.update(
                {
                    "price": price_last,
                    "last_return": float(self.indicators.get("last_return", 0.0) or 0.0),
                    "last_return_sign": int(self.indicators.get("last_return_sign", 0) or 0),
                    "ema": float(ema_price),
                    "volatility": float(return_vol),
                    "zscore": float(zscore),
                    "reference_price": float(reference_price),
                    "market_open_waiting": bool(bar_minutes < market_open_minutes),
                    "market_open_time": str(market_open_time_str),
                    "reference_vwap_count": int(self.reference_vwap_count),
                    "outside_range_streak": int(self.indicators.get("outside_range_streak", 0) or 0),
                    "outside_range_sign": int(self.indicators.get("outside_range_sign", 0) or 0),
                    "pullback_waiting": False,
                    "target_size": float(target_size),
                    "last_delta": 0.0,
                }
            )
            return 0.0

        pos_state = context.positions.get(self.symbol, {})
        current_position = float(pos_state.get("qty", 0.0) or 0.0)

        previous_price = self.indicators.get("price")
        current_return = float(price_last) - float(previous_price) if previous_price is not None else 0.0
        current_return_sign = 1 if current_return > 0 else -1 if current_return < 0 else 0
        previous_return = self.indicators.get("last_return")
        previous_return_value = float(previous_return) if previous_return is not None else 0.0
        previous_return_sign = 1 if previous_return_value > 0 else -1 if previous_return_value < 0 else 0

        signal_sign = 1 if float(zscore) > 0 else -1 if float(zscore) < 0 else 0
        position_sign = 1 if current_position > 0 else -1 if current_position < 0 else 0
        effective_risk_premium = max(0.0, float(risk_premium))
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

        trunc_zscore = int(math.trunc(float(zscore)))
        trunc_abs_zscore = int(math.trunc(abs(float(zscore))))
        trunc_sign = 1 if trunc_zscore > 0 else -1 if trunc_zscore < 0 else 0

        delta = 0.0
        target = current_position
        trade_reason = "position fits zscore"
        pullback_waiting = False

        if trunc_sign != 0 and position_sign != 0 and trunc_sign == position_sign:
            delta = -current_position
            target = 0.0
            trade_reason = "flip_direction"
        elif trunc_abs_zscore > abs(current_position):
            if trunc_zscore > 0 and trunc_zscore > -current_position:
                delta = -1.0
            elif trunc_zscore < 0 and trunc_zscore < -current_position:
                delta = 1.0
            target = current_position + delta
            trade_reason = "ratchet_add"

        uncapped_target = float(target)
        target = _cap_target_position(uncapped_target, pos_cap)
        position_cap_correction = target != uncapped_target or (pos_cap > 0.0 and abs(current_position) > pos_cap)
        delta = float(target) - current_position

        if delta != 0.0 and not position_cap_correction:
            if not zscore_outside_range:
                trade_reason = "z-score not outside risk-premium range"
                strategy_log(
                    "⏸️ ",
                    f"[strat_tanaka] symbol={self.symbol} no trade: z-score must be outside risk-premium range; "
                    f"zscore={float(zscore):.6f} risk_premium={effective_risk_premium:.6f}",
                )
                delta = 0.0
                target = current_position
            elif outside_range_streak < 2:
                trade_reason = "waiting for two-bar direction confirmation"
                strategy_log(
                    "⏸️ ",
                    f"[strat_tanaka] symbol={self.symbol} waiting for direction confirmation before submitting order: "
                    f"outside_range_streak={outside_range_streak} required=2 zscore={float(zscore):.6f} "
                    f"risk_premium={effective_risk_premium:.6f} signal_sign={signal_sign}",
                )
                delta = 0.0
                target = current_position
            elif current_return_sign == 0 or previous_return_sign == 0 or current_return_sign == previous_return_sign:
                pullback_waiting = True
                trade_reason = "waiting for pullback"
                strategy_log(
                    "⏸️ ",
                    f"[strat_tanaka] symbol={self.symbol} waiting for pullback: "
                    f"current_return={current_return:.6f} previous_return={previous_return_value:.6f} "
                    f"current_return_sign={current_return_sign} previous_return_sign={previous_return_sign}",
                )
                delta = 0.0
                target = current_position

        self.indicators.update(
            {
                "price": price_last,
                "last_return": float(current_return),
                "last_return_sign": current_return_sign,
                "ema": float(ema_price),
                "volatility": float(return_vol),
                "zscore": float(zscore),
                "reference_price": float(reference_price),
                "market_open_waiting": False,
                "market_open_time": str(market_open_time_str),
                "reference_vwap_count": int(self.reference_vwap_count),
                "outside_range_streak": int(outside_range_streak),
                "outside_range_sign": int(outside_range_sign),
                "pullback_waiting": bool(pullback_waiting),
                "position": current_position,
                "target": float(target),
                "target_size": float(target_size),
                "pos_cap": float(pos_cap),
                "last_delta": delta,
            }
        )

        if delta == 0.0:
            strategy_log(
                "ℹ️ ",
                f"[strat_tanaka] symbol={self.symbol} no trade: "
                f"zscore={float(zscore):.2f}. reason={trade_reason}",
            )

        if delta != 0.0:
            strategy_log(
                "🚀 ",
                f"[strat_tanaka] symbol={self.symbol} strategy delta: side={'buy' if delta > 0 else 'sell'} qty={abs(float(delta)):.4f}",
            )
            context.trading_state.add_strategy_amount(
                self.symbol,
                float(delta),
                metadata={
                    "strategy": "strat_tanaka",
                    "reason": trade_reason,
                    "order_type": "market",
                    "convert_market_to_limit_when_closed": True,
                    "minute": context.minute_key,
                    "price": price_last,
                    "reference_price": float(reference_price),
                    "reference_vwap_count": int(self.reference_vwap_count),
                    "ema": float(ema_price),
                    "volatility": float(return_vol),
                    "zscore": float(zscore),
                    "risk_premium": float(effective_risk_premium),
                    "position": current_position,
                    "target": float(target),
                    "target_size": float(target_size),
                    "pos_cap": float(pos_cap),
                },
            )

        return delta


_STATE_BY_SYMBOL: dict[str, TanakaState] = {}


def _build_strategy_state_csv_path(context) -> Path:
    strategy_name = str(
        getattr(context.trading_state, "strategy_name", "")
        or context.strategy_params.get("strategy_name", "")
        or "master_driver"
    ).strip()
    date_suffix = datetime.now(_NY_TZ).strftime("%Y%m%d")
    default_name = _derive_strategy_report_name(strategy_name, f"state_{date_suffix}.csv")
    return _resolve_csv_path("", default_name, context.strategy_params)


def _state_row_timestamp_with_seconds(context, symbol_key: str) -> str:
    bar = context.minute_bars.get(symbol_key, {}) if isinstance(context.minute_bars, dict) else {}
    raw_ts = bar.get("t", bar.get("timestamp")) if isinstance(bar, dict) else None
    if raw_ts is not None:
        parsed_dt = coerce_market_datetime_ny(raw_ts, fallback_to_now=False)
        if parsed_dt is not None:
            return parsed_dt.astimezone(_NY_TZ).strftime("%Y-%m-%d %H:%M:%S")
    return f"{_minute_to_str(context.minute_key)}:00"


def _state_row_rationale(delta: float, indicators: dict[str, Any]) -> str:
    if float(delta) > 0.0:
        return "signal buy"
    if float(delta) < 0.0:
        return "signal sell"
    if bool(indicators.get("pullback_waiting", False)):
        return "waiting for pullback"
    if bool(indicators.get("market_open_waiting", False)):
        return "waiting for market open"
    return "no trade"


def _append_strategy_state_csv(context, symbol_key: str, indicators: dict[str, Any], delta: float):
    path = _build_strategy_state_csv_path(context)
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()
    fieldnames = ["date_time", "symbol", "price", "EMA price", "volatility", "z-score", "order", "rationale"]

    order_text = "none"
    if float(delta) > 0.0:
        order_text = "buy"
    elif float(delta) < 0.0:
        order_text = "sell"

    row = {
        "date_time": _state_row_timestamp_with_seconds(context, symbol_key),
        "symbol": symbol_key,
        "price": _fmt_optional_number(indicators.get("price"), precision=6),
        "EMA price": _fmt_optional_number(indicators.get("ema"), precision=6),
        "volatility": _fmt_optional_number(indicators.get("volatility"), precision=6),
        "z-score": _fmt_optional_number(indicators.get("zscore"), precision=6),
        "order": order_text,
        "rationale": _state_row_rationale(delta, indicators),
    }

    print(
        "🧾 ",
        f"date_time={row['date_time']} | symbol={row['symbol']} | price={row['price']} | "
        f"EMA price={row['EMA price']} | volatility={row['volatility']} | z-score={row['z-score']} | "
        f"order={row['order']} | rationale={row['rationale']}",
    )

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


def call_back(context):
    """Master-driver strategy callback.

    Usage:
        --strategy MachineTrader.strat_tanaka:call_back
    """
    zscores_by_symbol: dict[str, float] = {}
    ema_by_symbol: dict[str, float] = {}
    volatility_by_symbol: dict[str, float] = {}
    symbols_to_process = sorted(context.minute_bars.keys())

    for symbol in symbols_to_process:
        symbol_key = str(symbol).upper()
        if symbol_key not in _STATE_BY_SYMBOL:
            _STATE_BY_SYMBOL[symbol_key] = TanakaState(symbol=symbol_key)
        delta = float(_STATE_BY_SYMBOL[symbol_key].on_minute(context) or 0.0)
        indicators = _STATE_BY_SYMBOL[symbol_key].indicators
        _append_strategy_state_csv(context, symbol_key, indicators, delta)
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


def tanaka_intraday_signal(context):
    """Alias for previous callback name.

    Usage:
        --strategy MachineTrader.strat_tanaka:tanaka_intraday_signal
    """
    return call_back(context)
