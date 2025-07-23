import alpaca_trade_api as tradeapi
import pandas as pd
from datetime import datetime
from alpaca.data.timeframe import TimeFrame

# Alpaca API credentials
API_KEY = "PKMIDDD0B792FZO6HF7E"
SECRET_KEY = "u89kQV6dRJyom4ONFgpWHOr7jho8fY3SrMTD6Fvs"
BASE_URL = "https://paper-api.alpaca.markets"

api = tradeapi.REST(API_KEY, SECRET_KEY, base_url=BASE_URL)

# Define timeframe
timeframe = TimeFrame.Month

# Define start and end dates (ISO8601 format)
start_date = "2024-01-01T00:00:00Z"  # January 1, 2024
end_date = "2024-06-01T00:00:00Z"    # June 1, 2024

# Fetch historical bars with date range
bars = api.get_bars(symbol="AAPL", timeframe=timeframe, start=start_date, end=end_date).df

# Convert to DataFrame and display
bars_df = pd.DataFrame(bars)
print(bars_df)

# Save DataFrame to a CSV file
csv_filename = "AAPL_bars.csv"
bars_df.to_csv(csv_filename, index=False)

print(f"CSV file saved: {csv_filename}")