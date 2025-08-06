### Liquidate all the open positions by submitting limit orders, using the Alpaca SDK.
# https://alpaca.markets/sdks/python/trading.html

import pandas as pd
from datetime import date, datetime
import requests
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockQuotesRequest, StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.enums import DataFeed
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from dotenv import load_dotenv
import os


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

# Create the SDK data client for live and historical stock data
data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)

# Create the SDK trading client
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)

# Get all open positions
portfolio = trading_client.get_all_positions()
# print(type(portfolio))  # Check if it's a list or object
# print(portfolio)  # Print the portfolio to see its contents

# Get all the symbols in the portfolio
# portfolio
symbol = "SPY"
symbols = ["SPY", "AAPL", "GOOGL"]  # Example list of symbols

# Get the prices for all the symbols in the portfolio
# Use SIP for comprehensive data, or IEX for free data.
request_params = StockLatestQuoteRequest(symbol_or_symbols=symbols, feed=DataFeed.SIP)
# Get the latest quotes - as a dictionary
latest_quotes = data_client.get_stock_latest_quote(request_params)
# Get the keys
latest_quotes.keys()
# Get the SPY quote
spy_quotes = latest_quotes["SPY"]
# Print the quotes
# print(f"Latest quotes for {symbol}: {spy_quotes}")
print(f"Latest quotes for {symbol}: Ask = {spy_quotes.ask_price}, Bid = {spy_quotes.bid_price}")


# Headers for Alpaca API price requests
headers = {
    "APCA-API-KEY-ID": DATA_KEY,
    "APCA-API-SECRET-KEY": DATA_SECRET
}

# Liquidate all the open positions in a loop
for position in portfolio:
    symbol = position.symbol
    # qty = -5
    qty = int(position.qty)
    # Get the latest bid/ask prices for symbol
    response = requests.get(
        "https://data.alpaca.markets/v2/stocks/quotes/latest", 
        headers = headers, 
        params = {"symbols": symbol})
    json_data = response.json()
    ask = json_data["quotes"][symbol]["ap"]
    bid = json_data["quotes"][symbol]["bp"]
    delta = 0.1 # Adjustment to the limit price to ensure it is slightly above the ask or below the bid
    # Set the limit order parameters based on the position side
    if (qty > 0):
        side = OrderSide.SELL
        limit_price = round(bid + delta, 2)  # Adjust the sell price slightly above the ask price
    else:
        side = OrderSide.BUY
        qty = -qty
        limit_price = round(ask - delta, 2)  # Adjust the buy price slightly below the ask price
    # Submit a limit order to liquidate the position
    print(f"Placing a limit {side} order for {qty} shares of {symbol} at {limit_price}")
    request = LimitOrderRequest(
        symbol = symbol,
        qty = qty,
        side = side,
        type = "limit",
        limit_price = limit_price,
        extended_hours = True,
        time_in_force = TimeInForce.DAY
    ) # end request
    # Submit the limit order
    print(f"Placing a limit {side} order at {limit_price} for {qty} shares of {symbol}")
    response = trading_client.submit_order(order_data=request)
    # print(f"Symbol: {position.symbol}, Qty: {position.qty}, Side: {position.side}, Unreal_PnL: {position.unrealized_pl}")

# Finished liquidating the positions
