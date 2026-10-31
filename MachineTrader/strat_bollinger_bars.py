### Bollinger strategy for minute bar prices.
# The strategy trades a single stock using the Z-score.
# The Z-score is equal to the difference between the current price minus its moving average EMA price, divided by the EMA volatility.
# If the z-score is below -1, then it buys the stock.
# If the z-score is above 1, then it sells the stock.
# The strategy uses the real-time stock prices streaming via a proxy server.

# This is only an illustration how to use the streaming real-time data, using the Alpaca websocket. 
# This is only for illustration purposes, and not a real trading strategy.

# Run examples:
# Local data proxy websocket (default):
#   python3 strat_bollinger_bars.py SPY
# SDK data client fallback (explicit):
#   python3 strat_bollinger_bars.py SPY --direct
# Local proxy websocket:
#   python3 strat_bollinger_bars.py SPY --proxy
# Symbol defaults to SPY if omitted:
#   python3 strat_bollinger_bars.py --proxy

# Backtest note: this legacy standalone script does not expose a
# master_backtest callback. Use MachineTrader.strat_bollinger_limit:call_back
# for the current backtest-compatible Bollinger implementation.

import time
import json
import asyncio
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
import os
import sys
import signal
from types import SimpleNamespace
import websockets
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from MachineTrader.helpers.alpacasdk import AlpacAPI
from MachineTrader.helpers.driver_common import rounded_print as _rounded_print
from MachineTrader import GetArgs, start_heartbeat_task
from MachineTrader.helpers.file_writing_helpers import sync_strategy_daily_file_names
from MachineTrader.helpers.file_handlers import append_strategy_symbol_indicator_csvs


def print(*args, **kwargs):
    _rounded_print(*args, **kwargs)


# --------- Create the SDK clients --------

# --------- Parse command line arguments --------

# Optional flags:
#   --proxy  -> use local proxy stream (default)
#   --direct -> force Alpaca direct websocket


def parse_arguments():
    """Parse strategy args and stream flags while preserving legacy bare flags."""
    args_handler = GetArgs()
    raw_args = [arg.strip() for arg in sys.argv[1:]]
    normalized_args = args_handler.normalize_legacy_flags(raw_args, {"proxy", "direct"})

    parser = argparse.ArgumentParser(
        description="Run Bollinger minute-bar strategy with optional proxy/direct stream source.",
    )
    parser.add_argument("trade_symbol", nargs="?", help="Ticker symbol, e.g. SPY")
    parser.add_argument("shares_per_trade", nargs="?", type=float)
    parser.add_argument("order_type", nargs="?", help="Order type: market or limit")
    parser.add_argument("vol_floor", nargs="?", type=float)
    parser.add_argument("deltap", nargs="?", type=float)
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
    parsed_args.vol_floor,
    parsed_args.deltap,
]
provided_args = [value for value in cli_args if value is not None]

# Default mode is proxy stream with SDK data client fallback.
# If --direct is present it takes precedence over proxy/default.
feed_source = "direct" if use_direct else "proxy"
HEARTBEAT_INTERVAL = float(os.getenv("HEARTBEAT_INTERVAL", "60"))

# Create AlpacAPI instance and initialize clients
alpaca_sdk = AlpacAPI()
# Create a trading client for submitting orders and receiving confirms
alpaca_sdk.create_trade_clients()

# Create the SDK live data stream client for real-time stock prices.
data_client = alpaca_sdk.create_data_stream_client()
# Get the trading client from SDK
trading_client = alpaca_sdk.get_trading_client()


# Define the trading parameters
if len(provided_args) >= 5:
    trade_symbol = parsed_args.trade_symbol.strip().upper()
    shares_per_trade = float(parsed_args.shares_per_trade)
    order_type = parsed_args.order_type.strip().lower()
    vol_floor = float(parsed_args.vol_floor)
    deltap = float(parsed_args.deltap)
elif len(provided_args) >= 4:
    trade_symbol = parsed_args.trade_symbol.strip().upper()
    shares_per_trade = float(parsed_args.shares_per_trade)
    order_type = parsed_args.order_type.strip().lower()
    vol_floor = float(parsed_args.vol_floor)
    deltap = 0.1
elif len(provided_args) >= 3:
    trade_symbol = parsed_args.trade_symbol.strip().upper()
    shares_per_trade = float(parsed_args.shares_per_trade)
    order_type = parsed_args.order_type.strip().lower()
    vol_floor = 0.02
    deltap = 0.1
elif len(provided_args) >= 2:
    trade_symbol = parsed_args.trade_symbol.strip().upper()
    shares_per_trade = float(parsed_args.shares_per_trade)
    order_type = "limit"
    vol_floor = 0.02
    deltap = 0.1
elif len(provided_args) >= 1:
    trade_symbol = parsed_args.trade_symbol.strip().upper()
    shares_per_trade = 1
    order_type = "limit"
    vol_floor = 0.02
    deltap = 0.1
else:
    trade_symbol = input("Enter symbol (default SPY): ").strip().upper() or "SPY"
    shares_input = input("Enter number of shares to trade (default 1): ").strip()
    shares_per_trade = float(shares_input) if shares_input else 1
    order_type = input("Enter order type (market/limit, default limit): ").strip().lower() or "limit"
    vol_floor_input = input("Enter volatility floor (default 0.02): ").strip()
    vol_floor = float(vol_floor_input) if vol_floor_input else 0.02
    deltap_input = input("Enter limit price adjustment delta (default 0.1): ").strip()
    deltap = float(deltap_input) if deltap_input else 0.1

print(
    f"Trading parameters: symbol={trade_symbol}, shares_per_trade={shares_per_trade}, "
    f"order_type={order_type}, vol_floor={vol_floor}, deltap={deltap}\n"
)

shares_owned = 0  # Number of shares currently owned
# order_type = "market"
# order_type = "limit"
# side = OrderSide.BUY  # Set to BUY or SELL as needed
# Adjustment to the limit price to make it below the ask or above the bid
# deltap = 0.1  # The delta price adjustment for the limit order
# vol_floor = 0.02  # The volatility floor
price_vol = vol_floor  # The price volatility, used to calculate the z-score

# Create the strategy name
strategy_name = f"StratBoll_{trade_symbol}_ns{shares_per_trade}_order{order_type}_floor{vol_floor}"



# Create file names with today's NY date
timezone = ZoneInfo("America/New_York")
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
print(f"The state file is: {state_file}\n")
print(f"The canceled orders file is: {canceled_file}\n")
print(f"The order errors file is: {error_file}\n")
print(f"Feed source: {'sdk_data_client' if feed_source == 'direct' else 'data_proxy'}\n")

# Configure SDK-managed files used by submit_order logging.
alpaca_sdk.state_file = state_file
alpaca_sdk.submits_file = None
alpaca_sdk.fills_file = fills_file
alpaca_sdk.canceled_file = canceled_file
alpaca_sdk.error_file = error_file
if not hasattr(alpaca_sdk, "orders_list") or alpaca_sdk.orders_list is None:
    alpaca_sdk.orders_list = {}

# Initialize the strategy state variables
position = 0  # The current position - the number of shares owned
shares_available = 0  # The number of available shares to trade, according to the broker
strategy_position_shares = 0.0  # Net position tracked only from this strategy's fills file


def get_strategy_position_from_fills(path):
    """Compute strategy-local net shares from this strategy's fills CSV."""
    if not path or not os.path.exists(path):
        return 0.0

    try:
        fills = pd.read_csv(path)
        if fills.empty:
            return 0.0

        if "side" not in fills.columns:
            return 0.0

        qty_col = "filled_qty" if "filled_qty" in fills.columns else ("qty" if "qty" in fills.columns else None)
        if qty_col is None:
            return 0.0

        qty_series = pd.to_numeric(fills[qty_col], errors="coerce").fillna(0.0)
        side_series = fills["side"].astype(str).str.lower()
        signed_qty = qty_series.where(side_series.str.endswith("buy"), -qty_series.where(side_series.str.endswith("sell"), 0.0))
        return float(signed_qty.sum())
    except Exception as e:
        print(f"Failed to compute strategy position from fills file {path}: {e}")
        return 0.0



# The callback trading function is called after each price bar is received
async def trade_bars(bar):
    global strategy_position_shares

    # Accept either direct Alpaca bar objects or proxy dict events.
    if isinstance(bar, dict):
        if bar.get("S") != trade_symbol:
            return

        bar = alpaca_sdk.convert_bar(bar)
        if bar is None:
            return

        bar.timestamp = bar.timestamp.astimezone(tzone)

    file_names = sync_strategy_daily_file_names(alpaca_sdk, strategy_name, dir_name, timezone)
    state_file = file_names["state_file"]
    fills_file = file_names["fills_file"]
    canceled_file = file_names["canceled_file"]
    error_file = file_names["error_file"]
    # print(f"Bar price: {bar}")
    # print(f"Symbol: {bar.symbol}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}, Trade_count: {bar.trade_count}, VWAP: {bar.vwap}")
    close_price = bar.close
    price_ema = bar.vwap  # The EMA price is the VWAP price
    timestamp = bar.timestamp.astimezone(tzone)
    date_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    print(f"Time: {date_time}, Symbol: {bar.symbol}, Close: {close_price}, VWAP: {price_ema}")

    # Track position only from this strategy's fills file.
    strategy_position_shares = get_strategy_position_from_fills(fills_file)
    # Broker shares remain useful for sell-side risk checks.
    shares_available = alpaca_sdk.get_available_shares(trade_symbol)

    # Print the current strategy position and broker available shares
    print(f"Strategy position (fills only): {strategy_position_shares}")
    print(f"Shares available to trade: {shares_available}")

    # Calculate the z-score of the price relative to the EMA price
    zscore = (close_price - price_ema) / price_vol  # Z-score of the price relative to the EMA price
    append_strategy_symbol_indicator_csvs(
        metric_file_owner,
        minute_bars={trade_symbol: {"t": bar.timestamp}},
        zscores_by_symbol={trade_symbol: float(zscore)},
        ema_by_symbol={trade_symbol: float(price_ema)},
        volatility_by_symbol={trade_symbol: float(bar.high - bar.low)},
        symbol_order=[trade_symbol],
    )

    # If the absolute value of the z-score is greater than 1, then submit a trade order
    if abs(zscore) > (1): # If the price is significantly different from the EMA price
        # Define the order parameters and side first, then use side-aware share checks.
        if zscore > 1:
            # Submit a sell order
            side = OrderSide.SELL
            # Limit price is equal to the last price plus a small adjustment
            limit_price = round(close_price + deltap, 2)
        elif zscore < (-1):
            # Submit a buy order
            side = OrderSide.BUY
            # Limit price is equal to the last price minus a small adjustment
            limit_price = round(close_price - deltap, 2)

        broker_available, shares_to_trade = alpaca_sdk.get_shares_to_trade(trade_symbol, shares_per_trade, side)
        print(f"Broker shares available: {broker_available}; Shares to submit: {shares_to_trade}")

        if shares_to_trade > 0:
            # Submit the trade order with side-aware capped quantity.
            order_data = alpaca_sdk.submit_order(trade_symbol, shares_to_trade, side, order_type, limit_price)
            if order_data is None:
                # If the order submission failed, cancel all the open orders
                print(f"Trade order submission failed for {trade_symbol}")
                print(f"Cancelling all open orders for {trade_symbol}")
                # Cancel all open orders for the symbol
                alpaca_sdk.cancel_orders(trade_symbol, None, canceled_file)
                # Submit the trade order again
                order_data = alpaca_sdk.submit_order(trade_symbol, shares_to_trade, side, order_type, limit_price)
        else:
            print(f"No trade executed: side={side}, broker_available={broker_available}, shares_per_trade={shares_per_trade}")
    else:
        print(f"Last price {close_price} is too close to the EMA price {price_ema} - no trade executed for {trade_symbol}")
        side = None


    # Save the strategy state to a CSV file
    state_data = {
        "date_time": date_time,
        "symbol": bar.symbol,
        "price": bar.close,
        "volatility": (bar.high - bar.low),
        "zscore": zscore,
        "order": side,
        "shares_owned": strategy_position_shares,
        "pnlReal": 0,
        "pnlUnreal": 0,
    }
    state_data = pd.DataFrame([state_data])
    state_data.to_csv(state_file, mode="a", header=not os.path.exists(state_file), index=False)
    print("Done\n")

# End of callback function trade_bars


async def preflight_proxy_stream(data_proxy_url: str, timeout_seconds: float = 5.0) -> bool:
    """Validate proxy websocket reachability before entering stream loop."""
    try:
        async with websockets.connect(data_proxy_url, open_timeout=timeout_seconds, close_timeout=timeout_seconds):
            print(f"Proxy preflight OK: {data_proxy_url}")
            return True
    except Exception as exc:
        print(f"Proxy preflight failed for {data_proxy_url}: {exc}")
        return False


async def run_proxy_stream():
    """Read bars from local proxy and pass them into strategy callback.

    Returns:
        bool: True if proxy loop ran without exhausting retries, False to signal fallback.
    """
    # Reconnect on transient proxy disconnects, then fall back to SDK data client.
    data_proxy_url = os.getenv("DATA_PROXY_URL", "ws://localhost:8765")
    reconnect_delay = 5
    max_proxy_retries = 3
    retry_count = 0
    heartbeat_task = start_heartbeat_task(
        "heartbeat",
        HEARTBEAT_INTERVAL,
        loop_name="run_proxy_stream",
        symbol=trade_symbol,
        feed_source=feed_source,
        data_proxy_url=data_proxy_url,
    )

    try:
        while retry_count < max_proxy_retries:
            try:
                async with websockets.connect(data_proxy_url) as ws:
                    print(f"Connected to WebSocket proxy at {data_proxy_url}")
                    retry_count = 0
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            events = data if isinstance(data, list) else [data]
                            for event in events:
                                await trade_bars(event)
                        except Exception as e:
                            print(f"Error processing proxy message: {e}")
            except Exception as e:
                retry_count += 1
                print(f"Proxy WebSocket error: {e}. Reconnecting in {reconnect_delay} seconds...")
                await asyncio.sleep(reconnect_delay)
    finally:
        heartbeat_task.cancel()

    print("Proxy stream unavailable after retries. Falling back to SDK data client stream.")
    return False


def run_direct_stream():
    """Subscribe to Alpaca live bars and run the direct websocket stream."""
    # Used when proxy is disabled or unavailable.
    data_client.subscribe_bars(trade_bars, trade_symbol)

    try:
        data_client.run()
    except Exception as e:
        time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
        error_text = f"{time_stamp} WebSocket error: {e}. Restarting connection in 5 seconds..."
        print(error_text)
        with open(error_file, "a") as f:
            f.write(error_text)
        time.sleep(5)



# --------- Handle Ctrl-C interrupt --------

# Stop stream clients cleanly so websocket sessions terminate quickly.

# The code below stops the stream when the user presses Ctrl-C

def signal_handler(sig, frame):
    # Handle Ctrl-C (SIGINT) gracefully
    print("\n\nCtrl-C pressed! Exiting...")
    # Stop the stream client before exiting
    try:
        if data_client is not None:
            data_client.stop()
            print("Stream stopped by user.")
    except Exception:
        pass
    sys.exit(0)

# Set up signal handler for Ctrl-C
print("Press Ctrl-C to stop the stream... \n")
signal.signal(signal.SIGINT, signal_handler)

if __name__ == "__main__":
    if feed_source == "proxy":
        data_proxy_url = os.getenv("DATA_PROXY_URL", "ws://localhost:8765")
        preflight_ok = asyncio.run(preflight_proxy_stream(data_proxy_url))
        if not preflight_ok:
            print("Proxy unavailable at startup. Falling back to SDK data client stream.")
            run_direct_stream()
        else:
            proxy_ok = asyncio.run(run_proxy_stream())
            if not proxy_ok:
                run_direct_stream()
    else:
        # Subscribe to quote or trade updates
        # data_client.subscribe_quotes(handle_quote, symbol)
        # data_client.subscribe_trades(handle_trade, symbol)
        run_direct_stream()


