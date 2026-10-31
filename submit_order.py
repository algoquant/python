### Submits a trade order using the Alpaca SDK, and later submits a request to confirm the order.
# https://docs.alpaca.markets/docs/working-with-orders
# https://wire.insiderfinance.io/alpaca-algorithmic-trading-api-in-python-part-1-getting-started-with-paper-trading-efbff8992836
# https://alpaca.markets/sdks/python/trading.html

# You can submit a trade order by running this script in the terminal:
# python3 submit_order.py symbol, type, side, num_shares, delta
# 
# The delta is the adjustment to the limit price, compared to the ask or bid price.
# For example, if the ask price is $100, and the delta is $0.5,
# the limit price will be set to $99.5 for a buy order, or $100.5 for a sell order.
# 
# Examples:
# python3 submit_order.py SPY limit buy 1 0.5
# python3 submit_order.py SPY market sell 1 0.0 --env-file /path/to/.env


import os
import sys
import time
import argparse
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data.enums import DataFeed
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from MachineTrader.helpers.alpacasdk import AlpacAPI
from MachineTrader import GetArgs
from MachineTrader.helpers.utils import convert_to_nytzone
from MachineTrader.helpers.file_writing_helpers import refresh_order_daily_file_names


# --------- Create the SDK clients --------

# --------- Get the trading parameters from the command line arguments --------

# Supports automated CLI usage and interactive prompts for manual execution.


def parse_arguments():
    """Parse optional order arguments; fall back to prompts when incomplete."""
    args_handler = GetArgs()
    parser = argparse.ArgumentParser(
        description="Submit one trade order and fetch order confirmation.",
    )
    parser.add_argument("symbol", nargs="?", help="Ticker symbol, e.g. SPY")
    parser.add_argument("order_type", nargs="?", help="Order type: market or limit")
    parser.add_argument("side", nargs="?", help="Order side: buy or sell")
    parser.add_argument("shares", nargs="?", type=float, help="Quantity to trade")
    parser.add_argument("delta", nargs="?", type=float, help="Limit price adjustment")
    parser.add_argument("--env-file", type=str, default=".env", help="Path to environment file (default: .env)")
    return args_handler.parse_custom(parser)


# Get the environment file argument first (needed before creating clients)
temp_args = parse_arguments()
env_file = temp_args.env_file

# Create AlpacaSDK instance and initialize clients
alpaca_sdk = AlpacAPI()
trading_client, confirm_stream = alpaca_sdk.create_trade_clients(env_file=env_file)
# Create the Alpaca SDK data client for live and historical stock data
data_client = alpaca_sdk.create_data_client(env_file=env_file)

# Get the symbol, order_type, side, shares_per_trade, and delta from the user
args = temp_args
if all(
    value is not None
    for value in (args.symbol, args.order_type, args.side, args.shares, args.delta)
):
    symbol = args.symbol.strip().upper()
    order_type = args.order_type.strip().lower()
    side_input = args.side.strip().lower()
    shares_per_trade = float(args.shares)
    delta = float(args.delta)
else:
    # If not provided, prompt the user for input
    symbol = input("Enter symbol: ").strip().upper()
    order_type = input("Enter order type (market/limit): ").strip().lower()
    side_input = input("Enter side (buy/sell): ").strip().lower()
    shares_input = input("Enter number of shares to trade (default 1): ").strip()
    shares_per_trade = float(shares_input) if shares_input else 1
    delta_input = input("Enter price adjustment (default 0.5): ").strip()
    delta = float(delta_input) if delta_input else 0.5

# Convert side_input to OrderSide
if side_input == "buy":
    side = OrderSide.BUY
elif side_input == "sell":
    side = OrderSide.SELL
else:
    raise ValueError("Side must be 'buy' or 'sell'")


shares_available, shares_to_trade = alpaca_sdk.get_shares_to_trade(symbol, shares_per_trade, side)
print(f"Available shares for {symbol}: {shares_available}")
print(f"Submitted shares for {symbol}: {shares_to_trade}")

if shares_to_trade <= 0:
    print(f"No shares can be submitted for {symbol} with side={side}. Exiting.")
    sys.exit(1)

# symbol = "SPY"
# order_type = "market"
# order_type = "limit"
# side = OrderSide.BUY  # Set to BUY or SELL as needed
# side = OrderSide.SELL
# Adjustment to the limit price to make it below the ask or above the bid
# delta = 0.5



# --------- Create the file names --------

# Per-day CSV outputs for submitted orders, fills, and errors.

# Create the file names for the submitted trade orders and the fills
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
time_now = time_now.strftime("%Y-%m-%d %H:%M:%S")
dir_name = os.getenv("DATA_DIR_NAME")
daily_files = refresh_order_daily_file_names(dir_name, tzone)
submits_file = daily_files["submits_file"]
fills_file = daily_files["fills_file"]
error_file = daily_files["error_file"]


# --------- Define the order parameters --------

# For limit orders, derive price from latest bid/ask adjusted by delta.

# Define the order parameters based on the order type
if order_type == "market":
    # Submit market order
    order_params = MarketOrderRequest(
        symbol = symbol,
        qty = shares_to_trade,
        side = side,
        type = order_type,
        time_in_force = TimeInForce.DAY
    ) # end order_params
    print(f"Submitting a {order_type} {side} order for {shares_to_trade} shares of {symbol}")
elif order_type == "limit":
    # Get the limit order price based on the latest bid/ask prices
    # Create the request parameters for live stock prices - SIP for comprehensive data, or IEX for free data.
    quote_params = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.SIP)
    # Get the latest bid/ask price quotes - as a dictionary
    latest_quotes = data_client.get_stock_latest_quote(quote_params)
    price_quotes = latest_quotes[symbol]
    ask_price = price_quotes.ask_price
    bid_price = price_quotes.bid_price
    print(f"Latest quotes for {symbol}: Ask = {price_quotes.ask_price}, Bid = {price_quotes.bid_price}")
    if side == OrderSide.BUY:
        # Submit a limit order to buy at the current ask price minus a small adjustment
        limit_price = round(ask_price - delta, 2)
    elif side == OrderSide.SELL:
        # Submit a limit order to sell at the current bid price plus a small adjustment
        limit_price = round(bid_price + delta, 2)
    # Define the limit order parameters
    order_params = LimitOrderRequest(
        symbol = symbol,
        qty = shares_to_trade,
        side = side,
        type = order_type,
        limit_price = limit_price,
        extended_hours = True,
        time_in_force = TimeInForce.DAY
    ) # end order_params
    print(f"Submitting a {order_type} {side} order for {shares_to_trade} shares of {symbol} at {limit_price}")



# --------- Submit the trade order --------

# Submit once and persist the raw order payload for auditability.

try:
    daily_files = refresh_order_daily_file_names(dir_name, tzone)
    submits_file = daily_files["submits_file"]
    fills_file = daily_files["fills_file"]
    error_file = daily_files["error_file"]
    response = trading_client.submit_order(order_data=order_params)
    # Remember the order ID to get the order status later
    order_id = response.id
    print(f"Submitted {side} order for {shares_per_trade} shares of {symbol} with the order-id: {order_id}")
    # Append the submitted orders to a CSV file
    order_frame = response.model_dump()  # or response._raw for some SDKs
    order_frame = convert_to_nytzone(order_frame)
    order_frame = pd.DataFrame([order_frame])
    # Append to CSV (write header only if file does not exist)
    order_frame.to_csv(submits_file, mode="a", header=not os.path.exists(submits_file), index=False)
    print(f"Order appended to {submits_file}")
except Exception as e:
    # Convert error to string and save to CSV
    daily_files = refresh_order_daily_file_names(dir_name, tzone)
    submits_file = daily_files["submits_file"]
    fills_file = daily_files["fills_file"]
    error_file = daily_files["error_file"]
    error_msg = pd.DataFrame([{"timestamp: ": time_now, "symbol: ": symbol, "side: ": side, "error: ": str(e)}])
    error_msg.to_csv(error_file, mode="a", header=not os.path.exists(error_file), index=False)
    print(f"Trade order rejected: {e}")



# --------- Get the trade confirm --------

# Poll order status shortly after submission and persist confirmation data.

try:
    daily_files = refresh_order_daily_file_names(dir_name, tzone)
    submits_file = daily_files["submits_file"]
    fills_file = daily_files["fills_file"]
    error_file = daily_files["error_file"]
    # After submitting the order and getting the response object
    # Check the order status after waiting for 1 second
    print("Waiting 1 second for the order to be processed...")
    time.sleep(1)
    order_status = trading_client.get_order_by_id(order_id)
    print(f"Order status: {order_status.status}")
    order_frame = order_status.model_dump()  # or response._raw for some SDKs
    order_frame = convert_to_nytzone(order_frame)
    order_frame = pd.DataFrame([order_frame])
    # Append to CSV (write header only if file does not exist)
    order_frame.to_csv(fills_file, mode="a", header=not os.path.exists(fills_file), index=False)
    print(f"Order appended to {fills_file}")
except Exception as e:
    # Convert error to string and save to CSV
    daily_files = refresh_order_daily_file_names(dir_name, tzone)
    submits_file = daily_files["submits_file"]
    fills_file = daily_files["fills_file"]
    error_file = daily_files["error_file"]
    error_msg = pd.DataFrame([{"timestamp: ": time_now, "symbol: ": symbol, "side: ": side, "error: ": str(e)}])
    error_msg.to_csv(error_file, mode="a", header=not os.path.exists(error_file), index=False)
    print(f"Trade order not filled: {e}")
