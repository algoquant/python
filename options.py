import alpaca_trade_api as tradeapi
from dotenv import load_dotenv
import os

# Load API keys from .env file
load_dotenv(".env")

# Get API keys from environment
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Replace with your actual API key and secret key
data_client = tradeapi.REST(DATA_KEY, DATA_SECRET)

try:
    # Example: Get option data for AAPL 250515C00175000
    option_symbol = "AAPL250515C00175000"
    option = data_client.(option_symbol)

    if option:
      latest_price = option.price
      print(f"The latest price for {option_symbol} is: {latest_price}")
    else:
        print(f"Could not retrieve option data for {option_symbol}")

except Exception as e:
    print(f"An error occurred: {e}")
