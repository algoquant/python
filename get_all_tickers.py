import alpaca_trade_api as tradeapi
import pandas as pd
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

# Fetch all active assets
active_assets = api.list_assets(status="active")

# Extract ticker symbols
tickers = [asset.symbol for asset in active_assets]

# Convert to DataFrame
tickers_df = pd.DataFrame(tickers, columns=["Ticker"])

# Save to CSV
csv_filename = "active_tickers.csv"
tickers_df.to_csv(csv_filename, index=False)

print(f"CSV file saved: {csv_filename}")
