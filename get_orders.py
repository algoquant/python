# Get the open trade orders, using the Alpaca SDK.
# https://alpaca.markets/sdks/python/trading.html

import pandas as pd
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus
from dotenv import load_dotenv
import os


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

# Create the SDK trading client
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)

# Define the trading parameters
symbol = "SPY"
# Get all the open orders for the symbol
request_params = GetOrdersRequest(
                    status=QueryOrderStatus.OPEN,
                    symbols=[symbol],
                 )
orders = trading_client.get_orders(filter=request_params)
# Get all closed orders
# orders = trading_client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.CLOSED))
# Get all buy orders for SPY and AAPL
# request_params = GetOrdersRequest(
#                     status=QueryOrderStatus.ALL,
#                     side=OrderSide.BUY,
#                     symbols=["SPY", "AAPL"],
#                  )
# orders = trading_client.get_orders(filter=request_params)

if len(orders) > 0:
    # Print the IDs and the client IDs of the orders
    for order in orders:
        print("Order ID: " + str(order.id))
        print("Client order ID: " + order.client_order_id)
        print("Client order ID: " + order.client_order_id)
        print("Client order ID: " + order.submitted_at.strftime("%Y-%m-%d %H:%M:%S"))
        print("Client order ID: " + order.type.name)
        print("Client order ID: " + order.side.name)
else:
    print("No open orders found.")


# Convert orders to data frame
orders_frame = pd.DataFrame([order.model_dump() for order in orders])
orders_frame.shape

# Save orders data frame to CSV file
time_now = datetime.now(ZoneInfo("America/New_York"))
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("data_dir_name")
orders_file = f"{dir_name}open_orders_" + date_short + ".csv"
orders_frame.to_csv(orders_file, index=False)
print("Finished getting orders and saved to orders.csv")



''' 

##########
# Alternative way to fetch orders using requests

import requests

headers = {
    "APCA-API-KEY-ID": TRADE_KEY,
    "APCA-API-SECRET-KEY": TRADE_SECRET
}

BASE_URL = "https://paper-api.alpaca.markets"  # Use "https://api.alpaca.markets" for live trading

# Fetch orders
response = requests.get(f"{BASE_URL}/v2/orders?status=all", headers=headers)
print(f"Fetching orders from {BASE_URL}/v2/orders")

if response.status_code == 200:
    orders = response.json()
    
    # Convert to DataFrame
    orders_frame = pd.DataFrame(orders)

    # Display the first few rows
    # print(orders_frame)
    print(orders_frame.head())

    # Optionally save to CSV
    orders_frame.to_csv("alpaca_orders.csv", index=False)
else:
    print(f"Error: {response.status_code}, {response.text}")

# Save DataFrame to CSV
orders_frame.to_csv("paper3_orders.csv", index=False)

''' 

