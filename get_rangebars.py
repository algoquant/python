import alpaca_trade_api as tradeapi
import pandas as pd
from datetime import datetime
from alpaca.data.timeframe import TimeFrame
import os
from dotenv import load_dotenv

# Alpaca API credentials
load_dotenv()

API_KEY = os.getenv("ALPACA_API_KEY", "")
SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

if not API_KEY or not SECRET_KEY:
	raise ValueError("Missing ALPACA_API_KEY or ALPACA_SECRET_KEY in environment")

api = tradeapi.REST(API_KEY, SECRET_KEY, base_url=BASE_URL)

# Define timeframe
timeframe = TimeFrame.Month

# Define start and end dates (ISO8601 format)
start_date = os.getenv("RANGEBARS_START_DATE", "2024-01-01T00:00:00Z")
end_date = os.getenv("RANGEBARS_END_DATE", "2024-06-01T00:00:00Z")
rangebars_symbol = os.getenv("RANGEBARS_SYMBOL", "AAPL")

# Fetch historical bars with date range
bars = api.get_bars(symbol=rangebars_symbol, timeframe=timeframe, start=start_date, end=end_date).df

# Convert to DataFrame and display
bars_df = pd.DataFrame(bars)
print(bars_df)

# Save DataFrame to a CSV file
csv_filename = os.getenv("RANGEBARS_OUTPUT_FILE", "AAPL_bars.csv")
bars_df.to_csv(csv_filename, index=False)

print(f"CSV file saved: {csv_filename}")