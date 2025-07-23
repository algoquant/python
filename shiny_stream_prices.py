# Shiny app for streaming real-time stock prices with live plot
# Based on stream_prices_single.py

import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from alpaca.data import DataFeed, StockHistoricalDataClient
from alpaca.data.live.stock import StockDataStream
from dotenv import load_dotenv
import os
import sys
import asyncio
from threading import Thread, Lock
from shiny import App, ui, render, reactive
import numpy as np


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
# Get API keys from environment
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Validate credentials
if not DATA_KEY or not DATA_SECRET:
    raise ValueError("Missing DATA_KEY or DATA_SECRET in environment variables")

print(f"Using API key: {DATA_KEY[:8]}...")

# Get the trading symbol
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = "SPY"  # Default symbol for demo

# Global data storage
price_data = pd.DataFrame(columns=["timestamp", "symbol", "price", "volume"])
data_lock = Lock()
stream_running = True

# Timezone setup
tzone = ZoneInfo("America/New_York")

# Create file name for CSV backup
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("data_dir_name")
os.makedirs(dir_name, exist_ok=True)
file_name = f"{dir_name}price_trades_{symbol}_{date_short}.csv"

# The callback function is called after each trade price update
async def handle_trade(latest_price):
    global price_data
    
    try:
        # Get the latest trade price and size
        time_stamp = latest_price.timestamp.astimezone(tzone)
        time_str = time_stamp.strftime("%Y-%m-%d %H:%M:%S")
        trade_price = latest_price.price
        trade_size = latest_price.size
        
        print(f"Time: {time_str}, Symbol: {symbol}, Price: {trade_price}, Size: {trade_size}")
        
        # Prepare a dict with the price data
        price_dict = {
            "timestamp": time_stamp,
            "symbol": symbol,
            "price": trade_price,
            "volume": trade_size,
        }
        
        # Thread-safe update of price data
        with data_lock:
            price_data.loc[len(price_data)] = price_dict
            
            # Limit memory usage - keep only last 1000 records
            if len(price_data) > 1000:
                price_data = price_data.tail(1000).reset_index(drop=True)
        
        # Append to CSV file for backup
        price_frame = pd.DataFrame([{
            "timestamp": time_str,
            "symbol": symbol,
            "price": trade_price,
            "volume": trade_size,
        }])
        price_frame.to_csv(file_name, mode="a", header=not os.path.exists(file_name), index=False)
        
    except Exception as e:
        print(f"Error in handle_trade: {e}")

# Stream function to run in background thread
def run_stream():
    global stream_running
    
    async def async_stream():
        while stream_running:
            try:
                print(f"Connecting to Alpaca stream for {symbol} using SIP feed...")
                stream_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=DataFeed.SIP)
                stream_client.subscribe_trades(handle_trade, symbol)
                
                print("Stream client connected, starting data flow...")
                await stream_client._run_forever()
                
            except ValueError as e:
                print(f"Authentication error: {e}")
                print("Please check your API credentials and permissions")
                break
            except Exception as e:
                print(f"Stream connection error: {e}")
                if stream_running:
                    print("Attempting to reconnect in 10 seconds...")
                    await asyncio.sleep(10)
                    continue
                else:
                    break
    
    try:
        asyncio.run(async_stream())
    except Exception as e:
        print(f"Stream thread error: {e}")

# Start the stream in a background thread
stream_thread = Thread(target=run_stream, daemon=True)
stream_thread.start()

# Shiny UI
app_ui = ui.page_fluid(
    ui.h1(f"📈 Live Stock Prices - {symbol}"),
    ui.div(
        ui.h3("Current Price Data"),
        ui.output_text("current_price"),
        style="margin-bottom: 20px;"
    ),
    ui.div(
        ui.h3("Live Price Chart"),
        ui.output_plot("price_plot", height="500px"),
        style="margin-bottom: 20px;"
    ),
    ui.div(
        ui.h3("Recent Trades"),
        ui.output_table("recent_trades"),
        style="margin-bottom: 20px;"
    ),
    # Auto-refresh every 2 seconds
    ui.tags.script(
        """
        setInterval(function() {
            Shiny.setInputValue('refresh', Math.random());
        }, 2000);
        """
    )
)

# Server function
def server(input, output, session):
    
    # Reactive value for auto-refresh
    @reactive.Calc
    def get_current_data():
        # This will be invalidated by the JavaScript refresh
        input.refresh()
        
        with data_lock:
            return price_data.copy() if not price_data.empty else pd.DataFrame()
    
    @output
    @render.text
    def current_price():
        df = get_current_data()
        if df.empty:
            return "Waiting for data..."
        
        latest = df.iloc[-1]
        return f"Latest: ${latest['price']:.2f} | Volume: {latest['volume']:,} | Time: {latest['timestamp'].strftime('%H:%M:%S')}"
    
    @output
    @render.plot
    def price_plot():
        df = get_current_data()
        
        plt.figure(figsize=(12, 6))
        plt.clf()
        
        if df.empty:
            plt.text(0.5, 0.5, "Waiting for live data...", 
                    transform=plt.gca().transAxes, ha='center', va='center', 
                    fontsize=16, color='gray')
            plt.title(f"{symbol} - No Data Yet")
        else:
            # Plot price over time
            plt.plot(df['timestamp'], df['price'], 'b-', linewidth=2, alpha=0.8)
            plt.scatter(df['timestamp'], df['price'], c='red', s=20, alpha=0.6)
            
            # Add moving average if enough data
            if len(df) >= 20:
                ma_20 = df['price'].rolling(window=20).mean()
                plt.plot(df['timestamp'], ma_20, 'r--', alpha=0.7, label='MA(20)')
                plt.legend()
            
            plt.title(f"{symbol} Live Price Stream")
            plt.xlabel("Time")
            plt.ylabel("Price ($)")
            plt.grid(True, alpha=0.3)
            
            # Format x-axis to show time nicely
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
            plt.gca().xaxis.set_major_locator(mdates.MinuteLocator(interval=1))
            plt.xticks(rotation=45)
            
            # Add current price annotation
            if not df.empty:
                latest_price = df.iloc[-1]['price']
                latest_time = df.iloc[-1]['timestamp']
                plt.annotate(f'${latest_price:.2f}', 
                           xy=(latest_time, latest_price), 
                           xytext=(10, 10), textcoords='offset points',
                           bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7),
                           arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))
        
        plt.tight_layout()
        return plt.gcf()
    
    @output
    @render.table
    def recent_trades():
        df = get_current_data()
        if df.empty:
            return pd.DataFrame({"Message": ["No data available yet"]})
        
        # Show last 10 trades
        recent = df.tail(10).copy()
        recent['timestamp'] = recent['timestamp'].dt.strftime('%H:%M:%S')
        recent['price'] = recent['price'].apply(lambda x: f"${x:.2f}")
        recent['volume'] = recent['volume'].apply(lambda x: f"{x:,}")
        
        return recent[['timestamp', 'price', 'volume']].rename(columns={
            'timestamp': 'Time',
            'price': 'Price',
            'volume': 'Volume'
        })

# Cleanup function
def cleanup():
    global stream_running
    print("Cleaning up stream connection...")
    stream_running = False
    time.sleep(1)

# Create and run the app
app = App(app_ui, server)

if __name__ == "__main__":
    try:
        print(f"Starting Shiny app for {symbol}...")
        print("Open your browser to http://127.0.0.1:8000")
        app.run(port=8000)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        cleanup()
