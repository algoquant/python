### Get the positions from Alpaca, with the available shares to trade, using the Alpaca SDK.
# https://docs.alpaca.markets/reference/getallopenpositions

# import requests
import pandas as pd
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
import os


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Trade keys
TRADE_KEY = os.getenv("ALPACA_TRADE_KEY")
TRADE_SECRET = os.getenv("ALPACA_TRADE_SECRET")

# Create the SDK trading client
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)

# Get all the open positions using the trading client
portfolio = trading_client.get_all_positions()
# type(portfolio)  # Check if it's a list or object
# portfolio  # Print the portfolio to see its contents

# Loop through the portfolio and print each position's details
for position in portfolio:
    print(f"Symbol: {position.symbol}, Side: {position.side}, Qty: {position.qty}, QtyAvail: {position.qty_available}, Unreal_PnL: {position.unrealized_pl}")
#     # Define the request parameters
# Extract 'qty' as an integer from the first position
#qty = int(portfolio[0]['qty'])

# Access the first position's quantity
position = portfolio[0]  # Get the first position
qty = int(position.qty)  # ✅ Use dot notation instead of brackets
symbol = position.symbol
# print(qty)  # Output: -2    

if ( qty < 0  ):
    print(f"Your first position is a short position of {qty} shares of {symbol}, with an unrealized PnL of: {position.unrealized_pl}")
else:
    print(f"Your first position is a long position of {qty} shares of {symbol}, with an unrealized PnL of: {position.unrealized_pl}")

# Convert positions to data frame
position_frame = pd.DataFrame(position)
position_frame.shape
# print(position_frame)


# Get current NY time
time_now = datetime.now(ZoneInfo("America/New_York"))
date_short = time_now.strftime("%Y%m%d")
filename = "positions_" + date_short + ".csv"
position_frame.to_csv(filename, index=False)
print("Finished getting positions and saving to CSV file")


''' 

### Alternative way to get the positions using requests
# Get the positions from Alpaca, with the available shares to trade.
# Define Alpaca API request parameters
headers = {
    "APCA-API-KEY-ID": TRADE_KEY,
    "APCA-API-SECRET-KEY": TRADE_SECRET
}
url = "https://paper-api.alpaca.markets/v2/positions"

# Submit the request to get the positions from the Alpaca endpoint
response = requests.get(url, headers=headers)

# Parse the response into json format
positions = response.json()

# Check if positions are not empty
if not positions:
    print("No open positions found.")
else:
    positions = positions[0]
    for key, value in positions.items():
        print(f"{key}: {value}")
    # Extract the quantity available for trading
    qty_available = int(positions["qty_available"])
# print(response.text)
response = response.json()[0]
# type(response)

# Extract the quantity available for trading
int(response["qty_available"])

''' 

