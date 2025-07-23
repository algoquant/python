# A shiny app to plot live stock prices with EMA, using streaming prices from the Alpaca websocket.
# It may be too complex, but it demonstrates how to use the Alpaca API with Shiny in Python.
# A better approach would be to plot asynchronously every 5 seconds, instead of at each data tick.

from shiny import App, ui, render
import asyncio
import pandas as pd
import matplotlib.pyplot as plt
from alpaca.data.live.stock import StockDataStream
from alpaca.data import DataFeed
from threading import Thread
from dotenv import load_dotenv
import os


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")

# Validate credentials
if not DATA_KEY or not DATA_SECRET:
    raise ValueError("Missing DATA_KEY or DATA_SECRET in environment variables")

print(f"Using API key: {DATA_KEY[:8]}...")  # Show first 8 chars for debugging

# Websocket stream setup
stream = StockDataStream(DATA_KEY, DATA_SECRET, feed=DataFeed.SIP)

# Initialize DataFrame to store live prices
price_frame = pd.DataFrame(columns=["timestamp", "price"])


def on_bar(bar):
    global price_frame
    try:
        price_frame.loc[len(price_frame)] = [bar.timestamp, bar.close]
        # Calculate EMAs only if we have enough data
        if len(price_frame) >= 12:
            price_frame["EMA_12"] = price_frame["price"].ewm(span=12, adjust=False).mean()
        if len(price_frame) >= 26:
            price_frame["EMA_26"] = price_frame["price"].ewm(span=26, adjust=False).mean()
        
        # Limit memory usage
        if len(price_frame) > 1000:
            price_frame.drop(price_frame.index[0], inplace=True)
            price_frame.reset_index(drop=True, inplace=True)
    except Exception as e:
        print(f"Error processing bar data: {e}")

# Subscribe to stream
stream.subscribe_bars(on_bar, "AAPL")

def start_stream():
    try:
        asyncio.run(stream._run_forever())
    except Exception as e:
        print(f"Stream error: {e}")

# Run stream in background
Thread(target=start_stream, daemon=True).start()

# Shiny app UI
app_ui = ui.page_fluid(
    ui.h2("📈 Live Stock Price with EMA"),
    ui.output_plot("plot")
)

# Plot rendering
def plot_data():
    plt.clf()
    if not price_frame.empty:
        plt.plot(price_frame["timestamp"], price_frame["price"], label="Price", linewidth=2)
        if "EMA_12" in price_frame.columns and not price_frame["EMA_12"].isna().all():
            plt.plot(price_frame["timestamp"], price_frame["EMA_12"], label="EMA 12", alpha=0.7)
        if "EMA_26" in price_frame.columns and not price_frame["EMA_26"].isna().all():
            plt.plot(price_frame["timestamp"], price_frame["EMA_26"], label="EMA 26", alpha=0.7)
        plt.xlabel("Time")
        plt.ylabel("Price")
        plt.title("AAPL Live Price with EMAs")
        plt.legend()
        plt.xticks(rotation=45)
        plt.tight_layout()
    else:
        plt.text(0.5, 0.5, "Waiting for data...", transform=plt.gca().transAxes, 
                ha='center', va='center', fontsize=16)
    return plt.gcf()

# Reactive output
def server(input, output, session):
    @output
    @render.plot
    def plot():
        return plot_data()

# Run the app
app = App(app_ui, server)

