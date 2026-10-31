"""strat_trendpreopen - Once-daily entry from the premarket price move.

Overview
--------
For each configured symbol, the strategy records the first observed price from
STRATEGY_START_TIME through 09:29 and compares it with the 09:30 bar price:

     premarket_return = price_at_0930 - first_premarket_price

The sign of this dollar price difference determines a fixed long or short target.
A positive move targets a long position and a negative move targets a short
position. STRATEGY_REVERSE flips that target direction.

The strategy makes at most one entry decision per symbol per day. It submits the
difference between the target and the current position, then marks that symbol's
daily entry attempt complete. It does not resize the position later in the day.

Trading Logic
-------------
1. Reset symbol state when the date in context.minute_key changes.
2. Capture the first available bar at or after STRATEGY_START_TIME and before
    09:30 as the premarket baseline. If no such bar arrives, no entry is made.
3. On a 09:30 bar, capture the open reference and calculate:

         premarket_return = price_at_0930 - first_premarket_price

4. Wait until at least second 10 of the 09:30 minute when the bar payload has
    second-level precision. If that opportunity is unavailable, enter on the
    first later-minute bar.
5. Convert the return sign to a position target:
    - positive return -> +quantity shares,
    - negative return -> -quantity shares,
    - zero return -> 0 shares,
    - STRATEGY_REVERSE negates the target.
    Per-symbol quantity is read from quantity_by_symbol, converted to an absolute
    value, and rounded to a whole number of shares.
6. If STRATEGY_POS_CAP is greater than zero, clamp the entry target to
    [-STRATEGY_POS_CAP, STRATEGY_POS_CAP].
7. Submit target minus current position as signed market-order intent. Outside
    regular market hours, the master driver may convert it to a limit order.
8. Record price, baseline, 09:30 price, premarket return, target, position, and
    requested delta for shared momentum reporting.

EOD Position Handling
---------------------
This strategy does not liquidate positions itself. When STRATEGY_EOD_FLATTEN is
enabled, the shared MasterDriver submits liquidation orders at
STRATEGY_END_TIME before passing the after-end bar to this strategy. If price
bars stop arriving, the shared driver uses its 65-second wall-clock fallback.

Examples
--------
    python3 -m MachineTrader.master_momentum \\
        --strategy MachineTrader.strat_trendpreopen:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum

Backtest one trading day:

    python3 -m MachineTrader.master_backtest \\
        --strategy MachineTrader.strat_trendpreopen:call_back \\
        --env-file /Users/jerzy/Develop/trading/config/.env_momentum \\
        --date 2026-09-04
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import MachineTrader.helpers.file_handlers as _file_handlers
from MachineTrader.helpers.calc_ema_class import EMACalculator
from MachineTrader.helpers.parse_args import hhmm_to_minutes_or_default as _hhmm_to_minutes_or_default
from MachineTrader.helpers.timestamp_utils import bar_second_from_payload as _bar_second_from_payload
from MachineTrader.helpers.driver_common import (
    cap_target_position as _cap_target_position,
    rounded_print as _rounded_print,
    strategy_dollar_vol_floor as _strategy_dollar_vol_floor,
    strategy_param_float as _strategy_param_float,
)


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


@dataclass
class FlipOpenState:
    symbol: str
    alpha: float = 0.99
    vol_floor: float = 0.1
    indicators: dict[str, Any] = field(default_factory=dict)
    _day_key: tuple[int, int, int] | None = None
    _premarket_start_price: float | None = None
    _price_0930: float | None = None
    _premarket_return: float | None = None
    _entry_submitted: bool = False

    def __post_init__(self):
        self.symbol = self.symbol.upper()
        self.emac = EMACalculator()
        self.indicators = {
            "price": None,
            "ema": None,
            "volatility": None,
            "zscore": None,
            "premarket_start_price": None,
            "premarket_price_0930": None,
            "premarket_return": None,
            "entry_target": 0.0,
            "position": 0.0,
            "last_delta": 0.0,
        }

    def _reset_for_day(self, day_key: tuple[int, int, int]):
        self._day_key = day_key
        self._premarket_start_price = None
        self._price_0930 = None
        self._premarket_return = None
        self._entry_submitted = False

    @staticmethod
    def _bar_minutes(minute_key: tuple[int, int, int, int, int]) -> int:
        _, _, _, hh, mm = minute_key
        return int(hh) * 60 + int(mm)

    @staticmethod
    def _signal_side_from_premarket_return(premarket_return: float) -> int:
        if premarket_return == 0.0:
            return 0
        return -1 if premarket_return < 0.0 else 1

    def calculate_indicators(self, context) -> bool:
        bar = context.minute_bars.get(self.symbol)
        if not isinstance(bar, dict):
            self.indicators["last_delta"] = 0.0
            return False

        if not isinstance(context.minute_key, tuple) or len(context.minute_key) != 5:
            self.indicators["last_delta"] = 0.0
            return False

        year, month, day, _, _ = context.minute_key
        day_key = (int(year), int(month), int(day))
        if self._day_key != day_key:
            self._reset_for_day(day_key)

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
        minute_of_day = self._bar_minutes(context.minute_key)
        minute_0930 = (9 * 60) + 30
        start_time_text = str((context.strategy_params or {}).get("start_time", "07:30") or "07:30")
        start_minutes = _hhmm_to_minutes_or_default(start_time_text, default_minutes=(7 * 60) + 30)
        baseline_minutes = max(start_minutes, 0)

        # Premarket baseline is the earliest observed bar at or after STRATEGY_START_TIME,
        # while still before the 09:30 market open minute.
        if self._premarket_start_price is None and baseline_minutes <= minute_of_day < minute_0930:
            self._premarket_start_price = float(price_last)

        if minute_of_day == minute_0930:
            self._price_0930 = float(price_last)
            if self._premarket_start_price is not None:
                self._premarket_return = float(self._price_0930) - float(self._premarket_start_price)

        self.indicators.update(
            {
                "price": float(price_last),
                "ema": float(ema_price),
                "volatility": float(return_vol),
                "zscore": float(zscore),
                "premarket_start_price": self._premarket_start_price,
                "premarket_price_0930": self._price_0930,
                "premarket_return": self._premarket_return,
            }
        )
        return True

    def calculate_target(self, context) -> float:
        bar = context.minute_bars[self.symbol]
        price_last = float(self.indicators["price"])
        ema_price = float(self.indicators["ema"])
        return_vol = float(self.indicators["volatility"])
        zscore = float(self.indicators["zscore"])
        minute_of_day = self._bar_minutes(context.minute_key)
        minute_0930 = (9 * 60) + 30
        bar_second = _bar_second_from_payload(bar)

        qty_map = _quantity_map_from_params(context.strategy_params)
        quantity = float(qty_map.get(self.symbol, 1.0) or 1.0)
        quantity_shares = int(round(abs(quantity)))
        pos_cap = _strategy_param_float(
            context.strategy_params,
            "pos_cap",
            0.0,
            env_key="STRATEGY_POS_CAP",
        )

        current_position = float(context.positions.get(self.symbol, {}).get("qty", 0.0) or 0.0)
        current_position_shares = int(round(current_position))
        reverse_enabled = bool(context.strategy_params.get("strategy_reverse", False))

        delta = 0.0
        entry_target = 0

        # Entry gate: 10 seconds after the 09:30 open when second-level timestamp
        # is available, with a safe fallback to any later minute if 09:30 second
        # granularity is not emitted by the upstream bar stream.
        should_enter = False
        if not self._entry_submitted and quantity_shares > 0 and self._premarket_return is not None:
            if minute_of_day == minute_0930:
                should_enter = bool(bar_second is not None and bar_second >= 10)
            elif minute_of_day > minute_0930:
                should_enter = True

        if should_enter:
            premarket_return = float(self._premarket_return) if self._premarket_return is not None else 0.0
            signal_side = self._signal_side_from_premarket_return(premarket_return)
            entry_target = int(signal_side) * int(quantity_shares)
            if reverse_enabled:
                entry_target = -int(entry_target)
            entry_target = _cap_target_position(float(entry_target), pos_cap)
            delta = float(entry_target) - float(current_position_shares)
            self._entry_submitted = True

        context.trading_state.add_strategy_amount(
            self.symbol,
            float(delta),
            metadata={
                "strategy": "strat_trendpreopen",
                "reason": "momentum_trend_entry_093010" if abs(delta) > 1e-9 else "no_trade",
                "order_type": "market",
                "convert_market_to_limit_when_closed": True,
                "minute": context.minute_key,
                "price": float(price_last),
                "ema": float(ema_price),
                "volatility": float(return_vol),
                "return_vol": float(return_vol),
                "zscore": float(zscore),
                "premarket_start_price": self._premarket_start_price,
                "premarket_price_0930": self._price_0930,
                "premarket_return": self._premarket_return,
                "configured_quantity": float(quantity_shares),
                "pos_cap": float(pos_cap),
                "entry_target_position": float(entry_target),
            },
        )

        self.indicators.update(
            {
                "price": float(price_last),
                "premarket_start_price": self._premarket_start_price,
                "premarket_price_0930": self._price_0930,
                "premarket_return": self._premarket_return,
                "entry_target": float(entry_target),
                "pos_cap": float(pos_cap),
                "position": float(current_position),
                "last_delta": float(delta),
            }
        )

        return float(delta)

    def on_minute(self, context) -> float:
        if not self.calculate_indicators(context):
            return 0.0
        return self.calculate_target(context)


_STATE_BY_SYMBOL: dict[str, FlipOpenState] = {}


def _quantity_map_from_params(strategy_params: dict[str, Any]) -> dict[str, float]:
    raw_map = strategy_params.get("quantity_by_symbol", {})
    parsed: dict[str, float] = {}
    if isinstance(raw_map, dict):
        for symbol, qty in raw_map.items():
            symbol_key = str(symbol or "").strip().upper()
            if not symbol_key:
                continue
            try:
                parsed[symbol_key] = float(qty)
            except (TypeError, ValueError):
                continue
    return parsed


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
        --strategy MachineTrader.strat_trendpreopen:call_back
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
            _STATE_BY_SYMBOL[symbol_key] = FlipOpenState(symbol=symbol_key)

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
