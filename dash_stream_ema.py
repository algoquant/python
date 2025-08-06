# Live EMA plot using Dash and Alpaca websocket

# To run:
# python3 dash_stream_ema.py SPY
# Then open the browser at http://127.0.0.1:8050


import os
import sys
import threading
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from numpy import sqrt
from alpaca.data import DataFeed, StockHistoricalDataClient
from alpaca.data.requests import StockLatestTradeRequest, StockLatestBarRequest
from alpaca.data.live.stock import StockDataStream

import dash
from dash import dcc, html
from dash.dependencies import Output, Input
import plotly.graph_objs as go

# Load environment variables
load_dotenv(".env")
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Validate credentials
if not DATA_KEY or not DATA_SECRET:
    raise ValueError("Missing DATA_KEY or DATA_SECRET in environment variables")

print(f"Using API key: {DATA_KEY[:8]}...")  # Show first 8 chars for debugging

# Alpaca clients
hist_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)

# Get symbol from user or argument
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()

tzone = ZoneInfo("America/New_York")
data_feed = DataFeed.SIP

# Get initial trade price and size
request_params = StockLatestTradeRequest(symbol_or_symbols=symbol, feed=data_feed)
latest_price = hist_client.get_stock_latest_trade(request_params)
latest_price = latest_price[symbol]
trade_price = latest_price.price
trade_size = latest_price.size

# Get initial bar for variance
request_params = StockLatestBarRequest(symbol_or_symbols=symbol, feed=data_feed)
bar_data = hist_client.get_stock_latest_bar(request_params)
bar_data = bar_data[symbol].model_dump()
price_var = (bar_data["high"] - bar_data["low"]) ** 2

# EMA state
alpha_param = 0.9
price_ema = trade_price
volume_ema = trade_size
price_emav = trade_price * trade_size

# Data for plotting
ema_times = []
ema_values = []

# Dash app setup
app = dash.Dash(__name__)
app.layout = html.Div([
    html.H2(f"Live EMA for {symbol}"),
    dcc.Graph(id="ema-graph", animate=True),
    dcc.Interval(id="interval-component", interval=2000, n_intervals=0),  # 2 seconds
])

# Shared state for thread-safe update
lock = threading.Lock()
stream_running = True

# Cleanup function
def cleanup():
    global stream_running
    print("Cleaning up stream connection...")
    stream_running = False
    # Give the thread a moment to stop gracefully
    import time
    time.sleep(1)

# EMA update callback for Alpaca websocket
async def update_ema(latest_price):
    global price_emav, volume_ema, price_ema, price_var
    trade_price = latest_price.price
    trade_size = latest_price.size

    with lock:
        price_emav = alpha_param * price_emav + (1 - alpha_param) * trade_price * trade_size
        volume_ema = alpha_param * volume_ema + (1 - alpha_param) * trade_size
        price_ema = price_emav / volume_ema
        price_var = alpha_param * price_var + (1 - alpha_param) * (trade_price - price_ema) ** 2

        time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
        ema_times.append(time_stamp)
        ema_values.append(price_ema)
        # Limit memory usage
        if len(ema_times) > 500:
            ema_times.pop(0)
            ema_values.pop(0)
# End update_ema callback

# Start websocket in a background thread with proper async handling
def run_stream():
    global stream_running
    
    async def async_stream():
        while stream_running:
            try:
                # Create a new stream client instance for this attempt
                print(f"Connecting to Alpaca stream for {symbol} using {data_feed.value} feed...")
                thread_data_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=data_feed)
                
                # Subscribe to trades
                thread_data_client.subscribe_trades(update_ema, symbol)
                
                print("Stream client configured, starting connection...")
                
                # Run the stream
                await thread_data_client._run_forever()
                    
            except ValueError as e:
                print(f"Authentication error: {e}")
                print("Please check your API credentials and permissions")
                if "auth failed" in str(e):
                    print("This may be due to:")
                    print("1. Invalid API key or secret")
                    print("2. Account doesn't have live data permissions")
                    print("3. Try using paper trading credentials")
                    break  # Don't retry auth failures
            except Exception as e:
                print(f"Stream connection error: {e}")
                if stream_running:
                    print("Attempting to reconnect in 10 seconds...")
                    await asyncio.sleep(10)  # Async sleep
                    continue
                else:
                    break
            finally:
                try:
                    if 'thread_data_client' in locals():
                        await thread_data_client.close()
                except:
                    pass
    
    # Run the async function
    try:
        asyncio.run(async_stream())
    except Exception as e:
        print(f"Stream thread error: {e}")

stream_thread = threading.Thread(target=run_stream, daemon=True)
stream_thread.start()

# Dash callback to update the plot
@app.callback(
    Output("ema-graph", "figure"),
    [Input("interval-component", "n_intervals")]
)
def update_graph(n):
    with lock:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ema_times, y=ema_values, mode='lines', name='EMA'))
        fig.update_layout(title=f"{symbol} EMA Over Time", xaxis_title="Time", yaxis_title="EMA Price")
        return fig

if __name__ == "__main__":
    try:
        app.run_server(debug=True)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        cleanup()
