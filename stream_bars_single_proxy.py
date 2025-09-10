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

# --------- Get the trading symbol from the command line arguments --------
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()


# --------- Create the file names --------
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
# Load from the .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
dir_name = os.getenv("DATA_DIR_NAME") or "./"
file_name = f"{dir_name}price_bars_{symbol}_{date_short}.csv"

print(f"This script streams real-time stock bar prices for {symbol} via the Alpaca websocket API, and saves them to the CSV file {file_name}\n")


# --------- Define the callback function for handling price bars --------

# The price bar handler converts the JSON to a dictionary and then to a DataFrame, and saves it to a CSV file
async def handle_bar(bar):

    # bar is a dict from JSON, convert timestamp and extract fields
    time_stamp = bar.get("t")
    if time_stamp:
        # If timestamp is in ISO format, parse it
        try:
            dt = datetime.fromisoformat(time_stamp.replace("Z", "+00:00")).astimezone(tzone)
            time_stamp = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass
    else:
        time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")

    symbol = bar.get("S")
    open = bar.get("o")
    high = bar.get("h")
    low = bar.get("l")
    close = bar.get("c")
    volume = bar.get("v")
    trade_count = bar.get("n")
    vwap = bar.get("vw")
    print(f"Time: {time_stamp}, Symbol: {symbol}, Open: {open}, High: {high}, Low: {low}, Close: {close}, Volume: {volume}, Trade_count: {trade_count}, VWAP: {vwap}")

    # Prepare a dict with the price bar data from JSON fields
    bar_dict = {
        "timestamp": time_stamp,
        "symbol": symbol,
        "open": open,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "trade_count": trade_count,
        "vwap": vwap
    }
    # Append the price bars to the CSV file for the symbol
    price_bar = pd.DataFrame([bar_dict])
    price_bar.to_csv(file_name, mode="a", header=not os.path.exists(file_name), index=False)

# End handle_bar callback


# --------- Define the callback function for streaming price bars --------

async def stream_bars():

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
                                    await handle_bar(event)
                        elif isinstance(data, dict):
                            if data.get("T") == "b" and data.get("S") == symbol:
                                await handle_bar(data)
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
