### Get historical OHLCV stock prices using the Alpaca API.

import pandas as pd
from datetime import datetime, timezone, timedelta
import pytz
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)


### Get historical OHLCV bars of prices

# Get current NY time
ny_timezone = pytz.timezone("America/New_York")
current_time = datetime.now(ny_timezone)
# Print current date and time
print("Date and time: ", current_time.strftime("%Y-%m-%d %H:%M:%S"))

# Run only between allowed hours (4 AM - 8 PM EST)
# if current_time.hour < 4 or current_time.hour >= 20:
#     print("Current time is outside of trading hours. Exiting script.")
#     exit()
                                    
# Calculate UTC start time (10 minutes ago)
# utc_now = datetime(2025, 6, 20, 15, 0, 0, tzinfo=timezone.utc)
utc_now = datetime.now(timezone.utc)
start_time = utc_now - timedelta(minutes=10)
#start_time = (datetime.utcnow() - timedelta(minutes=20)).isoformat()
start = start_time.strftime("%Y-%m-%d %H:%M:%S")
# print("Start time: ", start)
end = utc_now.strftime("%Y-%m-%d %H:%M:%S")
# print("End time:", end)

# Define the trading symbol
symbol = "SPY"
request_params = StockBarsRequest(
    symbol_or_symbols=[symbol],
    timeframe=TimeFrame.Minute,
    start=start,
    end=end,
    limit=100
) # end StockBarsRequest

bars = data_client.get_stock_bars(request_params)
# print(f"Fetched {len(bars['SPY'])} bars for SPY from {start} to {end}")
# print(bars)
price_bars = pd.DataFrame([bar.model_dump() for bar in bars[symbol]])

# Save data frame to CSV
current_time = datetime.now()
file_name = "/Users/jerzy/Develop/MachineTrader/Internship_Summer_2025/data/price_bars_" + current_time.strftime("%Y%m%d") + ".csv"
price_bars.to_csv(file_name, index=False)
print("Finished getting historical OHLCV stock prices and saved to price_bars.csv")
