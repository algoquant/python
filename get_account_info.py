### Download account information from Alpaca using the TradingClient.
# https://wire.insiderfinance.io/alpaca-algorithmic-trading-api-in-python-part-1-getting-started-with-paper-trading-efbff8992836

import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
import os


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Trade keys
TRADE_KEY = os.getenv("ALPACA_TRADE_KEY")
TRADE_SECRET = os.getenv("ALPACA_TRADE_SECRET")

# Create the SDK trading client
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)


### Get account information
account = trading_client.get_account()

# Print account info
print("Account info:")
print("Account ID:", account.id)
print("Status:", account.status)
print("Equity:", account.equity)
print("Buying Power:", account.buying_power)
print("Cash:", account.cash)
print("Portfolio Value:", account.portfolio_value)

# Convert account object to data frame
account_frame = pd.DataFrame(account)
# account_frame.shape

# Save account info to CSV file
time_now = datetime.now(ZoneInfo("America/New_York"))
date_short = time_now.strftime("%Y%m%d")
filename = "account_info_" + date_short + ".csv"
account_frame.to_csv(filename, index=False)


### Get account configurations
config = trading_client.get_account_configurations()

# Print configuration info
print("Account configuration:")
print("Fractional trading:", config.fractional_trading)
print("Margin multiplier:", config.max_margin_multiplier)
print("No shorting:", config.no_shorting)

# Convert config object to data frame
config_frame = pd.DataFrame(config)
# config_frame.shape

# Save config info to CSV file
filename = "config_info_" + date_short + ".csv"
config_frame.to_csv(filename, index=False)


