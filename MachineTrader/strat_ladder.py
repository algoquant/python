"""
strat_ladder - price-band ladder strategy.
==========================================

Overview
--------
This strategy is signal-only. For each symbol it recalculates the EMA z-score
and volatility, then uses abs(last_fill_prices[symbol]) from the master driver
as the reference price for a trading band. This reference is independent of
the local position queue and remains available after the position becomes flat.

The driver seeds the reference from the first valid startup price and updates
it after confirmed fills. If no reference is available, use the current price.
The same band rules apply whether the position queue is empty or populated:

    upper_level = reference_price + price_buffer
    lower_level = reference_price - price_buffer

where the price buffer is:

    price_buffer = stock_volatility * STRATEGY_RISK_PREMIUM

    price_buffer = STRATEGY_RISK_PREMIUM * (
        volatility + STRATEGY_VOL_PREMIUM * abs(inventory_price) / price_quantity
    )

    The band is shifted to reduce inventory risk. With signed inventory quantity,
    the shift is positive for long inventory and negative for short inventory:

        inventory_price = position * close_price
        price_quantity = num_shares * close_price
        price_shift = STRATEGY_PRICE_PREMIUM * inventory_price / price_quantity
        upper_price = reference_price + price_buffer - price_shift
        lower_price = reference_price - price_buffer - price_shift

Trading rules
-------------
For each stock, the strategy follows this order:

1. Define num_shares = STRATEGY_QUANTITY.
   num_shares is the number of shares to trade.
2. Recalculate the z-score and volatility from the latest price bar.
3. Recalculate the reference price and the price band.
4. Set reference_price to abs(last_fill_prices[symbol]) supplied by the driver,
    or the current price if unavailable. Do not derive it from the position queue.
5. If the current price is below the lower level, set both the target position
   and the delta to +num_shares for a buy.
6. If the current price is above the upper level, set both the target position
   and the delta to -num_shares for a sell.
7. If the current price stays inside the band, set the target position and the
   delta to zero.
8. Always return the delta value; if delta == 0, return 0.

A positive delta means a buy, and a negative delta means a sell.

Notes
-----
- This module does not submit broker orders directly.
- The master driver remains responsible for execution.
- The strategy is intentionally simple: it only emits a signal when the price
  crosses the band created around the reference level.

Examples
--------
Run the ladder strategy with the default momentum driver:

    python3 -m MachineTrader.master_momentum \
        --strategy MachineTrader.strat_ladder:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_ladder

Run the ladder strategy with a custom symbol list and quantity:

    python3 -m MachineTrader.master_momentum SPY \
        --strategy MachineTrader.strat_ladder:call_back \
        --strategy-symbols AAPL,MSFT,TSLA \
        --strategy-param quantity_by_symbol='{"AAPL":2,"MSFT":1,"TSLA":1}' \
        --strategy-param risk_premium=2.0

Run with a custom reference risk premium and fixed trade size:

    python3 -m MachineTrader.master_momentum SPY \
        --strategy MachineTrader.strat_ladder:call_back \
        --strategy-param risk_premium=3.0 \
        --strategy-param strategy_quantity=4

Backtest one trading day:

    python3 -m MachineTrader.master_backtest \
        --strategy MachineTrader.strat_ladder:call_back \
        --env-file /Users/jerzy/Develop/trading/config/.env_ladder \
        --date 2026-09-04
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import MachineTrader.helpers.file_handlers as _file_handlers
from MachineTrader.helpers.calc_ema_class import EMACalculator
from MachineTrader.helpers.driver_common import (
    calculate_inventory_price_buffer as _calculate_inventory_price_buffer,
    calculate_inventory_price_shift as _calculate_inventory_price_shift,
    rounded_print as _rounded_print,
    strategy_dollar_vol_floor as _strategy_dollar_vol_floor,
    strategy_param_float as _strategy_param_float,
    strategy_quantity_by_symbol as _strategy_quantity_by_symbol,
)


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


@dataclass
class StrategyState:
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

    def _reference_price(self, context) -> float:
        last_fill_prices = getattr(context, "last_fill_prices", {})
        if isinstance(last_fill_prices, dict):
            try:
                fill_price = abs(float(last_fill_prices.get(self.symbol)))
            except (TypeError, ValueError):
                fill_price = 0.0
            if fill_price > 0.0:
                return fill_price
        return float(self.indicators["price"])

    def calculate_target(self, context) -> float:
        if not self.calculate_indicators(context):
            return 0.0

        price_last = float(self.indicators["price"])
        return_vol = float(self.indicators["volatility"])
        risk_premium = _strategy_param_float(
            context.strategy_params,
            "risk_premium",
            1.0,
            env_key="STRATEGY_RISK_PREMIUM",
        )
        qty_map = _strategy_quantity_by_symbol(context.strategy_params)
        num_shares = float(qty_map.get(self.symbol, 1.0) or 1.0)
        position = float(context.positions.get(self.symbol, {}).get("qty", 0.0) or 0.0)
        price_premium = _strategy_param_float(
            context.strategy_params,
            "price_premium",
            0.01,
            env_key="STRATEGY_PRICE_PREMIUM",
        )
        vol_premium = _strategy_param_float(
            context.strategy_params,
            "vol_premium",
            0.0,
            env_key="STRATEGY_VOL_PREMIUM",
        )

        reference_price = self._reference_price(context)
        price_shift = _calculate_inventory_price_shift(
            position,
            price_last,
            num_shares,
            price_premium,
        )
        inventory_price = float(position) * float(price_last)
        price_quantity = float(num_shares) * float(price_last)
        price_buffer = _calculate_inventory_price_buffer(
            return_vol,
            risk_premium,
            inventory_price,
            price_quantity,
            vol_premium,
        )
        upper_level = float(reference_price) + float(price_buffer) - float(price_shift)
        lower_level = float(reference_price) - float(price_buffer) - float(price_shift)

        delta = 0.0
        target_position = 0.0
        if price_last < lower_level:
            delta = float(num_shares)
            target_position = float(num_shares)
        elif price_last > upper_level:
            delta = -float(num_shares)
            target_position = -float(num_shares)

        self.indicators.update(
            {
                "reference_price": float(reference_price),
                "upper_level": float(upper_level),
                "lower_level": float(lower_level),
                "price_buffer": float(price_buffer),
                "inventory_price": float(inventory_price),
                "price_quantity": float(price_quantity),
                "price_shift": float(price_shift),
                "price_premium": float(price_premium),
                "vol_premium": float(vol_premium),
                "position": float(position),
                "target": float(target_position),
                "last_delta": float(delta),
            }
        )

        context.trading_state.add_strategy_amount(
            self.symbol,
            float(delta),
            metadata={
                "strategy": "strat_ladder",
                "reason": "band_trigger",
                "order_type": "market",
                "price": float(price_last),
                "reference_price": float(reference_price),
                "upper_level": float(upper_level),
                "lower_level": float(lower_level),
                "price_buffer": float(price_buffer),
                "inventory_price": float(inventory_price),
                "price_quantity": float(price_quantity),
                "price_shift": float(price_shift),
                "price_premium": float(price_premium),
                "vol_premium": float(vol_premium),
                "volatility": float(return_vol),
                "zscore": float(self.indicators["zscore"]),
                "ema": float(self.indicators["ema"]),
                "position": float(position),
                "target": float(target_position),
                "target_position": float(target_position),
                "num_shares": float(num_shares),
                "risk_premium": float(risk_premium),
            },
        )

        if delta == 0:
            return 0.0
        return float(delta)

    def on_minute(self, context) -> float:
        if not self.calculate_indicators(context):
            return 0.0
        return self.calculate_target(context)


_STATE_BY_SYMBOL: dict[str, StrategyState] = {}


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
        --strategy MachineTrader.strat_ladder:call_back
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
            _STATE_BY_SYMBOL[symbol_key] = StrategyState(symbol=symbol_key)

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
