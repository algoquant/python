"""
Stream real-time stock bars for one symbol via a local WebSocket proxy.

Run the proxy server in one terminal:
    python3 live_data_proxy.py SPY

Run stream client in another terminal:
    python3 stream_bars_single_proxy.py SPY
Console-only mode (no CSV writes):
    python3 stream_bars_single_proxy.py --nofile SPY
Custom env file:
    python3 stream_bars_single_proxy.py SPY --env-file /path/to/.env

"""

import os
import sys
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo
import json
import asyncio
import signal
import websockets
from TechIndic import Bar
from MachineTrader.helpers.file_writing_helpers import current_price_bars_file_name
from MachineTrader.helpers.parse_args import parse_stream_bars_single_args
from MachineTrader.helpers.live_data import event_symbol, is_bar_event, resolve_data_proxy_url


# --------- Get the trading symbol from command line arguments --------
def parse_arguments():
    """Parse CLI arguments for symbol, output mode, and env file path."""
    normalized_argv = ["--nofile" if str(arg).strip().lower() == "nofile" else arg for arg in sys.argv[1:]]
    return parse_stream_bars_single_args(normalized_argv)


args = parse_arguments()
no_file = bool(args.nofile)
env_file = str(args.env_file)

if args.symbol:
    symbol = str(args.symbol).strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()


# --------- Build output filename --------
timezone = ZoneInfo("America/New_York")
time_now = datetime.now(timezone)
date_short = time_now.strftime("%Y%m%d")
load_dotenv(env_file)
dir_name = os.getenv("DATA_DIR_NAME") or "./"

file_name = current_price_bars_file_name(symbol, dir_name, timezone)
file_exists = os.path.exists(file_name)

if no_file:
    print(
        f"This script streams real-time stock bar prices for {symbol} via the Alpaca websocket API, "
        "without writing files (console update on each incoming bar).\n"
    )
else:
    print(
        f"This script streams real-time stock bar prices for {symbol} via the Alpaca websocket API, "
        f"and saves them to the CSV file {file_name}\n"
    )
    if file_exists:
        print(f"CSV exists. New bars will be appended to {file_name}\n")
    else:
        print(f"CSV does not exist. A new file will be created at {file_name}\n")


async def stream_bars():
    """Read bar events from proxy and either print or save them."""
    data_proxy_url = resolve_data_proxy_url(None)
    reconnect_delay = 5

    def print_console_bar(event):
        print(
            "[BAR] "
            f"symbol={event.get('S')} "
            f"time={event.get('t')} "
            f"open={event.get('o')} "
            f"high={event.get('h')} "
            f"low={event.get('l')} "
            f"close={event.get('c')} "
            f"volume={event.get('v')}"
        )

    while True:
        try:
            async with websockets.connect(data_proxy_url) as ws:
                print(f"Connected to WebSocket proxy at {data_proxy_url}")
                async for message in ws:
                    try:
                        data = json.loads(message)
                        events = data if isinstance(data, list) else [data]

                        for event in events:
                            if not isinstance(event, dict):
                                continue
                            if not is_bar_event(event) or event_symbol(event) != symbol:
                                continue

                            if no_file:
                                print_console_bar(event)
                            else:
                                file_name = current_price_bars_file_name(symbol, dir_name, timezone)
                                bar_object = Bar(event, timezone)
                                await bar_object.save_bar(file_name)
                    except Exception as e:
                        print(f"Error processing message: {e}")
        except Exception as e:
            print(f"WebSocket error: {e}. Reconnecting in {reconnect_delay} seconds...")
            await asyncio.sleep(reconnect_delay)


def signal_handler(sig, frame):
    print("\n\nCtrl-C pressed - Exiting...")
    sys.exit(0)


if __name__ == "__main__":
    print("Press Ctrl-C to stop the stream... \n")
    signal.signal(signal.SIGINT, signal_handler)
    asyncio.run(stream_bars())
