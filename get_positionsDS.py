import pandas as pd
import schedule
import time
import pytz
from datetime import datetime, timezone, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import alpaca_trade_api as tradeapi
import requests

# Initialize clients
API_KEY = "PKMIDDD0B792FZO6HF7E"
API_SECRET = "u89kQV6dRJyom4ONFgpWHOr7jho8fY3SrMTD6Fvs"

BASE_URL = "https://paper-api.alpaca.markets"

client = StockHistoricalDataClient(API_KEY, API_SECRET)
api = tradeapi.REST(API_KEY, API_SECRET, BASE_URL, api_version="v2")

from alpaca.trading.client import TradingClient
trading_client = TradingClient(API_KEY, API_SECRET)

        
# Get all open positions
portfolio = trading_client.get_all_positions()
print(type(portfolio))  # Check if it's a list or object
print(portfolio)  # Print the portfolio to see its contents
for position in portfolio:
    print(f"Symbol: {position.symbol}, Qty: {position.qty}, Side: {position.side}")
#     # Define the request parameters
# Extract 'qty' as an integer from the first position
#qty = int(portfolio[0]['qty'])

#print(qty)  # Output: -2

# Access the first position's quantity
qty = int(portfolio[0].qty)  # ✅ Use dot notation instead of brackets
print(qty)  # Output: -2    

if ( qty < 0  ):
    print("You have a short position in SPY.")
else:
    print("You do not have a short position in SPY.")
    