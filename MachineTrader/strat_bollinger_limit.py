"""
strat_bollinger_limit — Bollinger intraday mean-reversion strategy for a single stock using the z-score as an indicator of whether the stock is rich or cheap.
==================================================================

Overview
--------
The z-score is calculated from the streaming price bars as the difference between the stock's last price minus the EMA price divided by the return volatility.
When the z-score exceeds the threshold level (risk_premium), the strategy submits limit orders to fade the move in prices.  It sells one share when the z-score is above the threshold, and buys one share when the z-score is below the negative threshold.
As long as the z-score exceeds the threshold level, the strategy continues to submit additional limit orders at prices that are multiples of the volatility, so the orders are spaced out from the current market price.
When the price trends back toward the EMA, and the z-score changes sign, the strategy submits limit orders in the opposite direction.
The strategy also applies a take-profit rule that trims positions when the unrealized PnL exceeds a multiple of the volatility.

Trading Logic
-------------
Each time a new bar of prices arrives, the strategy performs the following steps:

1. **Window gate** — bars outside the range [start_time, end_time) still update
    EMA, volatility, and z-score state, but they do not submit trade orders.

2. **Indicator computation** — the EMA calculator produces:
   - ``ema``        : volume-weighted exponential moving average of price
   - ``volatility`` : EMA volatility of the dollar returns
   - ``zscore``     : (price - ema) / max(volatility, vol_floor)
     A Z-score near 0 means price is close to fair value.
     Z-score >> 0 means price is stretched above the EMA.
     Z-score << 0 means price is stretched below the EMA.

3. **Take-profit rules** — checked before new entries.
     - **Per-position rule**: use driver-provided per-position unrealized snapshot
         metrics and identify all positions whose unrealized PnL exceeds
         ``take_profit_factor * volatility``. Close all qualifying positions by
         returning their closing delta to the master driver.
     - **Aggregate rule**: if driver-provided ``unrealized_pl > take_profit_threshold * volatility``,
         return a delta to close half the current position.
     - **Confirmation-driven chaining**: after any take-profit delta is filled,
         remaining lots are re-evaluated on subsequent bars to continue trimming while
         the rule still holds.
     Both take-profit exits signal the driver to cancel open limit orders for the symbol
     and reset the limit-price calculator.

4. **Entry signals** (only when no take-profit triggered):
   - Z-score >  +risk_premium  → SELL ``shares_per_trade`` shares (fade the rally)
   - Z-score <  -risk_premium  → BUY  ``shares_per_trade`` shares (fade the sell-off)
   - Otherwise                 → no action

5. **Pullback gate** — after an entry signal is formed, if the current and previous
    return signs are the same (no pullback yet), the strategy marks
    ``pullback_waiting=True`` and suppresses the order for that bar.

6. **Limit price calculation** — entry orders use limit prices that discount the
   current market price by ``risk_premium * volatility`` to improve fill quality:
   - BUY  limit = price − (risk_premium × volatility)
   - SELL limit = price + (risk_premium × volatility)
   On successive signals in the same direction the limit is stepped further away from
   the market to avoid chasing price.  A direction change resets the anchor price.

7. **Position cap** — clamp the proposed post-trade position to
    ``[-STRATEGY_POS_CAP, STRATEGY_POS_CAP]`` when STRATEGY_POS_CAP is greater
    than zero, then recompute the delta from the capped target.

Parameters
----------
All parameters can be overridden at runtime via master_driver.py CLI arguments.

alpha : float  (default 0.1, CLI: --alpha)
    EMA decay factor in (0, 1].  Smaller values produce a slower-moving average that
    reacts less to recent prices (more stable Z-scores); larger values make the EMA
    track price more closely (more reactive signals).
    Typical range: 0.05 (very slow) – 0.5 (fast).

vol_floor : float  (default 0.05, CLI: --vol-floor)
    Minimum dollar volatility used as the denominator in the Z-score calculation.
    Prevents division by near-zero volatility during quiet markets and caps the
    Z-score magnitude in ultra-low-vol conditions.
    Set to roughly the smallest price move you consider meaningful (e.g. 0.05 for a
    $100 stock that should react to 5-cent moves at minimum).

risk_premium : float  (default 2.0, CLI: --risk-premium)
    Dual-purpose threshold:
      1. Entry gate  — |Z-score| must exceed risk_premium to trigger a signal.
         Higher values = fewer, more extreme entries.
      2. Limit offset — limit price is offset from market by risk_premium × volatility.
         Higher values = more conservative (worse) fill prices but less market impact.
    Typical range: 1.0 (active) – 3.0 (selective).

take_profit_threshold : float  (default 5.0, CLI: --take-profit-threshold)
    Aggregate profit-taking multiplier.  Half of the current position is closed when:
        unrealized_pl > take_profit_threshold × volatility
    Lower values trigger aggregate profit-taking sooner (tighter); higher values let winners
    run longer before aggregate unwinds.
    Typical range: 5 (tight) – 30 (loose).

take_profit_factor : float  (default 2.0, CLI: --take-profit-factor)
    Per-position profit-taking multiplier. All open positions selected by
    driver-provided per-position unrealized snapshot metrics are closed when:
        unrealized_position_pnl > take_profit_factor × volatility
    Lower values trigger trimming sooner; higher values require larger single-lot gains before
    trimming.

start_time : str  (default "09:30", CLI: --start-time)
    Trading window open in HH:MM America/New_York.  Bars before this time are
    ignored.  Defaults to regular US market open if not provided.

end_time : str  (default "16:00", CLI: --end-time)
    Trading window close in HH:MM America/New_York.  Bars at or after this time
    are ignored.

shares_per_trade : float  (default 1.0)
    Number of shares submitted on each entry signal.  Not currently exposed as a
    CLI argument; set in BollingerEmaState directly or extend strategy_params.


Setup
--------
This module is signal-only.  It has no direct broker connection.  All trade deltas
are recorded through ``context.trading_state.add_strategy_amount()`` and returned to
``MachineTrader/master_driver.py``.  Portfolio liquidation at EOD is handled exclusively
by the master driver.



Examples
--------
Minimal — single symbol, all defaults:

    python3 -m MachineTrader.master_driver SPY \\
        --strategy MachineTrader.strat_bollinger_limit:call_back

Multiple symbols — same strategy instance handles all:

    python3 -m MachineTrader.master_driver SPY QQQ IWM \\
        --strategy MachineTrader.strat_bollinger_limit:call_back

Custom EMA speed — faster decay (alpha=0.3) with tighter volatility floor:

    python3 -m MachineTrader.master_driver NVDA \\
        --strategy MachineTrader.strat_bollinger_limit:call_back \\
        --alpha 0.3 \\
        --vol-floor 0.5

Conservative entries — require a wider Z-score deviation before trading:

    python3 -m MachineTrader.master_driver TSLA \\
        --strategy MachineTrader.strat_bollinger_limit:call_back \\
        --risk-premium 2.5 \\
        --vol-floor 0.5

Extended trading window — pre-market open to 30 min after close:

    python3 -m MachineTrader.master_driver SPY \\
        --strategy MachineTrader.strat_bollinger_limit:call_back \\
        --start-time 07:00 \\
        --end-time 16:30

Tight take-profit — lock in gains quickly:

    python3 -m MachineTrader.master_driver AAPL \\
        --strategy MachineTrader.strat_bollinger_limit:call_back \\
        --take-profit-threshold 5.0

Loose take-profit — let winners run longer:

    python3 -m MachineTrader.master_driver AAPL \\
        --strategy MachineTrader.strat_bollinger_limit:call_back \\
        --take-profit-threshold 25.0

Full parameter set — typical configuration:

    python3 -m MachineTrader.master_driver SPY NVDA \\
        --strategy MachineTrader.strat_bollinger_limit:call_back \\
        --alpha 0.9 \\
        --vol-floor 0.5 \\
        --risk-premium 1.0 \\
        --take-profit-threshold 5.0 \\
        --start-time 09:30 \\
        --end-time 16:00

Combined with a second strategy — signals are aggregated per symbol:

    python3 -m MachineTrader.master_driver SPY \\
        --strategy MachineTrader.strat_bollinger_limit:call_back \\
        --strategy MachineTrader.strat_bollinger_bars:bollinger_signal \\
        --alpha 0.9 \\
        --risk-premium 1.0

Custom proxy and environment file:

    python3 -m MachineTrader.master_driver SPY \\
        --strategy MachineTrader.strat_bollinger_limit:call_back \\
        --data-proxy-url ws://192.168.1.10:8765 \\
        --env-file /secrets/alpaca.env

Backtest one trading day:

    python3 -m MachineTrader.master_backtest \\
        --strategy MachineTrader.strat_bollinger_limit:call_back \\
        --env-file /Users/jerzy/Develop/trading/config/.env_ladder \\
        --date 2026-09-04
"""

from __future__ import annotations

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
from MachineTrader.helpers.markets import Markets


@dataclass
class BollingerState:
    symbol: str
    shares_per_trade: float = 1.0
    alpha: float = 0.9
    vol_floor: float = 0.5
    risk_premium: float = 1.0
    take_profit_threshold: float = 5.0
    take_profit_factor: float = 2.0
    start_time: str | None = None
    end_time: str | None = None
    indicators: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.symbol = self.symbol.upper()
        self.emac = EMACalculator()
        self.markets = Markets()
        self.indicators = {
            "price": None,
            "last_return": 0.0,
            "last_return_sign": 0,
            "ema": None,
            "volatility": None,
            "zscore": None,
            "position": 0.0,
            "unrealized_pl": 0.0,
            "pnl_per_share": 0.0,
            "per_share_take_profit_level": 0.0,
            "take_profit_level": 0.0,
            "last_delta": 0.0,
            "last_limit_price": None,
            "last_limit_side": None,
            "take_profit_chain_active": False,
        }

    def on_minute(self, context):
        bar = context.minute_bars.get(self.symbol)
        if not isinstance(bar, dict):
            return 0.0

        bar_year, bar_month, bar_day, bar_hour, bar_minute = context.minute_key
        bar_date = date(bar_year, bar_month, bar_day)
        bar_minutes = bar_hour * 60 + bar_minute
        start_time_str = _strategy_param_text(context.strategy_params, "start_time", self.start_time)
        market_close_time_str = _strategy_param_text(context.strategy_params, "market_close_time", "")
        end_time_str = market_close_time_str or _strategy_param_text(context.strategy_params, "end_time", self.end_time)

        strategy_log = _make_strategy_logger(
            context.strategy_params,
            context.minute_key,
            timestamp_field="minute",
            use_data_dir_name=False,
        )

        if start_time_str:
            open_minutes = _hhmm_to_minutes(start_time_str)
        else:
            ot = self.markets.get_open_time(bar_date)
            open_minutes = ot.hour * 60 + ot.minute
            start_time_str = ot.strftime("%H:%M")
        if end_time_str:
            close_minutes = _hhmm_to_minutes(end_time_str)
        else:
            ct = self.markets.get_close_time(bar_date)
            close_minutes = ct.hour * 60 + ct.minute
            end_time_str = ct.strftime("%H:%M")
        price_last = float(bar.get("c", bar.get("close", 0.0)) or 0.0)
        reset_symbols = getattr(context.alpaca_api, "limit_price_reset_symbols", None)
        if isinstance(reset_symbols, set) and self.symbol in reset_symbols:
            self.indicators["last_limit_price"] = None
            self.indicators["last_limit_side"] = None
            reset_symbols.discard(self.symbol)
            strategy_log("🧮 ", f"[strat_bollinger_limit] symbol={self.symbol} limit calculator reset after order cancellations.")
        market_is_open = open_minutes <= bar_minutes < close_minutes
        allow_trade_submissions = market_is_open
        alpha = _strategy_param_float(context.strategy_params, "alpha", self.alpha)
        dollar_vol_floor = _strategy_dollar_vol_floor(context.strategy_params, price_last, self.vol_floor)
        risk_premium = _strategy_param_float(context.strategy_params, "risk_premium", self.risk_premium)
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
        pos_cap = _strategy_param_float(
            context.strategy_params,
            "pos_cap",
            0.0,
            env_key="STRATEGY_POS_CAP",
        )

        volume_last = float(bar.get("v", bar.get("volume", 1.0)) or 1.0)
        zscore, ema_price, volatility = self.emac.calc_zscore_price_return(
            price_last,
            alpha,
            volume_last,
            dollar_vol_floor,
        )
        strategy_log("📊 ", 
            f"[strat_bollinger_limit] symbol={self.symbol} "
            f"ema_price={float(ema_price):.6f} zscore={float(zscore):.6f} volatility={float(volatility):.6f} risk_premium={float(risk_premium):.6f}"
        )

        if not allow_trade_submissions:
            strategy_log(
                "🛌 ",
                f"[strat_bollinger_limit] symbol={self.symbol} outside trading window {start_time_str}-{end_time_str}; indicators only: "
                f"ema_price={float(ema_price):.6f} zscore={float(zscore):.6f} volatility={float(volatility):.6f}. "
                "No trade orders outside the trading window."
            )
            self.indicators.update(
                {
                    "price": price_last,
                    "last_return": float(self.indicators.get("last_return", 0.0) or 0.0),
                    "last_return_sign": int(self.indicators.get("last_return_sign", 0) or 0),
                    "ema": float(ema_price),
                    "volatility": float(volatility),
                    "zscore": float(zscore),
                    "position": float(context.positions.get(self.symbol, {}).get("qty", 0.0) or 0.0),
                    "last_delta": 0.0,
                }
            )
            return 0.0

        pos_state = context.positions.get(self.symbol, {})
        current_position = float(pos_state.get("qty", 0.0) or 0.0)
        shares_owned = abs(float(current_position))
        previous_price = self.indicators.get("price")
        previous_return_sign = int(self.indicators.get("last_return_sign", 0) or 0)
        if previous_price is None:
            current_return = 0.0
        else:
            current_return = float(price_last) - float(previous_price)
        if current_return > 0:
            current_return_sign = 1
        elif current_return < 0:
            current_return_sign = -1
        else:
            current_return_sign = 0
        unrealized_pl = float(pos_state.get("unrealized_pl", 0.0) or 0.0)
        pnl_per_share = float(pos_state.get("pnl_per_share", 0.0) or 0.0)

        largest_unrealized_position_pnl = float(pos_state.get("largest_unrealized_position_pnl", 0.0) or 0.0)
        best_lot_close_delta = float(pos_state.get("best_lot_close_delta", 0.0) or 0.0)
        raw_queue_prices = pos_state.get("position_queue_prices", [])
        position_queue_prices = [float(value) for value in raw_queue_prices] if isinstance(raw_queue_prices, list) else []
        raw_position_pnls = pos_state.get("unrealized_position_pnls", [])
        unrealized_position_pnls = [float(value) for value in raw_position_pnls] if isinstance(raw_position_pnls, list) else []

        effective_take_profit_threshold = max(0.0, float(take_profit_threshold))
        effective_take_profit_factor = max(0.0, float(take_profit_factor))
        take_profit_level = effective_take_profit_threshold * float(volatility)
        per_share_take_profit_level = effective_take_profit_factor * float(volatility)
        delta = 0.0
        selected_unwind_queue_prices: list[float] = []
        take_profit_triggered = False
        take_profit_reason = ""
        no_trade_reason = "zscore out of range"
        take_profit_chain_active = bool(self.indicators.get("take_profit_chain_active", False))

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
            strategy_log("🎯 ",
                f"[strat_bollinger_limit] symbol={self.symbol} per-share take-profit triggered: "
                f"qualifying_positions={qualifying_take_profit_count} "
                f"largest_unrealized_position_pnl={largest_unrealized_position_pnl:.2f} > "
                f"per_share_take_profit_level={per_share_take_profit_level:.2f}"
            )
        elif take_profit_chain_active:
            if shares_owned <= 0:
                take_profit_chain_active = False
                no_trade_reason = "take-profit chain complete"
                strategy_log("✅ ",
                    f"[strat_bollinger_limit] symbol={self.symbol} take-profit chain complete: no remaining position."
                )
            elif qualifying_take_profit_count <= 0:
                take_profit_chain_active = False
                no_trade_reason = "take-profit chain complete"
                strategy_log("✅ ",
                    f"[strat_bollinger_limit] symbol={self.symbol} take-profit chain complete: "
                    f"qualifying_positions=0 at per_share_take_profit_level={per_share_take_profit_level:.2f}"
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
            strategy_log("🎯 ", 
                f"[strat_bollinger_limit] symbol={self.symbol} take-profit rule triggered: "
                f"unrealized_pl={unrealized_pl:.2f} > take_profit_level={take_profit_level:.2f}"
            )
        elif zscore > risk_premium:
            delta = -float(self.shares_per_trade)
        elif zscore < -risk_premium:
            delta = float(self.shares_per_trade)

        uncapped_target = current_position + delta
        target_position = _cap_target_position(uncapped_target, pos_cap)
        position_cap_correction = target_position != uncapped_target or (pos_cap > 0.0 and abs(current_position) > pos_cap)
        delta = target_position - current_position

        pullback_required = (
            delta != 0.0
            and not take_profit_triggered
            and not position_cap_correction
            and current_return_sign != 0
            and previous_return_sign != 0
            and current_return_sign == previous_return_sign
        )
        if pullback_required:
            if not bool(self.indicators.get("pullback_waiting", False)):
                strategy_log("⏳ ",
                    f"[strat_bollinger_limit] symbol={self.symbol} waiting for a pullback; "
                    f"current_return={current_return:.6f} previous_return_sign={previous_return_sign:+d} "
                    f"current_return_sign={current_return_sign:+d}"
                )
            self.indicators["pullback_waiting"] = True
            no_trade_reason = "waiting for pullback"
            delta = 0.0
        else:
            self.indicators["pullback_waiting"] = False

        self.indicators.update(
            {
                "price": price_last,
                "last_return": float(current_return),
                "last_return_sign": int(current_return_sign),
                "ema": float(ema_price),
                "volatility": float(volatility),
                "zscore": float(zscore),
                "position": current_position,
                "target": float(target_position),
                "pos_cap": float(pos_cap),
                "unrealized_pl": unrealized_pl,
                "pnl_per_share": pnl_per_share,
                "unrealized_position_pnls": list(unrealized_position_pnls),
                "selected_unwind_queue_prices": list(selected_unwind_queue_prices),
                "largest_unrealized_position_pnl": largest_unrealized_position_pnl,
                "per_share_take_profit_level": per_share_take_profit_level,
                "qualifying_take_profit_count": int(qualifying_take_profit_count),
                "take_profit_level": take_profit_level,
                "last_delta": delta,
                "take_profit_chain_active": bool(take_profit_chain_active),
            }
        )

        if delta == 0.0:
            if no_trade_reason == "waiting for pullback":
                strategy_log("ℹ️ ",
                    f"[strat_bollinger_limit] symbol={self.symbol} no trade: waiting for pullback; "
                    f"zscore={float(zscore):.6f} risk_premium={float(risk_premium):.6f} "
                    f"current_return={current_return:.6f} previous_return_sign={previous_return_sign:+d} "
                    f"current_return_sign={current_return_sign:+d}"
                )
            elif no_trade_reason == "take-profit chain complete":
                strategy_log("ℹ️ ",
                    f"[strat_bollinger_limit] symbol={self.symbol} no trade: take-profit chain complete."
                )
            else:
                strategy_log("ℹ️ ",
                    f"[strat_bollinger_limit] symbol={self.symbol} no trade: zscore out of range; "
                    f"abs(zscore)={abs(float(zscore)):.6f} <= risk_premium={float(risk_premium):.6f}"
                )

        if delta != 0.0:
            if take_profit_triggered:
                order_type = "market"
                limit_price = None
                self.indicators["last_limit_price"] = None
                self.indicators["last_limit_side"] = None
                tp_reason_text = (
                    f"unrealized_pl={unrealized_pl:.2f} vs take_profit_threshold={take_profit_level:.2f}"
                )
                if take_profit_reason == "per_share":
                    strategy_log("💰 ",
                        f"[strat_bollinger_limit] symbol={self.symbol} TAKE-PROFIT triggered: "
                        f"closing {qualifying_take_profit_count:.0f} qualifying position(s) because {tp_reason_text}; "
                        f"largest_unrealized_position_pnl={largest_unrealized_position_pnl:.2f} > "
                        f"per_share_take_profit_level={per_share_take_profit_level:.2f} "
                        f"(delta={delta:.0f})."
                    )
                else:
                    strategy_log("💰 ", 
                        f"[strat_bollinger_limit] symbol={self.symbol} TAKE-PROFIT triggered: "
                        f"closing half position because {tp_reason_text} "
                        f"(delta={delta:.0f})."
                    )
                strategy_log("🚀 ",
                    f"[strat_bollinger_limit] symbol={self.symbol} strategy delta: "
                    f"side={'buy' if delta > 0 else 'sell'} qty={abs(float(delta)):.4f}"
                )
                context.trading_state.add_strategy_amount(
                    self.symbol,
                    delta,
                    metadata={
                        "strategy": "strat_bollinger_limit",
                        "order_type": "market",
                        "convert_market_to_limit_when_closed": True,
                        "take_profit_triggered": True,
                        "take_profit_reason": take_profit_reason,
                        "cancel_all_limits": True,
                        "reset_limit_calculator": True,
                        "risk_premium": float(risk_premium),
                        "take_profit_factor": float(take_profit_factor),
                        "minute": context.minute_key,
                        "price": price_last,
                        "ema": float(ema_price),
                        "volatility": float(volatility),
                        "zscore": float(zscore),
                        "position": current_position,
                        "target": float(target_position),
                        "pos_cap": float(pos_cap),
                        "unrealized_pl": unrealized_pl,
                        "pnl_per_share": pnl_per_share,
                        "unrealized_position_pnls": list(unrealized_position_pnls),
                        "selected_unwind_queue_prices": list(selected_unwind_queue_prices),
                        "largest_unrealized_position_pnl": largest_unrealized_position_pnl,
                        "per_share_take_profit_level": per_share_take_profit_level,
                        "qualifying_take_profit_count": int(qualifying_take_profit_count),
                        "take_profit_level": take_profit_level,
                        "take_profit_chain_active": bool(take_profit_chain_active),
                    },
                )
                self.indicators["take_profit_chain_active"] = bool(take_profit_chain_active)
            else:
                adjustment = risk_premium * float(volatility)
                min_limit_step = max(float(vol_floor), 0.0)
                step_size = max(float(adjustment), min_limit_step)
                side_label = "buy" if delta > 0 else "sell"
                prev_limit_price = self.indicators.get("last_limit_price")
                prev_limit_side = self.indicators.get("last_limit_side")
                if prev_limit_side is not None and prev_limit_side != side_label:
                    self.indicators["last_limit_price"] = None
                    self.indicators["last_limit_side"] = None
                    prev_limit_price = None
                    prev_limit_side = None
                if prev_limit_price is not None and prev_limit_side == side_label:
                    step = -step_size if delta > 0 else step_size
                    limit_price = round(float(prev_limit_price) + step, 2)
                else:
                    limit_price = round(price_last - step_size, 2) if delta > 0 else round(price_last + step_size, 2)
                self.indicators["last_limit_price"] = float(limit_price)
                self.indicators["last_limit_side"] = side_label
                strategy_log("🚀 ",
                    f"[strat_bollinger_limit] symbol={self.symbol} strategy delta: "
                    f"side={side_label} qty={abs(float(delta)):.4f} limit_price={float(limit_price):.2f}"
                )
                context.trading_state.add_strategy_amount(
                    self.symbol,
                    delta,
                    metadata={
                        "strategy": "strat_bollinger_limit",
                        "order_type": "limit",
                        "convert_market_to_limit_when_closed": False,
                        "limit_price": limit_price,
                        "risk_premium": float(risk_premium),
                        "minute": context.minute_key,
                        "price": price_last,
                        "ema": float(ema_price),
                        "volatility": float(volatility),
                        "adjustment": float(adjustment),
                        "limit_step": float(step_size),
                        "zscore": float(zscore),
                        "position": current_position,
                        "target": float(target_position),
                        "pos_cap": float(pos_cap),
                        "unrealized_pl": unrealized_pl,
                        "take_profit_level": take_profit_level,
                    },
                )
                self.indicators["take_profit_chain_active"] = False

        if delta == 0.0 and not take_profit_chain_active:
            self.indicators["take_profit_chain_active"] = False

        return delta


_STATE_BY_SYMBOL: dict[str, BollingerState] = {}


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
        --strategy MachineTrader.strat_bollinger_limit:call_back
    """
    zscores_by_symbol: dict[str, float] = {}
    ema_by_symbol: dict[str, float] = {}
    volatility_by_symbol: dict[str, float] = {}
    symbols_to_process = sorted(context.minute_bars.keys())

    for symbol in symbols_to_process:
        symbol_key = str(symbol).upper()
        if symbol_key not in _STATE_BY_SYMBOL:
            _STATE_BY_SYMBOL[symbol_key] = BollingerState(symbol=symbol_key)
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
