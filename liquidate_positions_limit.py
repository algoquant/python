### Liquidate all the open positions by submitting limit orders, using the Alpaca SDK.
# If the symbols are provided, then liquidate only those symbols' positions.
# If the symbols are not provided, then liquidate the available positions for all the symbols.
# Liquidate only the amount of shares available for each position.
# https://alpaca.markets/sdks/python/trading.html
#
# In the terminal, you can provide the symbols as command line arguments.
# python3 liquidate_positions_limit.py symbols, price_adjustment
# 
# The price_adjustment is the adjustment to the limit price, compared to the ask or bid price.
# For example, if the ask price is $100, and the price_adjustment is $0.5,
# the limit price will be set to $99.5 for a buy order, or $100.5 for a sell order.
# 
# For example, to liquidate all the positions for just SPY:
# python3 liquidate_positions_limit.py SPY 0.5
#
# To liquidate positions for multiple symbols:
# python3 liquidate_positions_limit.py AAPL MSFT TSLA 0.5
#
# To liquidate all the positions for all the symbols:
# python3 liquidate_positions_limit.py 0.5

import os
import sys
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


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
ALPACA_TRADE_KEY = os.getenv("ALPACA_TRADE_KEY")
ALPACA_TRADE_SECRET = os.getenv("ALPACA_TRADE_SECRET")

# Create the SDK data client for live and historical stock data
data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)
# Create the SDK trading client
trading_client = TradingClient(ALPACA_TRADE_KEY, ALPACA_TRADE_SECRET)


# --------- Get the trading parameters from the command line arguments --------

# Get the symbol, type, side, shares_per_trade, and price_adjustment from the command line arguments
symbols = []
lenarg = len(sys.argv)
if lenarg > 1:
    symbols = [arg.strip().upper() for arg in sys.argv[1:lenarg-1]]
    price_adjustment = float(sys.argv[lenarg-1])
else:
    symbol = input("Enter symbol: ").strip().upper()
    price_adjustment_input = input("Enter the limit price adjustment (default 0.5): ").strip()
    price_adjustment = float(price_adjustment_input) if price_adjustment_input else 0.5

print(f"Trading parameters: symbols={symbols}, price_adjustment={price_adjustment}\n")


# --------- Get all the open positions and their symbols --------

# Get all the open positions, then filter for the specified symbols
all_positions = trading_client.get_all_positions()
positions = []
if symbols:
    positions = [pos for pos in all_positions if pos.symbol in symbols]
else:
    positions = all_positions


# --------- Liquidate all the open positions in a loop --------

# Check if the position quantity is greater than zero
if positions:

    # Get the prices for all the symbols in the portfolio
    symbols = [pos.symbol for pos in positions]
    # Use SIP for comprehensive data, or IEX for free data.
    data_feed = DataFeed.SIP
    request_params = StockLatestQuoteRequest(symbol_or_symbols=symbols, feed=data_feed)
    # Get the latest quotes - as a dictionary
    latest_quotes = data_client.get_stock_latest_quote(request_params)
    for symbol in latest_quotes.keys():
        print(f"Latest quotes for {symbol}: Ask = {latest_quotes[symbol].ask_price}, Bid = {latest_quotes[symbol].bid_price}")

    # Loop through the positions and calculate the limit order parameters
    for position in positions:
        symbol = position.symbol
        # Get the number of available shares to trade from the broker
        shares_available = float(position.qty_available)
        qty = int(position.qty)
        if (qty != shares_available):
            print(f"Position {symbol} has only {shares_available} shares available, but {qty} shares owned.")
            qty = shares_available
        # Set the limit order parameters based on the position side
        if (qty > 0):
            bid_price = latest_quotes[symbol].bid_price
            side = OrderSide.SELL
            limit_price = round(bid_price + price_adjustment, 2)  # Adjust the sell price slightly above the ask price
        else:
            side = OrderSide.BUY
            qty = -qty
            ask_price = latest_quotes[symbol].ask_price
            limit_price = round(ask_price - price_adjustment, 2)  # Adjust the buy price slightly below the ask price

        # Create the limit order request
        request = LimitOrderRequest(
            symbol = symbol,
            qty = qty,
            side = side,
            type = "limit",
            limit_price = limit_price,
            extended_hours = True,
            time_in_force = TimeInForce.DAY
        ) # end request

        # Submit a limit order to liquidate the position
        print(f"Placing a limit {side} order for {qty} shares of {symbol} at {limit_price}")
        response = trading_client.submit_order(order_data=request)
        # print(f"Symbol: {position.symbol}, Qty: {position.qty}, Side: {position.side}, Unreal_PnL: {position.unrealized_pl}")

else:
    print("No positions to liquidate.")

