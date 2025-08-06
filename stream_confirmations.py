### Receives streaming trade confirmations for submitted orders via the WebSocket.
# When an order is submitted, filled, cancelled, etc, the user receives an event via the WebSocket.
# Updates the position variable based on the fills.

# Run this script in a terminal to listen for trade updates, 
# and then submit an order in another terminal to see the updates.
# https://alpaca.markets/sdks/python/trading.html

import os
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.trading.stream import TradingStream
from dotenv import load_dotenv


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

# Create the SDK confirm trading update client
confirm_stream = TradingStream(TRADE_KEY, TRADE_SECRET)


# --------- Create the file names --------

# Create the strategy name
strategy_name = "Strat001"
# Define the trading parameters
symbol = "SPY"

# Create the file names for the submitted trade orders and the fills
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("data_dir_name")
submits_file = f"{dir_name}submits_{strategy_name}_{symbol}_{date_short}.csv"
fills_file = f"{dir_name}fills_{strategy_name}_{symbol}_{date_short}.csv"
print(f"The order submits file is: {submits_file}\n")
print(f"The order fills file is: {fills_file}\n")

# Initialize the global variables
position = 0  # Initialize position variable



# Callback function to handle trade updates
async def handle_trade_update(event_data):
    global response  # Access the global response variable
    
    # Debug: Print incoming event data
    print(f"Received trade update: {event_data.event} for order {event_data.order.id}")
    
    # Compare order IDs (ensure both are strings)
    if response and str(event_data.order.id) == str(response.id):
        print(f"Trade update for our order {response.id}: {event_data.event}")
        
        # Convert to dictionary for processing
        event_dict = event_data.model_dump()
        event_name = event_dict["event"]
        
        # Process fill events
        if event_name in ["fill", "partial_fill"]:
            print(f"Order {response.id} filled!")
            # Stop the stream after receiving fill
            await confirm_stream.stop_ws()
            
            # Process fill data and save to CSV
            orderinfo = event_dict["order"]
            fill_data = pd.DataFrame([event_dict])
            fill_data.to_csv(fills_file, mode="a", header=not os.path.exists(fills_file), index=False)
            print(f"Fill data saved to {fills_file}")
            
        print("Finished processing trade update\n")
    else:
        print(f"Trade update for different order: {event_data.order.id}")

# End of callback function handle_trade_update


# Subscribe to trade updates and supply the handler as a parameter
# data_client.subscribe_trades(handle_trade, symbol)
confirm_stream.subscribe_trade_updates(handle_trade_update)


# Start the WebSocket streaming
async def main():
    # Run the confirm_stream until order is filled
    await confirm_stream.run()


# Check whether the script is being run directly or is imported as a module
# Check whether the script is being run directly or is imported as a module
if __name__ == "__main__":
    if response:  # Only run if order was successfully submitted
        print("Starting WebSocket stream to listen for trade updates...")
        
        # Use asyncio.run() directly - simpler and more reliable
        try:
            asyncio.run(main())
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                # If we're in Jupyter or similar/Users/jerzy/Develop/Python/.environment with existing loop
                import nest_asyncio
                nest_asyncio.apply()
                asyncio.run(main())
            else:
                raise e
        except Exception as e:
            print(f"Error running WebSocket stream: {e}")
    else:
        print("No order was submitted, skipping WebSocket stream.")

