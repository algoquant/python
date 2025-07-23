### Submit trade orders using the Alpaca SDK.
# https://docs.alpaca.markets/docs/working-with-orders
# https://wire.insiderfinance.io/alpaca-algorithmic-trading-api-in-python-part-1-getting-started-with-paper-trading-efbff8992836
# https://alpaca.markets/sdks/python/trading.html

import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockQuotesRequest, StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.enums import DataFeed
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from dotenv import load_dotenv
import os

# Load API keys from .env file
load_dotenv(".env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

# Create the SDK trading client
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)

# Create the strategy name
strategy_name = "Strat001"
# Define the trading parameters
symbol = "SPY"

# Create a file name with today's NY date
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("data_dir_name")
fills_file = f"{dir_name}" + "fills2_" + f"{strategy_name}_{symbol}_{date_short}.csv"


# buy
order_id = "84e04bc3-d401-44c6-85a4-f0b0ea7d0e47"
# sell
order_id = "377ae6b3-eb08-42d6-8043-e3156426664a"

order_status = trading_client.get_order_by_id(order_id)
print(f"Order status: {order_status.status}")

fills_data = order_status.model_dump()  # or response._raw for some SDKs
fills_data = pd.DataFrame([fills_data])

# Append to CSV (write header only if file does not exist)
fills_data.to_csv(fills_file, mode="a", header=not os.path.exists(fills_file), index=False)

