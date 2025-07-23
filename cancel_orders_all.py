### Cancel all the open trade orders, using the Alpaca SDK.
# https://alpaca.markets/sdks/python/trading.html

import pandas as pd
from datetime import date, datetime
from zoneinfo import ZoneInfo
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
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


# Get all the open orders
orders = trading_client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))

if len(orders) > 0:
    # Cancel all open orders
    canceled_orders = trading_client.cancel_orders()
    # Convert the list to a data frame
    canceled_orders = pd.DataFrame([order.model_dump() for order in canceled_orders])
    # Save canceled orders to CSV file
    time_now = datetime.now(ZoneInfo("America/New_York"))
    date_short = time_now.strftime("%Y%m%d")
    dir_name = os.getenv("data_dir_name")
    canceled_file = f"{dir_name}canceled_orders_" + date_short + ".csv"
    # Append to CSV (write header only if file does not exist)
    canceled_orders.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
    print("Finished cancelling orders and saved to canceled_orders.csv")
else:
    print("No open orders found.")

