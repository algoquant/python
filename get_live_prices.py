### Get live stock prices using the Alpaca API.
# https://alpaca.markets/sdks/python/api_reference/data/stock/requests.html
# https://alpaca.markets/sdks/python/api_reference/data/stock.html
# https://alpaca.markets/sdks/python/trading.html

import pandas as pd
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockLatestTradeRequest
from alpaca.data.enums import DataFeed
from dotenv import load_dotenv
import os


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
# Get API keys from environment
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Create the SDK data client for live and historical stock data
data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)

# Define the trading symbol
symbol = "SPY"
symbols = ["SPY", "AAPL", "GOOGL"]  # Example list of symbols

# Create the request parameters for live stock prices for all the symbols in the portfolio

# Price type - Use "quote" for latest quotes, or "trade" for latest trades
type = "quote"
# type = "trade"
# Use SIP for comprehensive data, or IEX for free data.
data_feed = DataFeed.SIP

# For options:
# quotes_request = OptionLatestQuotesRequest(symbols=["AAPL240719C00150000"], feed=DataFeed.OPRA)  # Use OPRA for options
# latest_prices = client.get_latest_option_quotes(quotes_request)


if type == "quote":
    # For quote prices:
    print(f"Getting latest quote prices")
    request_params = StockLatestQuoteRequest(symbol_or_symbols=symbols, feed=data_feed)
    latest_prices = data_client.get_stock_latest_quote(request_params)
    # Loop and print each symbol's prices
    if len(latest_prices) > 0:
        for symbol in symbols:
            # Check if prices were returned for the symbol
            if latest_prices[symbol]:
                symbol_prices = latest_prices[symbol]
                # Get the latest bid/ask prices
                ask_price = symbol_prices.ask_price
                bid_price = symbol_prices.bid_price
                print(f"Latest prices for {symbol}: Ask = {ask_price}, Bid = {bid_price}")
            else:
                print(f"No prices were returned for {symbol}")
        print("Finished getting live prices")
    else:
        print(f"No prices were returned")
elif type == "trade":
    print(f"Getting latest trade prices")
    request_params = StockLatestTradeRequest(symbol_or_symbols=symbol, feed=data_feed)
    latest_prices = data_client.get_stock_latest_trade(request_params)
    # Loop and print each symbol's prices
    if len(latest_prices) > 0:
        price_keys = latest_prices.keys()
        for symbol in symbols:
            # Check if prices were returned for the symbol
            if symbol in price_keys:
                symbol_prices = latest_prices[symbol]
                # Get the latest trade price and size
                trade_price = symbol_prices.price
                trade_size = symbol_prices.size
                print(f"Latest trade price for {symbol}: Price = {trade_price}, Size = {trade_size}")
            else:
                print(f"No prices were returned for {symbol}")
        print("Finished getting live prices")
    else:
        print(f"No prices were returned")


''' 

### Alternative method of downloading live prices using requests and the Alpaca endpoint.

import requests
# Define the request parameters for live stock prices
headers = {
    "APCA-API-KEY-ID": DATA_KEY,
    "APCA-API-SECRET-KEY": DATA_SECRET
}
params = {"symbols": symbol, "feed": "sip"}
# Submit the request to get the latest bid/ask prices
response = requests.get(
    "https://data.alpaca.markets/v2/stocks/quotes/latest", 
    headers = headers, 
    params = params)
json_data = response.json()
ask_price = json_data["quotes"][symbol]["ap"]
bid_price = json_data["quotes"][symbol]["bp"]
print(f"Endpoint latest quotes for {symbol}: Ask = {ask_price}, Bid = {bid_price}")


### Get the latest OHLCV bar of prices
response = requests.get(
    "https://data.alpaca.markets/v2/stocks/bars/latest",
    headers=headers,
    params=params
)
bar_data = response.json()
bar_data = bar_data["bars"][symbol]
print(f"Latest price bar for {symbol}: {bar_data}")
# Example: print open, high, low, close, volume
print(f"Open: {bar_data['o']}, High: {bar_data['h']}, Low: {bar_data['l']}, Close: {bar_data['c']}, Volume: {bar_data['v']}, VWAP: {bar_data['vw']}")

'''