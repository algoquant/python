### Submit trade orders using Alpaca API.

import requests
import alpaca_trade_api as tradeapi
from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)

# data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)
BASE_URL = "https://paper-api.alpaca.markets"
trade_api = tradeapi.REST(TRADE_KEY, TRADE_SECRET, BASE_URL, api_version = "v2")


### Submit market orders

# Define the trading symbol
symbol = "SPY"
side = "buy"
# side = "sell"
print(f"Placing a market {side} order")
order = trade_api.submit_order(
    symbol = symbol,
    qty = 1,
    side = side,
    type = "market",
    time_in_force = "day"
) # end submit_order

# Remember the order ID for reference
# order_id = "c4f6dd53-dedb-4ea4-9edd-23406da29608"
order_id = order.id
print(f"Market {side} order placed, with the order-id: {order.id}")
# Get order status using the order ID
order_status = trade_api.get_order(order_id)
print(f"Order status: {order_status.status}")



### Submit limit orders

# Get the latest bid/ask prices
headers = {
    "APCA-API-KEY-ID": DATA_KEY,
    "APCA-API-SECRET-KEY": DATA_SECRET
}
params = {"symbols": symbol}

response = requests.get(
    "https://data.alpaca.markets/v2/stocks/quotes/latest", 
    headers = headers, 
    params = params)
json_data = response.json()
ask = json_data["quotes"][symbol]["ap"]
bid = json_data["quotes"][symbol]["bp"]
print(f"Ask: {ask}, Bid: {bid}")  # Log ask and bid prices

# Submit a limit order to buy SPY at the current ask price minus a small adjustment
side = "buy"
# Submit a limit order to sell SPY at the current ask price minus a small adjustment
# side = "sell"
limit_price = round(ask - 0.1, 2)  # Adjust the buy price slightly below the ask price
# limit_price = round(bid + 0.1, 2)  # Adjust the sell price slightly below the ask price
print(f"Placing a limit {side} order at {limit_price}")
order = trade_api.submit_order(
    symbol = symbol,
    qty = 1,
    side = side,
    type = "limit",
    limit_price = limit_price,
    extended_hours = True,
    time_in_force = "day"
) # end submit_order
print(f"Limit {side} order placed at the price of {limit_price}, with the order-id: {order.id}")


# Remember the order ID for reference
# order_id = "c4f6dd53-dedb-4ea4-9edd-23406da29608"
order_id = order.id

# Get order status using the order ID
order_status = trade_api.get_order(order_id)
print(f"Order status: {order_status.status}")


# while True:
#     try:
#         schedule.run_pending()
#         time.sleep(1)  # Prevent CPU overload
#     except Exception as e:
#         print(f"Loop error: {e}")  # Log loop errors




