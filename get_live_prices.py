### Get live stock prices using the Alpaca API.

import requests
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")

# Get API keys from environment
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")


### Get the latest bid/ask prices
headers = {
    "APCA-API-KEY-ID": DATA_KEY,
    "APCA-API-SECRET-KEY": DATA_SECRET
}
symbol = "SPY"
params = {"symbols": symbol}
response = requests.get(
    "https://data.alpaca.markets/v2/stocks/quotes/latest", 
    headers = headers, 
    params = params)
json_data = response.json()
ask = json_data["quotes"][symbol]["ap"]
bid = json_data["quotes"][symbol]["bp"]
print(f"Ask: {ask}, Bid: {bid}")


### Get the latest OHLCV bar of prices
response = requests.get(
    "https://data.alpaca.markets/v2/stocks/bars/latest",
    headers=headers,
    params=params
)
bar_data = response.json()
bar = bar_data["bars"][symbol]
print(f"Latest bar for {symbol}: {bar}")
# Example: print open, high, low, close, volume
print(f"Open: {bar['o']}, High: {bar['h']}, Low: {bar['l']}, Close: {bar['c']}, Volume: {bar['v']}")

