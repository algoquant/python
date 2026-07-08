### Get the OHLC bar prices using the Alpaca API.
# https://alpaca.markets/sdks/python/api_reference/data/stock/requests.html
# https://alpaca.markets/sdks/python/api_reference/data/stock.html

# There are at least three different ways to get the latest OHLCV bar of prices for a stock using the Alpaca API:
# Using get_stock_latest_bar(), using the endpoint /v2/stocks/bars/latest, and using get_stock_bars().
# get_stock_latest_bar() and the endpoint produce the same prices.
# But both are different from the bar prices using get_stock_bars() with a time range.
# The close price using get_stock_latest_bar() is different from the latest price, because the latest bar price is formed only once a minute, and doesn't change in between.

# And there two different StockHistoricalDataClient classes in the Alpaca SDK.
# On from alpaca.data and another one from alpaca.data.historical.
# Both produce the same results, but the one from alpaca.data is the newer version?


from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import requests
from alpaca.data import StockHistoricalDataClient
# from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest, StockLatestBarRequest
from alpaca.data.enums import DataFeed
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv
import os
import pandas as pd


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/home/techyogi/dsavage/env")
#load_dotenv("/Users/danielsavage/desktop/Python_scripts/env")
# Get API keys from environment
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Data client for historical stock data
data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)


# --------- Get minute bars for a specific symbol --------

# Define the symbol
symbol = "SPY"
print(f"\nGetting minute bars for {symbol}...")

# Get historical 1-minute bars for a specific date range
# Note: Adjust the dates as needed
start_date = "2024-01-01"
end_date = "2024-12-31"  # Consider shorter periods for minute data to avoid large datasets

minute_bars_request = StockBarsRequest(
    symbol_or_symbols=symbol,
    timeframe=TimeFrame.Minute,
    start=start_date,
    end=end_date,
    feed=DataFeed.SIP
)

all_results = []

try:
    minute_bars = data_client.get_stock_bars(minute_bars_request)

    if symbol in minute_bars.data:
        for bar in minute_bars.data[symbol]:
            bar_data = bar.model_dump()
            bar_data['symbol'] = symbol
            all_results.append(bar_data)
        print(f"Collected {len(all_results)} minute bars")
    else:
        print(f"No data found for {symbol} in the specified date range")

except Exception as e:
    print(f"Error processing {symbol}: {str(e)}")

# Process results
if all_results:
    # Create DataFrame from all results
    results_df = pd.DataFrame(all_results)
    
    # Add calculated columns
    results_df['change'] = results_df['close'] - results_df['open']
    results_df['pctchange'] = results_df['change'] / results_df['open']
    results_df['highlowchange'] = results_df['high'] - results_df['low']
    results_df['pcthighlowchange'] = results_df['highlowchange'] / results_df['open']
    
    # Reorder columns
    cols = ['symbol', 'timestamp', 'open', 'high', 'low', 'close', 
            'change', 'pctchange', 'highlowchange', 'pcthighlowchange',
            'volume', 'vwap']
    results_df = results_df[cols]
    
    # Save to CSV
    output_file = 'spy_minute_bars.csv'
    results_df.to_csv(output_file, index=False)
    print(f"\nSaved {len(results_df)} records to {output_file}")
    
    # Display first few rows
    print("\nFirst few rows of data:")
    print(results_df.head())
else:
    print("No data was collected")




