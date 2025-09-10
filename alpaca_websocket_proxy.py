"""
Proxy server for the Alpaca WebSocket, using websockets and asyncio. 
It listens for client connections, subscribes to Alpaca's WebSocket, and relays messages to all connected clients.
You need to install: pip3 install websockets aiohttp

How it works:
Client scripts connect to ws://localhost:8765 and receive all the messages from Alpaca's WebSocket.
The proxy authenticates and subscribes to Alpaca's stream, then relays all messages to connected clients.
You can expand this to handle client-specific subscriptions or message filtering.

Note:
Replace "trades": ["AAPL", "MSFT"] with your desired symbols.
Make sure your .env file or environment variables provide DATA_KEY and DATA_SECRET.

To stream data from the WebSocket proxy, first change the path to the .env file.
Then run the WebSocket proxy in a terminal and specify the symbols, for example SPY:
    python3 alpaca_websocket_proxy.py SPY
Then you can run a streaming script in another terminal:
    python3 stream_bars_single_proxy.py SPY

"""


import asyncio
import websockets
import aiohttp
import os
import sys
from dotenv import load_dotenv

# Alpaca WebSocket URL (use /iex for free data)
ALPACA_WS_URL = "wss://stream.data.alpaca.markets/v2/sip"
# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
PROXY_HOST = "localhost"
PROXY_PORT = 8765

clients = set()


# --------- Get the symbols from the command line arguments --------

# Get the symbols from the command line arguments
if len(sys.argv) > 1:
    symbols = [arg.strip().upper() for arg in sys.argv[1:]]
    print(f"Setting up proxy for: {symbols}")
else:
    print("No symbols provided - exiting")
    sys.exit(1)


# --------- Define the Alpaca WebSocket proxy server --------

async def websocket_handler(websocket, path):
    clients.add(websocket)
    try:
        async for message in websocket:
            # Optionally handle client messages (e.g., subscribe/unsubscribe)
            pass
    finally:
        clients.remove(websocket)


# --------- Define the Alpaca WebSocket proxy server startup function --------

async def relay_alpaca_stream():
    reconnect_delay = 5  # seconds
    while True:
        try:
            async with websockets.connect(ALPACA_WS_URL) as alpaca_ws:
                try:
                    # Authenticate
                    auth_msg = {
                        "action": "auth",
                        "key": DATA_KEY,
                        "secret": DATA_SECRET
                    }
                    await alpaca_ws.send(str(auth_msg).replace("'", '"'))
                    # Optionally subscribe to channels
                    sub_msg = {
                        "action": "subscribe",
                        "trades": symbols,
                        "quotes": [],
                        "bars": symbols
                    }
                    await alpaca_ws.send(str(sub_msg).replace("'", '"'))

                    async for msg in alpaca_ws:
                        # Relay to all connected clients
                        websockets.broadcast(clients, msg)
                except websockets.ConnectionClosed as e:
                    print(f"[Alpaca Proxy] Connection closed: {e}. Reconnecting in {reconnect_delay} seconds...")
                    await asyncio.sleep(reconnect_delay)
                except Exception as e:
                    print(f"[Alpaca Proxy] Error in Alpaca stream: {e}. Reconnecting in {reconnect_delay} seconds...")
                    await asyncio.sleep(reconnect_delay)
        except (OSError, websockets.InvalidURI, websockets.InvalidHandshake) as e:
            print(f"[Alpaca Proxy] Connection error: {e}. Retrying in {reconnect_delay} seconds...")
            await asyncio.sleep(reconnect_delay)

        except KeyboardInterrupt:
            print("[Alpaca Proxy] Relay stopped by user.")
            break


# --------- Add main entry point to start the proxy server and relay ---------

async def main():
    # Start proxy server for clients
    server = await websockets.serve(websocket_handler, PROXY_HOST, PROXY_PORT)
    print(f"[Alpaca Proxy] Listening on ws://{PROXY_HOST}:{PROXY_PORT}")
    # Start Alpaca stream relay in a background task
    relay_task = asyncio.create_task(relay_alpaca_stream())
    await server.wait_closed()
    await relay_task

if __name__ == "__main__":
    try:
        print("Press Ctrl-C to stop the proxy server... \n")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[Alpaca Proxy] Server stopped by user")
