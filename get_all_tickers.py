import alpaca_trade_api as tradeapi
import pandas as pd

# Alpaca API credentials
API_KEY = "PKMIDDD0B792FZO6HF7E"
SECRET_KEY = "u89kQV6dRJyom4ONFgpWHOr7jho8fY3SrMTD6Fvs"
BASE_URL = "https://paper-api.alpaca.markets"

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
