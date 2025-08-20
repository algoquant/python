### Get the latest bar stock prices using the Alpaca API.
# https://alpaca.markets/sdks/python/api_reference/data/stock/requests.html
# https://alpaca.markets/sdks/python/api_reference/data/stock.html

# There are at least three different ways to get the latest OHLCV bar of prices for a stock using the Alpaca API:
# Using get_stock_latest_bar(), using the endpoint /v2/stocks/bars/latest, and using get_stock_bars().
# get_stock_latest_bar() and the endpoint produce the same prices.
# But both are different from the bar prices using get_stock_bars() with a time range.
# The close price using get_stock_latest_bar() is different from the latest price, because the latest bar price is formed only once a minute, and doesn't change in between.

# And there two different StockHistoricalDataClient classes in the Alpaca SDK.
# On from alpaca.data and another one from alpaca.data.historical.
# Both produce the same results, but the one from alpaca.data is the newer version?


import os
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import requests
from alpaca.data import StockHistoricalDataClient
# from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest, StockLatestBarRequest
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Data client for historical stock data
data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)

# Define the trading symbol
symbol = "SPY"


### Get the latest bid/ask prices using the Alpaca SDK.

request_params = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.SIP)
latest_quotes = data_client.get_stock_latest_quote(request_params)
price_quotes = latest_quotes[symbol]
ask_price = price_quotes.ask_price
bid_price = price_quotes.bid_price
print(f"Latest quotes for {symbol}: Ask = {price_quotes.ask_price}, Bid = {price_quotes.bid_price}")


### Get the latest OHLCV bar of prices using the Alpaca SDK get_stock_latest_bar.

request_params = StockLatestBarRequest(
    symbol_or_symbols=symbol,
    feed=DataFeed.SIP, # Or DataFeed.SIP, DataFeed.OTC
)

bar_data = data_client.get_stock_latest_bar(request_params)
bar_data = bar_data[symbol]
bar_data = bar_data.model_dump()
# bar_data["close"]

print(f"Prices: {bar_data['open']}, High: {bar_data['high']}, Low: {bar_data['low']}, Close: {bar_data['close']}, Volume: {bar_data['volume']}, VWAP: {bar_data['vwap']}")


### Get the latest OHLCV bar of prices using the endpoint requests.

# Define the request parameters for live stock prices
headers = {
    "APCA-API-KEY-ID": DATA_KEY,
    "APCA-API-SECRET-KEY": DATA_SECRET
}
params = {"symbols": symbol, "feed": "sip"}
response = requests.get(
    "https://data.alpaca.markets/v2/stocks/bars/latest",
    headers=headers,
    params=params
)
bar_data = response.json()
bar_data = bar_data["bars"][symbol]
# print(f"Latest price bar for {symbol}: {bar}")
# Example: print open, high, low, close, volume
print(f"Endpoint prices: {bar_data['o']}, High: {bar_data['h']}, Low: {bar_data['l']}, Close: {bar_data['c']}, Volume: {bar_data['v']}, VWAP: {bar_data['vw']}")



### Get the latest OHLCV bar of prices using the Alpaca SDK get_stock_bars with time range.

# Get the current UTC time
time_utc = datetime.now(timezone.utc)
# Get the current New_York time
time_now = time_utc.astimezone(ZoneInfo("America/New_York"))
# time_utc = datetime.now(timezone.utc)
start_time = time_utc - timedelta(minutes=5)
start_time = start_time.strftime("%Y-%m-%d %H:%M:%S")
end_time = time_utc.strftime("%Y-%m-%d %H:%M:%S")
# start_time = end_time
print(f"Getting bars from {start_time} to {end_time}")

# Define the request parameters
request_params = StockBarsRequest(
    symbol_or_symbols=symbol,
    timeframe=TimeFrame.Minute,
    start=start_time,
    end=end_time,
    limit=1, # Get only the latest bar
    feed="sip",  # Use "iex" for IEX data - if you don't have access to SIP data
)

# Parse the bars
bar_data = data_client.get_stock_bars(request_params)
bar_data = bar_data.data[symbol][0]
bar_data = bar_data.model_dump()
# bar_data["close"]

print(f"SDK price: {bar_data['open']}, High: {bar_data['high']}, Low: {bar_data['low']}, Close: {bar_data['close']}, Volume: {bar_data['volume']}, VWAP: {bar_data['vwap']}")




