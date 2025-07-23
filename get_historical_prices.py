### Get historical TAQ stock tick prices using the Alpaca API.

import pandas as pd
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockQuotesRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.data.enums import DataFeed
from dotenv import load_dotenv
import os


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)

# Define the trading symbol
symbol = "SPY"
symbols = ["SPY", "AAPL", "GOOGL"]  # Example list of symbols
# Define the time range
# time_utc = datetime(2025, 6, 30, 15, 0, 0, tzinfo=timezone.utc)
# Get the current UTC time
time_utc = datetime.now(timezone.utc)
end_time = time_utc
start_time = end_time - timedelta(seconds=1)
# Get the current New_York time
time_now = time_utc.astimezone(ZoneInfo("America/New_York"))

# Create the request for historical quotes
quotes_request = StockQuotesRequest(
    symbol_or_symbols = symbols,
    start = start_time,
    end = end_time,
    feed = DataFeed.SIP
)

# Get the price quotes
price_quotes = data_client.get_stock_quotes(quotes_request)
# Get the trade prices
# price_quotes = data_client.get_stock_trades(quotes_request)


'''
# Example: Print the first 5 quotes for SPY
# price_quotes is a dict: {symbol: [Quote, Quote, ...]}
spy_quotes = price_quotes.data[symbol]
print(f"Number of quotes for {symbol}: {len(price_quotes)}")
for q in spy_quotes[:5]:  # Print first 5 quotes
    print(f"Bid: {q.bid_price}, Ask: {q.ask_price}, Time: {q.timestamp}")
'''

# Loop and save each symbol's price quotes to a separate CSV file
date_short = time_now.strftime("%Y%m%d")
if len(price_quotes.data) > 0:
    for symbol in symbols:
        # Check if prices were returned for the symbol
        if price_quotes[symbol]:
            price_df = pd.DataFrame([price.model_dump() for price in price_quotes.data[symbol]])
            # Save data frame to CSV
            filename = f"price_quotes_{symbol}_{date_short}.csv"
            price_df.to_csv(filename, index=False)
            print(f"Saved historical price quotes for {symbol} and saved to {filename}")
        else:
            print(f"No prices were returned for {symbol} in the requested time range.")
    print("Finished getting historical price quotes.")
else:
    print(f"No prices were returned in the requested time range.")
