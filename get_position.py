# Get the open position for a stock symbol using the Alpaca TradingClient.

# Run the script from the terminal:
# python3 get_position.py SPY


from alpaca.trading.client import TradingClient
from dotenv import load_dotenv
import os
import sys


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
# Data keys
# DATA_KEY = os.getenv("DATA_KEY")
# DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

# Create the SDK trading client
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)

# Get the open position for the symbol
def get_position(trading_client, symbol):
    try:
        # Get the open position for the symbol
        position = trading_client.get_open_position(symbol)
        if position:
            print(f"Open position for {symbol}: {position.qty} shares at {position.avg_entry_price}")
            return position
        else:
            print(f"No open position for {symbol}.")
            return None
    except Exception as e:
        print(f"Error getting open position for {symbol}: {e}")
        return None
# End of get_position


# Get the symbol from the user
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()

# Get the open position for the symbol
position = get_position(trading_client, symbol)


# Print the open position for the symbol
if position:
    print(f"Symbol: {position.symbol}, Side: {position.side}, Qty: {position.qty}, QtyAvail: {position.qty_available}, Unreal_PnL: {position.unrealized_pl}")
else:
    print(f"No open position for {symbol}.")

