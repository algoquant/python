"""
strat_bollinger — Bollinger Bands Contrarian Strategy
==================================================================

Overview
--------
A mean-reversion (contrarian) intraday strategy built on exponential moving averages
(EMA) and volume-weighted volatility.  Each minute bar is scored against a running EMA
using a Z-score; when price strays too far above or below that average the strategy
fades the move.  Positions are exited either via a take-profit rule or an end-of-day
flatten, and all normal entries are placed as limit orders to control fill cost.

This module is signal-only.  It has no direct broker connection.  All trade signals
are recorded through ``context.trading_state.add_strategy_amount()`` and dispatched by
``AlpacaSDK/master_driver.py``.

Trading Logic
-------------
Every minute the strategy performs the following steps, in order:

1. **Window gate** — bars outside [start_time, end_time) are skipped entirely.

2. **EOD flatten** — if ``eod_flatten`` is True and the bar falls within
    ``eod_flatten_minutes`` of ``end_time``, the strategy liquidates the full open
    position.  It submits a market order while the market is open; if the market is
    closed it submits a limit order at the current bar price.  No new entries are
    made after this point.

3. **Indicator computation** — the EMA calculator produces:
   - ``ema``        : volume-weighted exponential moving average of price
   - ``volatility`` : running estimate of dollar price dispersion (EMA of |price - ema|)
   - ``zscore``     : (price - ema) / max(volatility, vol_floor)
     A Z-score near 0 means price is close to fair value.
     Z-score >> 0 means price is stretched above the EMA.
     Z-score << 0 means price is stretched below the EMA.

4. **Take-profit rules** — checked before new entries.
     - **Per-share rule**: compute ``pnl_per_share = unrealized_pl / abs(position)``.
         If ``pnl_per_share > take_profit_factor * volatility``, liquidate one share via market order.
     - **Aggregate rule**: if ``unrealized_pl > take_profit_threshold * volatility``,
         liquidate half the current position via market order.
     Both take-profit exits cancel open limit orders for the symbol and reset the
     limit-price calculator.

5. **Entry signals** (only when no take-profit triggered):
   - Z-score >  +risk_premium  → SELL ``shares_per_trade`` shares (fade the rally)
   - Z-score <  -risk_premium  → BUY  ``shares_per_trade`` shares (fade the sell-off)
   - Otherwise                 → no action

6. **Limit price calculation** — entry orders use limit prices that discount the
   current market price by ``risk_premium * volatility`` to improve fill quality:
   - BUY  limit = price − (risk_premium × volatility)
   - SELL limit = price + (risk_premium × volatility)
   On successive signals in the same direction the limit is stepped further away from
   the market to avoid chasing price.  A direction change resets the anchor price.

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
    Aggregate profit-taking multiplier.  Half of the current position is liquidated when:
        unrealized_pl > take_profit_threshold × volatility
    In addition, a separate per-share rule liquidates one share whenever:
        unrealized_pl / abs(position) > take_profit_factor × volatility
    Lower values trigger aggregate profit-taking sooner (tighter); higher values let winners
    run longer before aggregate unwinds.  Take-profit exits use market orders.
    Typical range: 5 (tight) – 30 (loose).

take_profit_factor : float  (default 2.0, CLI: --take-profit-factor)
    Per-share profit-taking multiplier. One share is liquidated when:
        unrealized_pl / abs(position) > take_profit_factor × volatility
    Lower values trigger per-share profit-taking sooner; higher values require larger
    per-share gains before trimming.

start_time : str  (default "09:30", CLI: --start-time)
    Trading window open in HH:MM America/New_York.  Bars before this time are
    ignored.  Defaults to regular US market open if not provided.

end_time : str  (default "16:00", CLI: --end-time)
    Trading window close in HH:MM America/New_York.  Bars at or after this time
    are ignored.  EOD flatten fires within eod_flatten_minutes of this time.

eod_flatten : bool  (default True, CLI: --eod-flatten / --no-eod-flatten)
    When True the strategy will submit a market order to flatten any open position
    when the bar timestamp enters the EOD flatten window.  Disabling this leaves
    position management entirely to the broker or other logic.

eod_flatten_minutes : int  (default 2, CLI: --eod-flatten-minutes)
    How many minutes before end_time to begin EOD flattening.  With end_time=16:00
    and eod_flatten_minutes=2, flattening fires at or after 15:58.

shares_per_trade : float  (default 1.0)
    Number of shares submitted on each entry signal.  Not currently exposed as a
    CLI argument; set in BollingerEmaState directly or extend strategy_params.

Examples
--------
Minimal — single symbol, all defaults:

    python3 -m AlpacaSDK.master_driver SPY \\
        --strategy strat_bollinger:call_back

Multiple symbols — same strategy instance handles all:

    python3 -m AlpacaSDK.master_driver SPY QQQ IWM \\
        --strategy strat_bollinger:call_back

Custom EMA speed — faster decay (alpha=0.3) with tighter volatility floor:

    python3 -m AlpacaSDK.master_driver NVDA \\
        --strategy strat_bollinger:call_back \\
        --alpha 0.3 \\
        --vol-floor 0.5

Conservative entries — require a wider Z-score deviation before trading:

    python3 -m AlpacaSDK.master_driver TSLA \\
        --strategy strat_bollinger:call_back \\
        --risk-premium 2.5 \\
        --vol-floor 0.5

Extended trading window — pre-market open to 30 min after close:

    python3 -m AlpacaSDK.master_driver SPY \\
        --strategy strat_bollinger:call_back \\
        --start-time 07:00 \\
        --end-time 16:30

Tight take-profit — lock in gains quickly:

    python3 -m AlpacaSDK.master_driver AAPL \\
        --strategy strat_bollinger:call_back \\
        --take-profit-threshold 5.0

Loose take-profit — let winners run longer:

    python3 -m AlpacaSDK.master_driver AAPL \\
        --strategy strat_bollinger:call_back \\
        --take-profit-threshold 25.0

Disable EOD flatten — hold positions overnight:

    python3 -m AlpacaSDK.master_driver SPY \\
        --strategy strat_bollinger:call_back \\
        --no-eod-flatten

Full parameter set — typical production configuration:

    python3 -m AlpacaSDK.master_driver SPY NVDA \\
        --strategy strat_bollinger:call_back \\
        --alpha 0.9 \\
        --vol-floor 0.5 \\
        --risk-premium 1.0 \\
        --take-profit-threshold 5.0 \\
        --start-time 09:30 \\
        --end-time 16:00 \\
        --eod-flatten \\
        --eod-flatten-minutes 2

Combined with a second strategy — signals are aggregated per symbol:

    python3 -m AlpacaSDK.master_driver SPY \\
        --strategy strat_bollinger:call_back \\
        --strategy strat_bollinger_bars:bollinger_signal \\
        --alpha 0.9 \\
        --risk-premium 1.0

Custom proxy and environment file:

    python3 -m AlpacaSDK.master_driver SPY \\
        --strategy strat_bollinger:call_back \\
        --proxy-url ws://192.168.1.10:8765 \\
        --env-file /secrets/alpaca.env

Backtest one trading day:

    python3 -m MachineTrader.master_backtest \\
        --strategy MachineTrader.strat_bollinger:call_back \\
        --env-file /Users/jerzy/Develop/trading/config/.env_ladder \\
        --date 2026-09-04
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

from calc_ema_class import EMACalculator
from MachineTrader.markets import Markets
from MachineTrader.helpers.setup_strat import strategy_dollar_vol_floor


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
    eod_flatten: bool = True
    indicators: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.symbol = self.symbol.upper()
        self.emac = EMACalculator()
        self.markets = Markets()
        self.indicators = {
            "price": None,
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
        }

    @staticmethod
    def _hhmm_to_minutes(hhmm: str) -> int:
        text = str(hhmm or "").strip()
        parts = text.split(":")
        if len(parts) < 2:
            raise ValueError(f"Invalid time value '{hhmm}'. Expected HH:MM or HH:MM:SS")
        h = int(parts[0])
        m = int(parts[1])
        return h * 60 + m

    def on_minute(self, context):
        bar = context.minute_bars.get(self.symbol)
        if not isinstance(bar, dict):
            return 0.0

        bar_year, bar_month, bar_day, bar_hour, bar_minute = context.minute_key
        bar_date = date(bar_year, bar_month, bar_day)
        bar_minutes = bar_hour * 60 + bar_minute
        start_time_str = str(context.strategy_params.get("start_time") or self.start_time or "")
        end_time_str = str(context.strategy_params.get("end_time") or self.end_time or "")
        if start_time_str:
            open_minutes = self._hhmm_to_minutes(start_time_str)
        else:
            ot = self.markets.get_open_time(bar_date)
            open_minutes = ot.hour * 60 + ot.minute
            start_time_str = ot.strftime("%H:%M")
        if end_time_str:
            close_minutes = self._hhmm_to_minutes(end_time_str)
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
            print("🧮 ", f"[strat_bollinger] symbol={self.symbol} limit calculator reset after order cancellations.")
        eod_flatten = bool(context.strategy_params.get("eod_flatten", self.eod_flatten))
        eod_flatten_minutes = int(context.strategy_params.get("eod_flatten_minutes", 2))
        market_is_open = open_minutes <= bar_minutes < close_minutes
        if eod_flatten and bar_minutes >= close_minutes - eod_flatten_minutes:
            current_position = float(context.positions.get(self.symbol, {}).get("qty", 0.0) or 0.0)
            if abs(current_position) > 0:
                delta = -current_position
                order_type = "market" if market_is_open else "limit"
                limit_price = round(price_last, 2) if order_type == "limit" else None
                print("🏁 ", 
                    f"[strat_bollinger] symbol={self.symbol} EOD flatten at "
                    f"{bar_hour:02d}:{bar_minute:02d}; {order_type} order delta={delta:.0f}"
                )
                self.indicators["last_limit_price"] = None
                self.indicators["last_limit_side"] = None
                context.trading_state.add_strategy_amount(
                    self.symbol,
                    float(delta),
                    metadata={
                        "strategy": "strat_bollinger",
                        "order_type": order_type,
                        "limit_price": limit_price,
                        "eod_flatten": True,
                        "minute": context.minute_key,
                        "price": price_last,
                    },
                )
                return delta
            return 0.0

        if not market_is_open:
            print("⏭️ ", f"[strat_bollinger] symbol={self.symbol} outside trading window {start_time_str}-{end_time_str}; skipping.")
            return 0.0

        alpha = float(context.strategy_params.get("alpha", self.alpha) or self.alpha)
        dollar_vol_floor = strategy_dollar_vol_floor(context.strategy_params, price_last, self.vol_floor)
        risk_premium = float(context.strategy_params.get("risk_premium", self.risk_premium) or self.risk_premium)
        take_profit_factor = float(
            context.strategy_params.get("take_profit_factor", self.take_profit_factor) or self.take_profit_factor
        )

        volume_last = float(bar.get("v", bar.get("volume", 1.0)) or 1.0)
        zscore, ema_price, volatility = self.emac.calc_zscorew(
            price_last,
            alpha,
            volume_last,
            dollar_vol_floor,
        )
        print("📊 ", 
            f"[strat_bollinger] symbol={self.symbol} "
            f"zscore={float(zscore):.6f} volatility={float(volatility):.6f} risk_premium={float(risk_premium):.6f}"
        )

        pos_state = context.positions.get(self.symbol, {})
        current_position = float(pos_state.get("qty", 0.0) or 0.0)
        unrealized_pl = float(pos_state.get("unrealized_pl", 0.0) or 0.0)
        shares_owned = abs(float(current_position))
        last_entry_price = float(pos_state.get("last_entry_price", 0.0) or 0.0)

        take_profit_level = float(self.take_profit_threshold) * float(volatility)
        per_share_take_profit_level = float(take_profit_factor) * float(volatility)
        if shares_owned > 0:
            if current_position > 0 and last_entry_price < 0.0:
                pnl_per_share = price_last + last_entry_price
            elif current_position < 0 and last_entry_price > 0.0:
                pnl_per_share = last_entry_price - price_last
            else:
                pnl_per_share = unrealized_pl / shares_owned
        else:
            pnl_per_share = 0.0
        delta = 0.0
        take_profit_triggered = False
        take_profit_reason = ""

        if shares_owned > 0 and pnl_per_share > per_share_take_profit_level:
            take_profit_triggered = True
            take_profit_reason = "per_share"
            delta = -1.0 if current_position > 0 else 1.0
            print("🎯 ",
                f"[strat_bollinger] symbol={self.symbol} per-share take-profit triggered: "
                f"pnl_per_share={pnl_per_share:.2f} > per_share_take_profit_level={per_share_take_profit_level:.2f}"
            )
        elif abs(current_position) > 0 and unrealized_pl > take_profit_level:
            take_profit_triggered = True
            take_profit_reason = "aggregate"
            half_position = min(abs(float(current_position)), max(1.0, abs(float(current_position)) / 2.0))
            delta = -half_position if current_position > 0 else half_position
            print("🎯 ", 
                f"[strat_bollinger] symbol={self.symbol} take-profit rule triggered: "
                f"unrealized_pl={unrealized_pl:.2f} > take_profit_level={take_profit_level:.2f}"
            )
        elif zscore > risk_premium:
            delta = -float(self.shares_per_trade)
        elif zscore < -risk_premium:
            delta = float(self.shares_per_trade)

        self.indicators.update(
            {
                "price": price_last,
                "ema": float(ema_price),
                "volatility": float(volatility),
                "zscore": float(zscore),
                "position": current_position,
                "unrealized_pl": unrealized_pl,
                "pnl_per_share": pnl_per_share,
                "per_share_take_profit_level": per_share_take_profit_level,
                "take_profit_level": take_profit_level,
                "last_delta": delta,
            }
        )

        if delta != 0.0:
            if take_profit_triggered:
                order_type = "market"
                limit_price = None
                self.indicators["last_limit_price"] = None
                self.indicators["last_limit_side"] = None
                if take_profit_reason == "per_share":
                    print("💰 ",
                        f"[strat_bollinger] symbol={self.symbol} TAKE-PROFIT triggered: "
                        f"liquidating one share via market order because pnl_per_share={pnl_per_share:.2f} "
                        f"> per_share_take_profit_level={per_share_take_profit_level:.2f} (delta={delta:.0f})."
                    )
                else:
                    print("💰 ", 
                        f"[strat_bollinger] symbol={self.symbol} TAKE-PROFIT triggered: "
                        f"unrealized_pl={unrealized_pl:.2f} > take_profit_level={take_profit_level:.2f}; "
                        f"liquidating half position via market order (delta={delta:.0f})."
                    )
                context.trading_state.add_strategy_amount(
                    self.symbol,
                    delta,
                    metadata={
                        "strategy": "strat_bollinger",
                        "order_type": "market",
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
                        "unrealized_pl": unrealized_pl,
                        "pnl_per_share": pnl_per_share,
                        "per_share_take_profit_level": per_share_take_profit_level,
                        "take_profit_level": take_profit_level,
                    },
                )
            else:
                adjustment = risk_premium * float(volatility)
                min_limit_step = max(float(dollar_vol_floor), 0.0)
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
                context.trading_state.add_strategy_amount(
                    self.symbol,
                    delta,
                    metadata={
                        "strategy": "strat_bollinger",
                        "order_type": "limit",
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
                        "unrealized_pl": unrealized_pl,
                        "take_profit_level": take_profit_level,
                    },
                )

        return delta


_STATE_BY_SYMBOL: dict[str, BollingerState] = {}


def call_back(context):
    """Master-driver strategy callback.

    Usage:
        --strategy strat_bollinger:call_back
    """
    for symbol in context.minute_bars.keys():
        symbol_key = str(symbol).upper()
        if symbol_key not in _STATE_BY_SYMBOL:
            _STATE_BY_SYMBOL[symbol_key] = BollingerState(symbol=symbol_key)
        _STATE_BY_SYMBOL[symbol_key].on_minute(context)

    return None
