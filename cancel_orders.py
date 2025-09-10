### Cancel the open trade orders for a symbol, using the Alpaca SDK.
# https://alpaca.markets/sdks/python/trading.html

# Cancel the open trade orders by running the script in the terminal:
# python3 cancel_orders.py SPY


import pandas as pd
from datetime import date, datetime
from zoneinfo import ZoneInfo
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from dotenv import load_dotenv
import os
import sys


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Trade keys
TRADE_KEY = os.getenv("ALPACA_TRADE_KEY")
TRADE_SECRET = os.getenv("ALPACA_TRADE_SECRET")

# Create the SDK trading client
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)

# Get the symbol from the user
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()


# Create file name with today's NY date
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("data_dir_name")
# Create file name for the canceled trade orders
canceled_file = f"{dir_name}" + "canceled_" + f"{symbol}_{date_short}.csv"


# Get all open orders for the symbol
request_params = GetOrdersRequest(
                    status=QueryOrderStatus.OPEN,
                    symbols=[symbol],
                )
open_orders = trading_client.get_orders(filter=request_params)


# Cancel the open orders one at a time
if not open_orders:
    print(f"No open orders found for {symbol}.")
else:
    print(f"Found {len(open_orders)} open orders for {symbol}.")
    for order in open_orders:
        order_id = str(order.id)
        try:
            # Cancel the order
            trading_client.cancel_order_by_id(order_id=order_id)
            # Get the canceled order details
            order = trading_client.get_order_by_id(order_id=order_id)
            # Append the canceled order to CSV file (write header only if file does not exist)
            canceled_frame = pd.DataFrame([order.model_dump()])
            canceled_frame.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
            print(f"Cancelled order: {order_id} for {symbol}")
        except Exception as e:
            print(f"Error cancelling order {order.id} for {symbol}: {e}")
    print(f"Canceled orders saved to {canceled_file}")

