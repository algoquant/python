"""
Stream real-time stock bar prices for a single symbol via a local WebSocket proxy, and save them to a CSV file.

To run the WebSocket proxy, first change the path to the .env file.
Run the WebSocket proxy in a terminal:
    python3 alpaca_websocket_proxy.py SPY
Then run the streaming data script in another terminal:
    python3 stream_bars_single_proxy.py SPY

"""

import os
import sys
import time
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import json
import asyncio
import signal
import websockets
from TechIndic import Bar

# --------- Get the trading symbol from the command line arguments --------
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()


# --------- Create the file names --------
timezone = ZoneInfo("America/New_York")
time_now = datetime.now(timezone)
date_short = time_now.strftime("%Y%m%d")
# Load from the .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
dir_name = os.getenv("DATA_DIR_NAME") or "./"
file_name = f"{dir_name}price_bars_{symbol}_{date_short}.csv"

print(f"This script streams real-time stock bar prices for {symbol} via the Alpaca websocket API, and saves them to the CSV file {file_name}\n")


# --------- Define the callback function for streaming price bars --------

async def stream_bars():
    """
    Stream the price bars from WebSocket proxy and process them for trading strategy.
    
    When a new WebSocket bar message arrives matching the symbol, it creates a new Bar instance
    directly from the JSON data using the Bar constructor.
    It then calls the strategy function specified by strategy.strategy_function via the execute_strategy method.
    
    Args:
        symbol (str): Trading symbol to filter for
        strategy: Strategy instance with execute_strategy method and strategy_function attribute
    """

    # Connect to the WebSocket proxy URL
    proxy_url = "ws://localhost:8765"
    reconnect_delay = 5
    while True:
        try:
            async with websockets.connect(proxy_url) as ws:
                print(f"Connected to WebSocket proxy at {proxy_url}")
                async for message in ws:
                    try:
                        data = json.loads(message)
                        # Alpaca sends a list of events, each is a dict
                        if isinstance(data, list):
                            for event in data:
                                # Only handle bar events for our symbol
                                if event.get("T") == "b" and event.get("S") == symbol:
                                    # Create Bar object and save to CSV
                                    bar_object = Bar(event, timezone)
                                    await bar_object.save_bar(file_name)
                        elif isinstance(data, dict):
                            if data.get("T") == "b" and data.get("S") == symbol:
                                # Create Bar object and save to CSV
                                bar_object = Bar(data, timezone)
                                await bar_object.save_bar(file_name)
                    except Exception as e:
                        print(f"Error processing message: {e}")
        except Exception as e:
            print(f"WebSocket error: {e}. Reconnecting in {reconnect_delay} seconds...")
            time.sleep(reconnect_delay)

# End stream_bars


def signal_handler(sig, frame):
    print("\n\nCtrl-C pressed - Exiting...")
    sys.exit(0)

if __name__ == "__main__":
    print("Press Ctrl-C to stop the stream... \n")
    signal.signal(signal.SIGINT, signal_handler)
    asyncio.run(stream_bars())
