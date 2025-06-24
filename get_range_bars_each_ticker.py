import alpaca_trade_api as tradeapi
import pandas as pd
from alpaca.data.timeframe import TimeFrame
import requests
import os

# Alpaca API credentials
API_KEY = "PKMIDDD0B792FZO6HF7E"
SECRET_KEY = "u89kQV6dRJyom4ONFgpWHOr7jho8fY3SrMTD6Fvs"
BASE_URL = "https://paper-api.alpaca.markets"

api = tradeapi.REST(API_KEY, SECRET_KEY, base_url=BASE_URL)

# Define timeframe
timeframe = TimeFrame.Month

# Define start and end dates
start_date = "2025-01-01T00:00:00Z"
end_date = "2025-06-01T00:00:00Z"


csv_filename = "active_tickers.csv"

# Load CSV file into a DataFrame
df = pd.read_csv(csv_filename)

# Display first few rows
print(df.head())
#exit()

# Pass one element at a time
for index, row in df.iterrows():
    for col in df.columns:
        element = str(row[col])  # Convert each element to a string
        print(element)  # Outputs elements one by one

    symbol = element
    #symbol = 'AAPL'  # Example ticker symbols, replace with actual tickers


    # Define timeframe
    timeframe = TimeFrame.Month

    # Define start and end dates (ISO8601 format)
    start_date = "2025-01-01T00:00:00Z"  # January 1, 2024
    end_date = "2025-06-01T00:00:00Z"    # June 1, 2024

    # Fetch historical bars with date range
    bars = api.get_bars(symbol, timeframe=timeframe, start=start_date, end=end_date).df
    bars["Ticker"] = symbol
    bars = pd.DataFrame(bars, columns=["datetime", "open", "high", "low", "close", "volume", "trades", "vwap", "Ticker"])
    bars.reset_index(inplace=True)
    print(bars) 

 #   exit()

    if not bars.empty:
        bars.to_csv("bars5mts.csv", mode="a", index=False, header=False)

        csv_filename = "bars5mts.csv"

        # Check if file exists; write headers only if it's the first iteration
        write_header = not os.path.exists(csv_filename)

        # Save DataFrame to CSV
        bars.to_csv(csv_filename, mode="a", index=False, header=write_header)


        print("Appended data to CSV")


    else:
       print("DataFrame is empty, nothing added")
  
