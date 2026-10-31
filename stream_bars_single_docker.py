"""
Stream real-time stock bar prices for a single symbol via a Docker WebSocket proxy, and save them to a CSV file.

You can run this script in the terminal for SPY as follows:
First start the Docker proxy:
    docker run -p 8765:8765 -e USE_POLYGON=false shlomik/alpaca-proxy-agent
Then run the streaming script:
    python3 stream_bars_single_docker.py SPY

"""

import os
import sys
import asyncio
import signal
import json
import time
import websockets
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from dotenv import load_dotenv

# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# --------- Get the trading symbol from the command line arguments --------

if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()


# --------- Create the file names --------

# Load environment variables
load_dotenv("/Users/jerzy/Develop/Python/.env")

# Create a file name with today's NY date
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("DATA_DIR_NAME") or "./"
file_name = f"{dir_name}price_bars_{symbol}_{date_short}.csv"

print(f"This script streams real-time stock bar prices for {symbol} via Docker WebSocket proxy at localhost:8765, and saves them to the CSV file {file_name}\n")


# --------- Define the callback function for handling price bars --------

async def handle_bar(bar):
    # bar is a dict from the Docker proxy JSON with single-letter keys
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


# --------- WebSocket connection to Docker proxy --------

async def stream_bars():
    # Connect to the Docker WebSocket proxy URL
    proxy_url = "ws://localhost:8765"
    reconnect_delay = 5
    message_count = 0
    max_reconnect_attempts = 10
    reconnect_attempts = 0
    
    while reconnect_attempts < max_reconnect_attempts:
        try:
            reconnect_attempts += 1
            print(f"Attempting to connect to {proxy_url}... (attempt {reconnect_attempts}/{max_reconnect_attempts})")
            
            async with websockets.connect(proxy_url, ping_interval=None, ping_timeout=None) as ws:
                print(f"✅ Connected to Docker WebSocket proxy at {proxy_url}")
                # Don't reset reconnect_attempts here - only reset after sustained connection
                
                # Send authentication message
                auth_msg = {
                    "action": "authenticate",
                    "data": {
                        "key_id": DATA_KEY,
                        "secret_key": DATA_SECRET
                    }
                }
                print(f"🔑 Sending authentication...")
                await ws.send(json.dumps(auth_msg))
                
                # Wait for auth response with timeout
                try:
                    auth_response = await asyncio.wait_for(ws.recv(), timeout=10.0)
                    print(f"🔐 Auth response: {auth_response}")
                    
                    # Parse auth response to check if successful
                    auth_data = json.loads(auth_response)
                    if isinstance(auth_data, dict) and auth_data.get("stream") == "authorization":
                        if auth_data.get("data", {}).get("status") == "authorized":
                            print(f"✅ Authentication successful!")
                        else:
                            print(f"❌ Authentication failed: {auth_data}")
                            continue  # Reconnect
                    
                except asyncio.TimeoutError:
                    print(f"⏰ Authentication timeout - no response received")
                    continue  # Reconnect
                except json.JSONDecodeError:
                    print(f"❌ Invalid JSON in auth response: {auth_response}")
                    continue  # Reconnect
                
                # Send subscription message for bars
                subscribe_msg = {
                    "action": "listen",
                    "data": {
                        "streams": [f"AM.{symbol}"]  # Alpaca minute bars format
                    }
                }
                print(f"📡 Subscribing to bars for {symbol}...")
                await ws.send(json.dumps(subscribe_msg))
                
                # Wait for subscription confirmation
                try:
                    sub_response = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    print(f"📋 Subscription response: {sub_response}")
                except asyncio.TimeoutError:
                    print(f"⏰ Subscription timeout - proceeding anyway")
                
                print("Waiting for messages...")
                
                # Reset reconnect attempts after successful auth and subscription
                reconnect_attempts = 0
                
                async for message in ws:
                    message_count += 1
                    print(f"\n📨 Message #{message_count} received at {datetime.now().strftime('%H:%M:%S')}")
                    print(f"📏 Message length: {len(message)} characters")
                    
                    # Show first 500 characters of raw message
                    preview = message[:500] + "..." if len(message) > 500 else message
                    print(f"📋 Raw message preview: {preview}")
                    
                    try:
                        data = json.loads(message)
                        print(f"✅ JSON parsed successfully")
                        print(f"📊 Data type: {type(data)}")
                        
                        # Docker proxy sends a list of events, each is a dict
                        if isinstance(data, list):
                            print(f"📝 Received list with {len(data)} items")
                            for i, event in enumerate(data):
                                event_type = event.get('T', 'Unknown')
                                event_symbol = event.get('S', 'Unknown')
                                print(f"  📍 Item {i+1}: Type='{event_type}', Symbol='{event_symbol}'")
                                
                                # Only handle bar events for our symbol
                                if event.get("T") == "b" and event.get("S") == symbol:
                                    print(f"🎯 Processing bar data for {symbol}")
                                    await handle_bar(event)
                                elif event.get("T") == "b":
                                    print(f"⏭️  Skipping bar for different symbol: {event.get('S')}")
                                    
                        elif isinstance(data, dict):
                            event_type = data.get('T', 'Unknown')
                            event_symbol = data.get('S', 'Unknown')
                            print(f"📝 Received dict: Type='{event_type}', Symbol='{event_symbol}'")
                            
                            if data.get("T") == "b" and data.get("S") == symbol:
                                print(f"🎯 Processing bar data for {symbol}")
                                await handle_bar(data)
                            elif data.get("T") == "b":
                                print(f"⏭️  Skipping bar for different symbol: {data.get('S')}")
                        else:
                            print(f"❓ Unexpected data format: {type(data)}")
                            
                    except json.JSONDecodeError as e:
                        print(f"❌ JSON decode error: {e}")
                        print(f"🔍 Problematic message: {message}")
                    except Exception as e:
                        print(f"❌ Error processing message: {e}")
                        print(f"🔍 Message that caused error: {message}")
                        
        except websockets.ConnectionClosed as e:
            print(f"🔌 WebSocket connection closed: {e}")
            if reconnect_attempts >= max_reconnect_attempts:
                print(f"❌ Max reconnection attempts ({max_reconnect_attempts}) reached. Exiting.")
                break
            print(f"🔄 Reconnecting in {reconnect_delay} seconds... (attempt {reconnect_attempts+1}/{max_reconnect_attempts})")
            await asyncio.sleep(reconnect_delay)
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
            if reconnect_attempts >= max_reconnect_attempts:
                print(f"❌ Max reconnection attempts ({max_reconnect_attempts}) reached. Exiting.")
                break
            print(f"🔄 Reconnecting in {reconnect_delay} seconds... (attempt {reconnect_attempts+1}/{max_reconnect_attempts})")
            await asyncio.sleep(reconnect_delay)
    
    print(f"🔚 Stream ended after {reconnect_attempts} connection attempts.")

# End stream_bars


# --------- Main with async WebSocket handling --------

def signal_handler(sig, frame):
    print("\n\nCtrl-C pressed - Exiting...")
    sys.exit(0)

async def main():
    print("Press Ctrl-C to stop the stream... \n")
    signal.signal(signal.SIGINT, signal_handler)
    await stream_bars()

if __name__ == "__main__":
    asyncio.run(main())


