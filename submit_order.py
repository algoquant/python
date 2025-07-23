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
# Example:
# python3 submit_order.py SPY limit buy 1 0.5


import os
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockQuotesRequest, StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.enums import DataFeed
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from dotenv import load_dotenv
from utils import convert_to_nytzone


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

# Create the SDK trading client
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)
# Create the SDK data client for live and historical stock data
data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)



# --------- Get the trading parameters from the command line arguments --------

# Get the symbol, type, side, shares_per_trade, and delta from the user
if len(sys.argv) > 5:
    symbol = sys.argv[1].strip().upper()
    type = sys.argv[2].strip().lower()
    side_input = sys.argv[3].strip().lower()
    shares_per_trade = float(sys.argv[4])
    delta = float(sys.argv[5])
else:
    # If not provided, prompt the user for input
    symbol = input("Enter symbol: ").strip().upper()
    type = input("Enter order type (market/limit): ").strip().lower()
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

# symbol = "SPY"
# type = "market"
# type = "limit"
# side = OrderSide.BUY  # Set to BUY or SELL as needed
# side = OrderSide.SELL
# Adjustment to the limit price to make it below the ask or above the bid
# delta = 0.5



# --------- Create the file names --------

# Create the file names for the submitted trade orders and the fills
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
time_now = time_now.strftime("%Y-%m-%d %H:%M:%S")
dir_name = os.getenv("data_dir_name")
submits_file = f"{dir_name}submits_{date_short}.csv"
fills_file = f"{dir_name}fills_{symbol}_{date_short}.csv"


# --------- Define the order parameters --------

# Define the order parameters based on the order type
if type == "market":
    # Submit market order
    order_params = MarketOrderRequest(
        symbol = symbol,
        qty = shares_per_trade,
        side = side,
        type = type,
        time_in_force = TimeInForce.DAY
    ) # end order_params
    print(f"Submitting a {type} {side} order for {shares_per_trade} shares of {symbol}")
elif type == "limit":
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
        qty = shares_per_trade,
        side = side,
        type = type,
        limit_price = limit_price,
        extended_hours = True,
        time_in_force = TimeInForce.DAY
    ) # end order_params
    print(f"Submitting a {type} {side} order for {shares_per_trade} shares of {symbol} at {limit_price}")



# --------- Submit the trade order --------

try:
    response = trading_client.submit_order(order_data=order_params)
    # Remember the order ID to get the order status later
    order_id = response.id
    print(f"Submitted {side} order for {shares_per_trade} shares of {symbol} with the order-id: {order_id}")
    # Append the submitted orders to a CSV file
    order_data = response.model_dump()  # or response._raw for some SDKs
    order_data = convert_to_nytzone(order_data)
    order_data = pd.DataFrame([order_data])
    # Append to CSV (write header only if file does not exist)
    order_data.to_csv(submits_file, mode="a", header=not os.path.exists(submits_file), index=False)
    print(f"Order appended to {submits_file}")
except Exception as e:
    # Convert error to string and save to CSV
    error_msg = pd.DataFrame([{"timestamp: ": time_now, "symbol: ": symbol, "side: ": side, "error: ": str(e)}])
    error_msg.to_csv(error_file, mode="a", header=not os.path.exists(error_file), index=False)
    print(f"Trade order rejected: {e}")



# --------- Get the trade confirm --------

try:
    # After submitting the order and getting the response object
    # Check the order status after waiting for 1 second
    print("Waiting 1 second for the order to be processed...")
    time.sleep(1)
    order_status = trading_client.get_order_by_id(order_id)
    print(f"Order status: {order_status.status}")
    order_data = order_status.model_dump()  # or response._raw for some SDKs
    order_data = convert_to_nytzone(order_data)
    order_data = pd.DataFrame([order_data])
    # Append to CSV (write header only if file does not exist)
    order_data.to_csv(fills_file, mode="a", header=not os.path.exists(fills_file), index=False)
    print(f"Order appended to {fills_file}")
except Exception as e:
    # Convert error to string and save to CSV
    error_msg = pd.DataFrame([{"timestamp: ": time_now, "symbol: ": symbol, "side: ": side, "error: ": str(e)}])
    error_msg.to_csv(error_file, mode="a", header=not os.path.exists(error_file), index=False)
    print(f"Trade order not filled: {e}")
