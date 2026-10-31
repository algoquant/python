"""
Bollinger strategy trades a single stock using the streaming real-time stock price bars from the Alpaca API.
The Bollinger strategy uses the Z-score, equal to the difference between the stock's price minus its Moving Average Price (EMA), divided by the volatility.

    Z-score = (price - EMA) / volatility

The strategy uses streaming bar prices and streaming confirms via the Alpaca websocket API.

The strategy uses the contrarian rule based on the Bollinger Bands concept, where the Z-score indicates if the stock is cheap or rich (expensive).

To run the strategy, first change the path to the .env file.
Then run the strategy by executing this script with the appropriate parameters in the terminal:
    python3 strat_bollinger_bars_ema.py symbol num_shares type alpha vol_floor risk_premium take_profit_factor delay
For example:
    python3 strat_bollinger_bars_ema.py SPY 1 limit 0.9 0.1 1.0 20.0 5.0

Backtest note: this legacy standalone script does not expose a master_backtest
callback. Use MachineTrader.strat_bollinger_limit:call_back for the current
backtest-compatible Bollinger implementation.

The num_shares parameter specifies the number of shares for each trade.

The type parameter specifies the order type, either "market" or "limit".

The alpha parameter is the EMA decay parameter (0 < alpha <= 1).
It's used to calculate the Exponential Moving Average (EMA) of the stock price.
Larger alpha values apply more weight to past prices, with more smoothing, and a slower response to new prices.
Smaller alpha values provide less smoothing and a faster response to new prices.

The vol_floor is the minimum value of the dollar volatility used in the Z-score calculations.
This prevents division by very small numbers when the price volatility is low.
Typical values range from 0.01 to 0.2 depending on the asset and the time horizon.

The risk_premium parameter serves two purposes:
1. It adjusts the limit price for limit orders.
2. It serves as the threshold for the Z-score.

The risk_premium parameter is used to determine the limit price, compared to the ask or bid price.
The limit price adjustment pa is equal to the risk_premium parameter times the volatility.
For example, if the risk_premium is 2.0 and the volatility is $0.1, then the price adjustment pa is $0.2.
If the ask price is $100, then the limit buy price is set to $99.8.
If the bid price is $99, then the limit sell price is set to $99.2.
The subsequent limit order prices are spread apart by the price adjustment pa, to avoid submitting multiple limit orders at the same price.
If another limit order is submitted, then its price is set based on the previous limit order price and the risk_premium parameter.
For example, the next limit buy price after $99.8 would be set to $99.6.
This is to avoid submitting multiple limit orders at the same price.

The risk_premium serves as the threshold level for the Z-score.
If the Z-score is between -risk_premium and risk_premium, then the strategy does not trade.
If the Z-score is below -risk_premium, then it buys the stock.
If the Z-score is above +risk_premium, then it sells the stock.
It submits either limit or market orders when the Z-score is above +risk_premium or below -risk_premium.

The take_profit_factor is used to determine the take profit level for the strategy.
It is a multiplier applied to the average cost basis of the position.
For example, if the take_profit_factor is 2.0 and the average cost basis is $100, then the take profit level is set to $102.

The delay parameter specifies the number of seconds to wait before submitting trade orders.
This delay allows for better timing control and can help avoid rapid-fire trading.
For example, if the delay is 5.0, then the strategy will wait 5 seconds before submitting each trade order.
A delay of 0.0 means no delay (immediate order submission).

NOTE:
This script is only for illustration purposes, and not a real trading strategy.
This is only an illustration how to use the streaming real-time data from the Alpaca websocket. 
"""


import os
import sys
import asyncio
import argparse
import signal
import time
import math
import json
import glob
from functools import partial
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.data.enums import DataFeed
import websockets
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from MachineTrader.helpers.calc_ema_class import EMACalculator
from MachineTrader.helpers.alpacasdk import AlpacAPI, Trading
from MachineTrader.helpers.driver_common import dollar_vol_floor as _dollar_vol_floor, rounded_print as _rounded_print
from MachineTrader.helpers.master_driver_execution import handle_trade_update_signed_queue
from MachineTrader import GetArgs, to_float, format_data, start_heartbeat_task
from MachineTrader.helpers.file_writing_helpers import sync_strategy_daily_file_names
from MachineTrader.helpers.file_handlers import append_strategy_symbol_indicator_csvs


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


# --------- Create the SDK clients --------

# --------- Parse command line arguments --------

# Parse optional stream source flags before positional strategy args.
# --direct forces Alpaca stream; otherwise proxy is default with direct fallback.
# We strip these flags from cli_args so positional parsing remains unchanged.


def parse_arguments():
    """Parse strategy args and stream flags while preserving legacy bare flags."""
    args_handler = GetArgs()
    raw_args = [arg.strip() for arg in sys.argv[1:]]
    normalized_args = args_handler.normalize_legacy_flags(raw_args, {"proxy", "direct"})

    parser = argparse.ArgumentParser(
        description="Run EMA Bollinger strategy with optional proxy/direct stream source.",
    )
    parser.add_argument("trade_symbol", nargs="?")
    parser.add_argument("shares_per_trade", nargs="?", type=float)
    parser.add_argument("order_type", nargs="?")
    parser.add_argument("alpha", nargs="?", type=float)
    parser.add_argument("vol_floor", nargs="?", type=float)
    parser.add_argument("risk_premium", nargs="?", type=float)
    parser.add_argument("take_profit_factor", nargs="?", type=float)
    parser.add_argument("delay", nargs="?", type=float)
    parser.add_argument("--proxy", action="store_true", help="Use local proxy stream")
    parser.add_argument("--direct", action="store_true", help="Use direct Alpaca stream")
    return args_handler.parse_custom(parser, normalized_args)


parsed_args = parse_arguments()
use_proxy = parsed_args.proxy
use_direct = parsed_args.direct

cli_args = [
    parsed_args.trade_symbol,
    parsed_args.shares_per_trade,
    parsed_args.order_type,
    parsed_args.alpha,
    parsed_args.vol_floor,
    parsed_args.risk_premium,
    parsed_args.take_profit_factor,
    parsed_args.delay,
]
provided_args = [value for value in cli_args if value is not None]
# Default mode is proxy stream with Alpaca direct fallback.
feed_source = "direct" if use_direct else "proxy"
HEARTBEAT_INTERVAL = float(os.getenv("HEARTBEAT_INTERVAL", "60"))
STALE_DATA_WARN_SECONDS = max(30.0, HEARTBEAT_INTERVAL * 1.5)

# Create AlpacAPI instance and initialize clients
alpaca_sdk = AlpacAPI()
# Create a trading client for submitting orders and receiving confirms
alpaca_sdk.create_trade_clients()

# Create the SDK data client for live stock prices
data_client = alpaca_sdk.create_data_stream_client(feed=DataFeed.SIP)
# Get clients from SDK
trading_client = alpaca_sdk.get_trading_client()
confirm_stream = alpaca_sdk.get_confirm_stream()


# --------- Get the trading parameters from the command line arguments --------

# Positional args configure strategy parameters; interactive prompts are fallback.
# Expected order:
#   symbol shares_per_trade order_type alpha vol_floor risk_premium [take_profit_factor] [delay]

# Get the symbol, order_type, shares_per_trade, risk_premium, alpha, vol_floor, take_profit_factor, and delay from the command line arguments
if len(provided_args) >= 8:
    trade_symbol = parsed_args.trade_symbol.strip().upper()  # Symbol to trade
    shares_per_trade = float(parsed_args.shares_per_trade)  # Number of shares to trade
    order_type = parsed_args.order_type.strip().lower()  # Order type (market/limit)
    alpha = float(parsed_args.alpha)  # EMA alpha parameter
    vol_floor = float(parsed_args.vol_floor)  # Volatility floor
    risk_premium = float(parsed_args.risk_premium)  # Limit price adjustment
    take_profit_factor = float(parsed_args.take_profit_factor)  # Take profit level
    delay = float(parsed_args.delay)  # Delay before order submission (seconds)
elif len(provided_args) >= 7:
    trade_symbol = parsed_args.trade_symbol.strip().upper()  # Symbol to trade
    shares_per_trade = float(parsed_args.shares_per_trade)  # Number of shares to trade
    order_type = parsed_args.order_type.strip().lower()  # Order type (market/limit)
    alpha = float(parsed_args.alpha)  # EMA alpha parameter
    vol_floor = float(parsed_args.vol_floor)  # Volatility floor
    risk_premium = float(parsed_args.risk_premium)  # Limit price adjustment
    take_profit_factor = float(parsed_args.take_profit_factor)  # Take profit level
    delay = 0.0  # Default delay (no delay)
elif len(provided_args) >= 6:
    trade_symbol = parsed_args.trade_symbol.strip().upper()
    shares_per_trade = float(parsed_args.shares_per_trade)
    order_type = parsed_args.order_type.strip().lower()
    alpha = float(parsed_args.alpha)
    vol_floor = float(parsed_args.vol_floor)  # Volatility floor
    risk_premium = float(parsed_args.risk_premium)  # Limit price adjustment
    take_profit_factor = 20.0  # Default take profit level
    delay = 0.0  # Default delay (no delay)
elif len(provided_args) >= 5:
    trade_symbol = parsed_args.trade_symbol.strip().upper()
    shares_per_trade = float(parsed_args.shares_per_trade)  # Number of shares to trade
    order_type = parsed_args.order_type.strip().lower()  # Order type (market/limit)
    alpha = float(parsed_args.alpha)
    vol_floor = float(parsed_args.vol_floor)  # Volatility floor
    risk_premium = 2.0  # Default risk_premium value
    take_profit_factor = 20.0  # Default take profit level
    delay = 0.0  # Default delay (no delay)
elif len(provided_args) >= 4:
    trade_symbol = parsed_args.trade_symbol.strip().upper()
    shares_per_trade = float(parsed_args.shares_per_trade)  # Number of shares to trade
    order_type = parsed_args.order_type.strip().lower()  # Order type (market/limit)
    alpha = float(parsed_args.alpha)
    vol_floor = 0.1  # Default vol_floor value
    risk_premium = 2.0  # Default risk_premium value
    take_profit_factor = 20.0  # Default take profit level
    delay = 0.0  # Default delay (no delay)
else:
    # If not provided, prompt the user for input
    trade_symbol = input("Enter symbol: ").strip().upper()
    shares_input = input("Enter number of shares to trade (default 1): ").strip()
    shares_per_trade = float(shares_input) if shares_input else 1
    order_type = input("Enter order type (market/limit): ").strip().lower()
    alpha_input = input("Enter EMA alpha parameter (default 0.1): ").strip()
    alpha = float(alpha_input) if alpha_input else 0.1
    risk_premium_input = input("Enter price adjustment (default 0.5): ").strip()
    risk_premium = float(risk_premium_input) if risk_premium_input else 0.5
    vol_floor_input = input("Enter volatility floor (default 0.05): ").strip()
    vol_floor = float(vol_floor_input) if vol_floor_input else 0.05
    take_profit_input = input("Enter take profit level (default 2.0): ").strip()
    take_profit_factor = float(take_profit_input) if take_profit_input else 2.0
    delay_input = input("Enter delay before order submission in seconds (default 0.0): ").strip()
    delay = float(delay_input) if delay_input else 0.0

print(f"Trading parameters: symbol={trade_symbol}, order_type={order_type}, shares_per_trade={shares_per_trade}, alpha={alpha}, risk_premium={risk_premium}, vol_floor={vol_floor}, take_profit_factor={take_profit_factor}, delay={delay}\n")


# --------- Specify the strategy parameters --------

# Strategy state below is updated continuously by bar and trade callbacks.
# Values here represent in-memory strategy state and are not persisted unless written to CSV.

# symbol = "SPY"
# Specify the strategy name
# Add to the strategy name its parameters.
# For example: "StratBoll001_SPY_limit_1_0.5_0.9_0.05"
strategy_name = f"StratBoll_{trade_symbol}_ns{shares_per_trade}_order{order_type}_decay{alpha}_premium{risk_premium}_floor{vol_floor}_take{take_profit_factor}"
# Specify the trading parameters
# shares_per_trade = 1  # Number of shares to trade per each order
# order_type = "market"
# order_type = "limit"
# trade_side = OrderSide.BUY  # Set to BUY or SELL as needed
# The risk_premium parameter, for the Z-score threshold and for setting the limit price
# risk_premium = 2.0  # The risk_premium parameter

# Initialize the strategy state variables
# Signed-price queue by symbol: negative prices for long lots, positive for short lots.
position_queue = {str(trade_symbol).upper(): []}
position_shares = 0  # The number of shares currently owned (positive for long positions, negative for short positions)

# A negative shares_available value indicates that there is a short position.
# A positive shares_available value indicates that there is a long position.
shares_available = 0  # The number of available shares to trade, according to the broker
# Initialize the order response variable
order_response = None
order_id = None  # Initialize order_id variable
# Initialize last limit price tracking for staggered orders
last_buy_price = None  # Track the last buy limit price submitted
last_sell_price = None  # Track the last sell limit price submitted
# Initialize dictionary to track pending order IDs and their limit prices
# Positive prices for sell orders, negative prices for buy orders
orders_list = {}  # Dictionary of pending limit order IDs: {order_id: limit_price}
# Track cumulative filled quantity per order so partial fills are applied incrementally once.
order_filled_qty = {}
# Initialize the cumulative realized P&L
pnl_real = 0.0  # The cumulative realized P&L from closed positions
pnl_unreal = 0.0  # The unrealized PnL from open positions
price_vol = vol_floor  # The price volatility
# The price adjustment for limit orders
price_adjustment = risk_premium * price_vol
# The take profit level
take_profit_level = take_profit_factor * price_vol

# Create an instance of the EMACalculator for calculating the EMA prices and Z-scores
EMAC = EMACalculator()

# Keep a latest snapshot for heartbeat status output between bars.
latest_data = {
    "date_time": None,
    "price": None,
    "ema": None,
    "volatility": None,
    "zscore": None,
    "take_profit_level": None,
    "last_buy_price": None,
    "last_sell_price": None,
    "position_shares": 0,
    "pnl_real": 0.0,
    "pnl_unreal": 0.0,
    "pending_orders": 0,
    "last_feed": feed_source,
}

# Proxy stream health tracking for heartbeat warnings.
last_bar_monotonic = None
proxy_connected = False
last_warn_monotonic = None
trade_confirm_state = {
    "pnl_real": pnl_real,
    "position_shares": position_shares,
}


# --------- Create the file names --------

# Create file names with today's NY date
# Daily files keep strategy state, submit/fill events, cancellations, and runtime errors.
timezone = ZoneInfo("America/New_York")
time_now = datetime.now(timezone)
dir_name = os.getenv("DATA_DIR_NAME")
metric_file_owner = SimpleNamespace(
    strategy_params={
        "strategy_name": strategy_name,
        "log_dir_name": os.getenv("LOG_DIR_NAME") or dir_name,
    }
)
file_names = sync_strategy_daily_file_names(alpaca_sdk, strategy_name, dir_name, timezone)
state_file = file_names["state_file"]
fills_file = file_names["fills_file"]
canceled_file = file_names["canceled_file"]
error_file = file_names["error_file"]

# Keep SDK file handles fully populated for submit/cancel/state logging paths.
alpaca_sdk.state_file = state_file
alpaca_sdk.submits_file = None
alpaca_sdk.fills_file = fills_file
alpaca_sdk.canceled_file = canceled_file
alpaca_sdk.error_file = error_file


def read_state_from_file(csv_path):
    """Load and normalize the most recent strategy-state row from CSV."""
    if (not csv_path) or (not os.path.exists(csv_path)) or (os.path.getsize(csv_path) == 0):
        return None

    try:
        state_frame = pd.read_csv(csv_path, on_bad_lines="skip")
    except Exception as exc:
        print(f"⚠️ Could not read previous state file {csv_path}: {exc}")
        return None

    if state_frame.empty:
        return None

    last_row = state_frame.iloc[-1]
    raw_symbol = str(last_row.get("symbol", "")).strip().upper()
    normalized_symbol = "" if raw_symbol in {"", "NAN", "NONE"} else raw_symbol
    return {
        "date_time": str(last_row.get("date_time", "")),
        "symbol": normalized_symbol,
        "price": to_float(last_row.get("price"), None),
        "ema": to_float(last_row.get("ema"), None),
        "volatility": to_float(last_row.get("volatility"), None),
        "zscore": to_float(last_row.get("zscore"), None),
        "position_shares": int(round(to_float(last_row.get("position_shares"), 0.0) or 0.0)),
        "pnlReal": to_float(last_row.get("pnlReal"), 0.0) or 0.0,
        "pnlUnreal": to_float(last_row.get("pnlUnreal"), 0.0) or 0.0,
    }


def restore_state_from_snapshot(snapshot):
    """Restore coarse strategy state and seed EMA state for restart continuity."""
    global position_shares, pnl_real, pnl_unreal, latest_data, trade_confirm_state

    if not snapshot:
        print("ℹ️ No previous strategy state snapshot found for today.")
        return

    snapshot_symbol = snapshot.get("symbol")
    if snapshot_symbol and snapshot_symbol != trade_symbol:
        print(
            f"ℹ️ Previous snapshot in {state_file} is for {snapshot_symbol}; "
            f"current symbol is {trade_symbol}. Skipping restore."
        )
        return

    position_shares = int(snapshot.get("position_shares", 0) or 0)
    pnl_real = float(snapshot.get("pnlReal", 0.0) or 0.0)
    pnl_unreal = float(snapshot.get("pnlUnreal", 0.0) or 0.0)
    trade_confirm_state["position_shares"] = position_shares
    trade_confirm_state["pnl_real"] = pnl_real

    last_price = snapshot.get("price")
    last_ema = snapshot.get("ema")
    last_vol = snapshot.get("volatility")
    last_zscore = snapshot.get("zscore")
    last_ts = snapshot.get("date_time", "")

    if (last_price is not None) or (last_ema is not None):
        # Seed EMA internals so first post-restart bar does not reinitialize from scratch.
        seed_ema = last_ema if last_ema is not None else last_price
        seed_vol = max(float(last_vol or vol_floor), float(vol_floor))
        EMAC.price_ema = float(seed_ema)
        EMAC.price_var = float(seed_vol * seed_vol)
        EMAC.alpha1 = 1 - alpha
        EMAC.alpha_squared = alpha * alpha
        EMAC.alpha2 = 1 - EMAC.alpha_squared
        EMAC.volume = 1.0

    print("♻️ Restored previous strategy snapshot:")
    print(
        f"   Time: {last_ts}, Symbol: {trade_symbol}, Price: {last_price}, "
        f"EMA: {last_ema}, Vol: {last_vol}, Z-score: {last_zscore}, "
        f"Position: {position_shares}, PnL(real/unreal)=${pnl_real:.2f}/${pnl_unreal:.2f}"
    )

    latest_data.update(
        {
            "date_time": last_ts,
            "price": last_price,
            "ema": last_ema,
            "volatility": last_vol,
            "zscore": last_zscore,
            "take_profit_level": take_profit_factor * max(float(last_vol or vol_floor), float(vol_floor)),
            "last_buy_price": last_buy_price,
            "last_sell_price": last_sell_price,
            "position_shares": position_shares,
            "pnl_real": pnl_real,
            "pnl_unreal": pnl_unreal,
            "pending_orders": len(orders_list),
        }
    )


def get_state_from_file():
    """Populate latest_data from the newest available state CSV snapshot."""
    snapshot = read_state_from_file(state_file)

    if snapshot is None:
        state_pattern = os.path.join(dir_name or ".", f"state_*_{trade_symbol}_*.csv")
        candidates = sorted(
            [path for path in glob.glob(state_pattern) if os.path.isfile(path)],
            key=os.path.getmtime,
            reverse=True,
        )
        for candidate in candidates:
            snapshot = read_state_from_file(candidate)
            if snapshot is None:
                continue
            snapshot_symbol = str(snapshot.get("symbol") or "").strip().upper()
            if snapshot_symbol and snapshot_symbol != trade_symbol:
                continue
            break

    if snapshot is None:
        return False

    last_price = snapshot.get("price")
    last_ema = snapshot.get("ema")
    last_vol = snapshot.get("volatility")
    last_zscore = snapshot.get("zscore")
    last_ts = snapshot.get("date_time", "")
    pnl_real_snapshot = float(snapshot.get("pnlReal", 0.0) or 0.0)
    pnl_unreal_snapshot = float(snapshot.get("pnlUnreal", 0.0) or 0.0)
    vol_for_take = max(float(last_vol or vol_floor), float(vol_floor))

    latest_data.update(
        {
            "date_time": last_ts,
            "price": last_price,
            "ema": last_ema,
            "volatility": last_vol,
            "zscore": last_zscore,
            "take_profit_level": take_profit_factor * vol_for_take,
            "last_buy_price": last_buy_price,
            "last_sell_price": last_sell_price,
            "position_shares": int(snapshot.get("position_shares", 0) or 0),
            "pnl_real": pnl_real if pnl_real != 0.0 else pnl_real_snapshot,
            "pnl_unreal": pnl_unreal if pnl_unreal != 0.0 else pnl_unreal_snapshot,
            "pending_orders": len(orders_list),
        }
    )
    return True


async def print_heartbeat(interval, loop_name, **kwargs):
    """Emit heartbeat and include latest strategy state snapshot."""
    global last_warn_monotonic
    ny_tz = ZoneInfo("America/New_York")

    while True:
        if latest_data.get("price") is None:
            get_state_from_file()
        base_info = ", ".join([f"{key}={value}" for key, value in kwargs.items()])
        print(f"heartbeat(interval={interval}, loop_name={loop_name}, {base_info})")
        now_ny = datetime.now(ny_tz)
        print(
            "heartbeat_state(" 
            f"current_time={now_ny.strftime('%Y-%m-%d %H:%M:%S')}, "
            f"symbol={trade_symbol}, "
            f"time={latest_data.get('date_time') or 'n/a'}, "
            f"price={format_data(latest_data.get('price'), 4)}, "
            f"zscore={format_data(latest_data.get('zscore'), 4)}, "
            f"ema={format_data(latest_data.get('ema'), 4)}, "
            f"vol={format_data(latest_data.get('volatility'), 6)}, "
            f"take_profit={format_data(latest_data.get('take_profit_level'), 4)}, "
            f"last_buy_limit={format_data(latest_data.get('last_buy_price'), 4)}, "
            f"last_sell_limit={format_data(latest_data.get('last_sell_price'), 4)}, "
            f"last_fill_price={format_data(latest_data.get('filled_avg_price'), 4)}, "
            f"position={int(latest_data.get('position_shares') or 0)}, "
            f"pending={int(latest_data.get('pending_orders') or 0)}, "
            f"pnl_real={format_data(latest_data.get('pnl_real'), 2)}, "
            f"pnl_unreal={format_data(latest_data.get('pnl_unreal'), 2)}"
            ")"
        )

        if kwargs.get("feed_source") == "proxy":
            now_mono = time.monotonic()
            if getattr(alpaca_sdk, "proxy_connected", False):
                if last_bar_monotonic is None:
                    should_warn = (
                        (last_warn_monotonic is None)
                        or ((now_mono - last_warn_monotonic) >= STALE_DATA_WARN_SECONDS)
                    )
                    if should_warn:
                        print(
                            "⚠️ Proxy connected but no bar data received yet "
                            f"for {trade_symbol}."
                        )
                        last_warn_monotonic = now_mono
                else:
                    stale_seconds = now_mono - last_bar_monotonic
                    if stale_seconds >= STALE_DATA_WARN_SECONDS:
                        should_warn = (
                            (last_warn_monotonic is None)
                            or ((now_mono - last_warn_monotonic) >= STALE_DATA_WARN_SECONDS)
                        )
                        if should_warn:
                            print(
                                "⚠️ Proxy data stale: no bar data received for "
                                f"{stale_seconds:.1f}s (symbol={trade_symbol}, threshold={STALE_DATA_WARN_SECONDS:.1f}s)."
                            )
                            last_warn_monotonic = now_mono

        await asyncio.sleep(interval)


restore_state_from_snapshot(read_state_from_file(state_file))



# --------- Calculate the number of shares to trade to take profit on the unrealized P&L --------

# take_profit() computes side/limit/qty when unrealized PnL exceeds target threshold.

# Calculate the trade side and the number of shares to trade based on the Z-score and the available shares.
# Returns trade_side = None if no trade is to be made.
def take_profit(position_shares, price_last, shares_per_trade, shares_available, last_buy_price, last_sell_price, price_adjustment):

    # Initialize the trade buy/sell side variable and the limit price
    trade_side = None
    limit_price = None
    shares_to_trade = 0  # Initialize shares_to_trade to 0

    if position_shares > 0:
        # If the position is long stock - submit a sell trade order
        trade_side = OrderSide.SELL
        # The limit price is equal to the last sell price plus the price_adjustment adjustment
        if last_sell_price is None:
            limit_price = round(price_last + price_adjustment, 2)
        else:
            limit_price = round(max(price_last, last_sell_price) + price_adjustment, 2)
        last_sell_price = limit_price

    else: # position_shares < 0
        # The position is short stock - submit a buy trade order
        trade_side = OrderSide.BUY
        # The limit price is equal to the last buy price minus the price_adjustment adjustment
        if last_buy_price is None:
            limit_price = round(price_last - price_adjustment, 2)
        else:
            limit_price = round(min(price_last, last_buy_price) - price_adjustment, 2)
        last_buy_price = limit_price

    # The number of shares to trade is limited by the shares_available
    shares_to_trade = min(abs(shares_available), shares_per_trade)

    return trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price

# End of take_profit



# --------- Calculate the number of shares to trade based on the Z-score --------

# calc_shares_to_trade() applies the contrarian rule and position-aware sizing.

# Calculate the trade side and the number of shares to trade based on the Z-score and the available shares.
# Returns trade_side = None if no trade is to be made.
def calc_shares_to_trade(zscore, price_last, shares_per_trade, shares_available, last_buy_price, last_sell_price, risk_premium, price_adjustment):

    # Initialize the trade buy/sell side variable and the limit price
    trade_side = None
    limit_price = None
    shares_to_trade = 0  # Initialize shares_to_trade to 0

    # A negative shares_available value indicates that there is a short position.
    # In that case, the strategy can only buy back the shares it has sold short.
    # But it can sell more shares without limitation.

    # A positive shares_available value indicates that there is a long position.
    # In that case, the strategy can only sell the shares it owns.
    # But it can buy more shares without limitation.

    # If the Z-score is greater than the risk_premium, then submit a sell order
    # If the price is significantly different from the EMA price
    if zscore > risk_premium:
        # Submit a sell order if the price is significantly above the EMA price
        trade_side = OrderSide.SELL
        # The limit price is equal to the last sell price plus the price_adjustment adjustment
        if last_sell_price is None:
            limit_price = round(price_last + price_adjustment, 2)
        else:
            limit_price = round(max(price_last, last_sell_price) + price_adjustment, 2)
        last_sell_price = limit_price
        if shares_available > 0:
            # The number of shares to trade is limited by the shares_available
            shares_to_trade = min(abs(shares_available), shares_per_trade)
        else:
            # The number of shares to trade is equal to the shares_per_trade
            shares_to_trade = shares_per_trade

    # If the Z-score is less than minus the risk_premium, then submit a buy order
    elif zscore < (-risk_premium):
        # Submit a buy order if the price is significantly below the EMA price
        trade_side = OrderSide.BUY
        # The limit price is equal to the last buy price minus the price_adjustment adjustment
        if last_buy_price is None:
            limit_price = round(price_last - price_adjustment, 2)
        else:
            limit_price = round(min(price_last, last_buy_price) - price_adjustment, 2)
        last_buy_price = limit_price
        if shares_available < 0:
            # The number of shares to trade is limited by the shares_available
            shares_to_trade = min(abs(shares_available), shares_per_trade)
        else:
            # The number of shares to trade is equal to the shares_per_trade
            shares_to_trade = shares_per_trade

    else:
        # If the Z-score is not significant, do not trade
        print(f"⏸️ No trade for {trade_symbol} - the Z-score = {zscore:.2f} is not significant compared to the risk premium = {risk_premium}")
        shares_to_trade = 0

    return trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price

# End of calc_shares_to_trade



async def trade_bars(bar_event):
    """
    --------- Define the trading function - the callback handler for the price bars --------
    trade_bars() is the main decision loop executed on each incoming bar.
    trade_bars() receives the price bars and submits the trade orders.
    """
    global order_response, order_id, position_shares, last_buy_price, last_sell_price, orders_list, position_queue, pnl_unreal, pnl_real, latest_data, last_bar_monotonic, last_warn_monotonic, trade_confirm_state

    pnl_real = float(trade_confirm_state.get("pnl_real", pnl_real))

    # Convert dict object from proxy stream into a bar object, or accept the bar object directly from the Alpaca stream.
    if isinstance(bar_event, dict):
        if bar_event.get("S") != trade_symbol:
            return

        barobj = alpaca_sdk.convert_bar(bar_event)
        if barobj is None:
            return

        barobj.timestamp = barobj.timestamp.astimezone(timezone)

        last_bar_monotonic = time.monotonic()
        last_warn_monotonic = None
        latest_data["last_feed"] = "proxy"
    else:
        barobj = bar_event

    file_names = sync_strategy_daily_file_names(alpaca_sdk, strategy_name, dir_name, timezone)
    state_file = file_names["state_file"]
    fills_file = file_names["fills_file"]
    canceled_file = file_names["canceled_file"]
    error_file = file_names["error_file"]

    ### Get the latest price and volume from the price bar
    # print(f"Bar price: {barobj}")
    # print(f"Symbol: {barobj.symbol}, Open: {barobj.open}, High: {barobj.high}, Low: {barobj.low}, Close: {barobj.close}, Volume: {barobj.volume}, Trade_count: {barobj.trade_count}, VWAP: {barobj.vwap}")
    price_last = barobj.close
    volume_last = barobj.volume
    time_stamp = barobj.timestamp.astimezone(timezone)
    date_time = time_stamp.strftime("%Y-%m-%d %H:%M:%S")

    ### Print strategy information
    print(f"🎯 Strategy: {strategy_name}")
    print(f"⚙️ Parameters: symbol={trade_symbol}, shares={shares_per_trade}, order_type={order_type}, alpha={alpha}, vol_floor={vol_floor}, risk_premium={risk_premium}, take_profit_factor={take_profit_factor}, delay={delay}")


    ### Calculate the Z-score, EMA price, and price volatility
    dollar_vol_floor = _dollar_vol_floor(price_last, vol_floor)
    zscore, ema_price, price_vol = EMAC.calc_zscore_price_weighted(
        price_last,
        alpha,
        volume_last,
        dollar_vol_floor,
    )
    append_strategy_symbol_indicator_csvs(
        metric_file_owner,
        minute_bars={trade_symbol: {"t": barobj.timestamp}},
        zscores_by_symbol={trade_symbol: float(zscore)},
        ema_by_symbol={trade_symbol: float(ema_price)},
        volatility_by_symbol={trade_symbol: float(price_vol)},
        symbol_order=[trade_symbol],
    )
    # The price adjustment for limit orders
    price_adjustment = risk_premium * price_vol

    ### Calculate the unrealized P&L and update the stock positions
    trading_helper = Trading(trade_symbol)
    trading_helper._position_queue = position_queue
    trading_helper.last_price = price_last
    position_shares, pnl_unreal = trading_helper.calc_unrealized_pnl()

    ### Get the current position from the broker and the number of available shares to trade for the symbol
    _, shares_available, _ = alpaca_sdk.get_position_and_available_shares(trade_symbol, shares_per_trade)

    # Calculate the total number of buy and sell limit orders
    num_buy_orders = sum(1 for price in orders_list.values() if price < 0)
    num_sell_orders = sum(1 for price in orders_list.values() if price > 0)
    # Calculate the take profit level
    take_profit_level = take_profit_factor * price_vol

    print(f"📊 Time: {date_time}, Symbol: {barobj.symbol}, Z-score: {zscore:.2f}, Price: {price_last}, EMA: {ema_price:.2f}, Vol: {price_vol:.4f}")
    print(f"💼 Position: {position_shares} shares, Pending orders: {len(orders_list)} (Buy: {num_buy_orders}, Sell: {num_sell_orders}), Unrealized P&L: ${pnl_unreal:.2f}, Take Profit Level: ${take_profit_level:.2f}, Realized P&L: ${pnl_real:.2f}")
    print(f"📋 Current position queue: {position_queue.get(str(trade_symbol).upper(), [])}")
    # Print the current pending order IDs
    print(f"🔄 Current pending order IDs: {list(orders_list.keys())}")

    latest_data.update(
        {
            "date_time": date_time,
            "price": price_last,
            "ema": ema_price,
            "volatility": price_vol,
            "zscore": zscore,
            "take_profit_level": take_profit_level,
            "last_buy_price": last_buy_price,
            "last_sell_price": last_sell_price,
            "position_shares": position_shares,
            "pnl_real": pnl_real,
            "pnl_unreal": pnl_unreal,
            "pending_orders": len(orders_list),
            "last_feed": feed_source,
        }
    )

    ### Cancel all the open limit orders if the limit prices are too far apart
    if (last_buy_price is not None) and (last_sell_price is not None):
        if (last_sell_price - last_buy_price) > (10 * price_adjustment):
            # Cancel all the open limit orders
            print(f"\n❌ The limit prices are too far apart for {trade_symbol} - Canceling all open limit orders")
            remaining_order_ids = alpaca_sdk.cancel_orders(trade_symbol, list(orders_list.keys()))
            # Update orders_list to keep only the remaining orders
            orders_list = {order_id: orders_list[order_id] for order_id in remaining_order_ids if order_id in orders_list}
            last_sell_price = None  # Reset the last sell limit price
            last_buy_price = None  # Reset the last buy limit price


    ### If there are some shares available to trade, then either take profit on the unrealized P&L or execute the contrarian rule based on the Z-score.

    # Initialize the trade side
    trade_side = None

    if (shares_available != 0):

        # Apply the take-profit rule
        if (pnl_unreal > take_profit_level):
            print(f"\n💰 Take profit triggered for {trade_symbol}: Selling the position\n")
            print(f"💵 Unrealized PnL = {pnl_unreal:.2f} and Take profit level = {take_profit_level:.2f}\n")
            trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price = take_profit(position_shares, price_last, shares_per_trade, shares_available, last_buy_price, last_sell_price, price_adjustment)

        # Apply the contrarian rule based on the Z-score
        elif (abs(zscore) > abs(risk_premium)):
            print(f"\n🎯 Take profit not triggered for {trade_symbol} - Applying contrarian rule\n")
            # Calculate the trade side and the number of shares to trade based on the Z-score and the available shares.
            trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price = calc_shares_to_trade(zscore, price_last, shares_per_trade, shares_available, last_buy_price, last_sell_price, risk_premium, price_adjustment)

        else:
            print(f"\n⏸️ No trade conditions met for {trade_symbol}")

    ### Cancel all the open limit orders if there are no available shares for the symbol
    else:
        # No shares available
        # Cancel all the open limit orders
        print(f"\n⚠️ No shares available for {trade_symbol}")
        # print(f"\nNo shares available for {symbol} - Canceling all open limit orders")
        # orders_list = cancel_orders(trading_client, symbol, orders_list)
        # last_sell_price = None  # Reset the last sell limit price
        # last_buy_price = None  # Reset the last buy limit price


    ### Submit the trade order if the trade side is not None
    if trade_side is not None:

        print(f"Z-score: {zscore:.2f}, Side: {trade_side}, Limit price: {limit_price}, Shares to trade: {shares_to_trade}")
        
        # Apply delay before order submission if specified
        if delay > 0:
            print(f"⏱️ Waiting {delay} seconds before submitting order...")
            time.sleep(delay)
        
        order_response = None
        order_response = alpaca_sdk.submit_order(trade_symbol, shares_to_trade, trade_side, order_type, limit_price)

        # If the order submission failed, cancel all the open limit orders for the symbol and submit the order again
        if order_response is None:
            print(f"❌ Trade order submission failed for {trade_symbol}")
            # Do nothing - don't cancel all the open orders
            # pass
            print(f"🧹 Canceling all the open orders for {trade_symbol}")
            alpaca_sdk.cancel_orders(trade_symbol)
            # remaining_order_ids = cancel_orders(trading_client, symbol, list(orders_list.keys()))
            # Update orders_list to keep only the remaining orders
            # orders_list = {order_id: orders_list[order_id] for order_id in remaining_order_ids if order_id in orders_list}
            last_sell_price = None  # Reset the last sell limit price
            last_buy_price = None  # Reset the last buy limit price
            # Submit the trade order again
            print(f"🔄 Submitting the trade order again for {trade_symbol}")
            order_response = alpaca_sdk.submit_order(trade_symbol, shares_to_trade, trade_side, order_type, limit_price)

        # Add the order ID to the pending orders dictionary with signed limit price
        if order_response is not None:
            # Extract the order ID from the order_response
            order_id = str(order_response.id)
            # Store signed limit price: positive for sell orders, negative for buy orders
            signed_limit_price = limit_price if trade_side == OrderSide.SELL else -limit_price
            orders_list[order_id] = signed_limit_price
            print(f"✅ Added order ID {order_id} with limit price {signed_limit_price} to pending list. Total pending orders: {len(orders_list)}")
            # Print the current pending order IDs
            # print(f"Current pending order IDs: {orders_list}")
        else:
            print("❌ Failed to submit order after retry\n")
    else:
        trade_side = None # No trade executed, side remains None

    latest_data.update(
        {
            "last_buy_price": last_buy_price,
            "last_sell_price": last_sell_price,
            "position_shares": position_shares,
            "pnl_real": pnl_real,
            "pnl_unreal": pnl_unreal,
            "pending_orders": len(orders_list),
        }
    )


    ### Save the strategy state to the CSV file
    state_data = {
        "date_time": date_time,
        "symbol": barobj.symbol,
        "price": barobj.close,
        "ema": ema_price,
        "volatility": price_vol,
        "zscore": zscore,
        "order": trade_side,
        "position_shares": position_shares,
        "pnlReal": pnl_real,
        "pnlUnreal": pnl_unreal,
    }
    state_data = pd.DataFrame([state_data])
    state_data.to_csv(state_file, mode="a", header=not os.path.exists(state_file), index=False)
    print("✨ Done\n")

# End of callback function trade_bars



async def preflight_proxy_stream(data_proxy_url: str, timeout_seconds: float = 5.0) -> bool:
    """Validate proxy websocket reachability before starting stream tasks."""
    try:
        async with websockets.connect(data_proxy_url, open_timeout=timeout_seconds, close_timeout=timeout_seconds):
            print(f"Proxy preflight OK: {data_proxy_url}")
            return True
    except Exception as exc:
        print(f"Proxy preflight failed for {data_proxy_url}: {exc}")
        return False


# --------- Run the WebSocket to handle trade updates and confirmations, and exceptions and Ctrl-C interrupt --------
# --------- Run the data WebSocket stream --------

# main() runs bar stream and optional trade-confirm stream concurrently.
# In OAuth mode confirm_stream is unavailable, so only the data stream runs.

# Define the main function to run the WebSockets
async def main():

    data_proxy_url = os.getenv("DATA_PROXY_URL", "ws://localhost:8765")
    proxy_preflight_ok = True
    if feed_source == "proxy":
        proxy_preflight_ok = await preflight_proxy_stream(data_proxy_url)

    effective_feed_source = feed_source if proxy_preflight_ok else "direct"

    heartbeat_task = asyncio.create_task(
        print_heartbeat(
            HEARTBEAT_INTERVAL,
            "main",
            symbol=trade_symbol,
            feed_source=effective_feed_source,
            data_proxy_url=data_proxy_url,
        )
    )

    try:
        trade_update_callback = partial(
            handle_trade_update_signed_queue,
            trade_symbol=trade_symbol,
            alpaca_sdk=alpaca_sdk,
            strategy_name=strategy_name,
            dir_name=dir_name,
            timezone=timezone,
            orders_list=orders_list,
            position_queue=position_queue,
            order_filled_qty=order_filled_qty,
            latest_data=latest_data,
            pnl_real=pnl_real,
            position_shares=position_shares,
            state_ref=trade_confirm_state,
        )

        if feed_source == "proxy" and proxy_preflight_ok:
            latest_data["last_feed"] = "proxy"
            data_task = asyncio.create_task(
                alpaca_sdk.connect_proxy_stream(
                    trade_symbol,
                    trade_bars,
                    data_proxy_url=data_proxy_url,
                    on_fallback_direct=lambda: latest_data.__setitem__("last_feed", "direct"),
                )
            )
        else:
            if feed_source == "proxy" and not proxy_preflight_ok:
                print("Proxy unavailable at startup. Falling back to Alpaca direct stream.")
            latest_data["last_feed"] = "direct"
            data_task = asyncio.create_task(alpaca_sdk.run_direct_stream(trade_symbol, trade_bars))

        if confirm_stream is not None:
            # Subscribe to trade updates with driver-level confirmation handling.
            confirm_stream.subscribe_trade_updates(trade_update_callback)
            # Run both WebSocket streams concurrently
            print("\nStarting the data WebSocket connection...")
            print("\nStarting the trade updates and confirmations WebSocket connection...")
            await asyncio.gather(
                data_task,
                confirm_stream._run_forever()
            )
        else:
            # OAuth fallback provides TradingClient but no TradingStream credentials.
            print("\nStarting the data WebSocket connection...")
            print("\nTrade update stream disabled: OAuth fallback in use (no trade key/secret).")
            await data_task
    except Exception as e:
        pass  # Handle exceptions here if needed
        # print(f"WebSocket error: {e}")
    finally:
        print("\nClosing the trade updates and confirmations WebSocket connection...")
        heartbeat_task.cancel()
        try:
            await data_client.close()
            if confirm_stream is not None:
                await confirm_stream.close()
        except:
            pass  # Ignore errors when closing


# Check whether the script is being run directly or is imported as a module
if __name__ == "__main__":
    # Perform simplified event loop handling
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "Cannot be called from a running event loop" in str(e):
            print("Running in existing event loop/Users/jerzy/Develop/Python/.environment...")
            # Create a task in the existing loop
            loop = asyncio.get_event_loop()
            task = loop.create_task(main())
            # You might need to await this task manually in Jupyter
        else:
            # Suppress traceback for other RuntimeErrors
            print(f"Runtime error: {str(e)}")
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        # Suppress full traceback, just show error message
        print(f"Error occurred: {str(e)}")

