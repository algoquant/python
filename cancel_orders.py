### Cancel trade orders using Alpaca API.

import pandas as pd
from datetime import date, datetime
import pandas as pd
import alpaca_trade_api as tradeapi
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)

BASE_URL = "https://paper-api.alpaca.markets"

# data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)
trade_api = tradeapi.REST(TRADE_KEY, TRADE_SECRET, BASE_URL, api_version="v2")


# Get all open orders
orders = trading_client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.OPEN))
# Get order_id of first open order
# order_id = "31077c7b-67f8-4b25-a38b-0889023b2cb1"
# order_id = orders[0].id
# print("order_id: " + order_id)
# Cancel the order using the order_id
# trade_api.cancel_order(order_id)

# Cancel all open orders in a loop
if (len(orders) > 0):
    # Create empty data frame of cancelled orders
    cancelled_orders = pd.DataFrame(columns=["date", "timestamp", "order_id"])
    # Cancel all open orders in a loop
    for order in orders:
        order_id = order.id
        trade_api.cancel_order(order_id)
        date_now = datetime.now()
        time_stamp = date_now.timestamp()
        cancelled_orders.loc[len(cancelled_orders)] = [date_now, time_stamp, order_id]
        print(f"Cancelled order {order_id} at {date_now}")
    # Save cancelled orders to CSV file
    # current_time = time.localtime()
    # file_name = "/Users/jerzy/Develop/Python/cancelled_orders_" + time.strftime("%Y%m%d", current_time) + ".csv"
    current_time = datetime.now()
    file_name = "/Users/jerzy/Develop/MachineTrader/Internship_Summer_2025/data/cancelled_orders_" + current_time.strftime("%Y%m%d") + ".csv"
    cancelled_orders.to_csv(file_name, index=False)
    print("Finished cancelling orders and saved to cancelled_orders.csv")
else:
    print("No open orders found. Exiting script.")


### Alternative way to cancel an order using requests the Alpaca API
### Example of how to cancel an order using requests the Alpaca API
# import requests
# # Get account details
# account = trade_api.get_account()
# # print("account: " + account)
# # Extract the account ID
# account_id = account.id
# # print("account_id: " + account_id)

# url = "https://paper-api.alpaca.markets/v2/orders/" + order_id
# # url = "https://paper-api.alpaca.markets/v2/orders/" + account_id + "/orders/" + order_id
# print("url: " + url)
# response = requests.delete(url)

# # # headers = {"accept": "application/json"}
# # # response = requests.delete(url, headers=headers)

# print(response)
# # print(response.status_code)
# # print(response.text)
