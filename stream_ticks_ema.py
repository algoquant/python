### Calculates the volume weighted EMA prices and variance from the streaming real-time tick stock prices from the Alpaca websocket.
# Saves the tick prices to a CSV file and plots the EMA prices with Bollinger Bands.

import os
import sys
import signal
from numpy import sqrt
import pandas as pd
import matplotlib.pyplot as plt
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from alpaca.data import DataFeed, StockHistoricalDataClient
from matplotlib.pyplot import bar
from alpaca.data.requests import StockLatestQuoteRequest, StockBarsRequest, StockLatestBarRequest, StockLatestTradeRequest
from alpaca.data.live.stock import StockDataStream
from dotenv import load_dotenv



# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
# TRADE_KEY = os.getenv("TRADE_KEY")
# TRADE_SECRET = os.getenv("TRADE_SECRET")

# Create the SDK data client for live and historical stock data
hist_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)
# Create the SDK data client for live stock prices
# Use SIP for comprehensive data, or IEX for free data.
data_feed = DataFeed.SIP
data_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=data_feed)
# Create the SDK trading client
# trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)


# --------- Load the initial stock prices --------

# Get the stock symbol from the command line
# symbol = "SPY"
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()

print(f"This script calculates the volume weighted EMA prices and variance from streaming real-time stock prices for {symbol}\n")

print("Initializing the EMA prices\n")
# Get the latest trade price and size
request_params = StockLatestTradeRequest(symbol_or_symbols=symbol, feed=data_feed)
last_trade = hist_client.get_stock_latest_trade(request_params)
# Get the latest trade price and size
last_trade = last_trade[symbol]
# symbol = last_trade.symbol
tzone = ZoneInfo("America/New_York")
time_stamp = last_trade.timestamp.astimezone(tzone).strftime("%Y-%m-%d %H:%M:%S")
new_price = last_trade.price
trade_size = last_trade.size
print(f"Latest trade price for {symbol}: Price = {new_price}, Size = {trade_size}")


# Get the latest 1-minute bar prices from SDK
# print(f"Getting latest 1-minute bar prices")
request_params = StockLatestBarRequest(
    symbol_or_symbols=symbol,
    feed=data_feed, # Or DataFeed.SIP, DataFeed.IEX
)
bar_prices = hist_client.get_stock_latest_bar(request_params)
bar_prices = bar_prices[symbol]
bar_prices = bar_prices.model_dump()
# Parse the bar prices
print(f"Latest bar prices: {bar_prices['open']}, High: {bar_prices['high']}, Low: {bar_prices['low']}, Close: {bar_prices['close']}, Volume: {bar_prices['volume']}, VWAP: {bar_prices['vwap']}\n")


# --------- Create the file names --------

# Create file names with today's NY date
time_now = datetime.now(tzone)
date_short = time_now.strftime("%Y-%m-%d")
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("data_dir_name")
# Create file name for the state variables
data_file = f"{dir_name}prices_EMA_{symbol}_{date_short}.csv"
# Create file name for the websocket errors
error_file = f"{dir_name}error_{symbol}_{date_short}.csv"
# Plot file
plot_file = f"{dir_name}plot_{symbol}_{date_short}.png"
# print(f"Data file: {data_file}")
# print(f"Error file: {error_file}")

print(f"The EMA prices are saved to {data_file}\n")
print(f"The plot file is: {plot_file}\n")



# --------- Create the model variables --------

# Define the alpha parameter for the exponential moving average
# The alpha parameter is the smoothing factor, and must be between 0 and 1
# The alpha parameter determines how much weight is given to the past data points
# The value of alpha closer to 1 gives more weight to the past data points
alpha_param = 0.99
alpha1 = 1 - alpha_param
alpha_squared = alpha_param ** 2
alpha2 = 1 - alpha_param

# Threshold for spike detection
spike_threshold = 2
# Previous price for spike detection
price_prev = new_price
# Boolean flag to indicate if the previous price was a spike
prev_spike = False

# The number of shares that have been traded
num_shares_traded = 0
# The number of shares before the next plot
num_shares_max = 10000
# The number of ticks that have been processed
num_ticks = 0
# The number of ticks before the next plot
num_ticks_max = 100
# Minimum shares size for the trade to be considered significant
min_size = 100
max_frame_size = 1000  # Maximum size of the price frame to keep in memory

# The initial EMA price is the trade price
price_ema = new_price
# The initial EMA volume is the trade size
volume_ema = trade_size
# The initial EMA price-volume is the product of the trade price and size
price_emav = new_price * trade_size
# The initial price variance is the squared difference between the high and low prices of the latest bar
# Set a minimum variance because sometimes in the morning the high and low prices are the same
price_varv_min = 0.001 # Minimum price variance to avoid division by zero
# price_var = max((bar_prices["high"] - bar_prices["low"]) ** 2, price_varv_min)
price_var = price_varv_min
price_varv = price_var * trade_size  # The initial price variance is the product of the price variance and trade size
price_vol = sqrt(price_var) # The price volatility is the square root of the price variance
# Number of standard deviations for the Bollinger Bands
bollinger_width = 1.0

# Combine the file names into a dictionary
file_names = {
    "data_file": data_file,
    "error_file": error_file,
    "plot_file": plot_file,
    "plot_title": f"{symbol} EMA Prices and Bollinger Bands with α = {alpha_param} / {date_short}",
}

# Combine the alpha parameters into a dictionary
alpha_params = {
    "alpha_param": alpha_param,
    "alpha1": alpha1,
    "alpha_squared": alpha_squared,
    "alpha2": alpha2,
}

# Combine the control variables into a dictionary
control_params = {
    "num_ticks": num_ticks,
    "num_shares_traded": num_shares_traded,
    "num_shares_max": num_shares_max,
    "max_frame_size": max_frame_size,
    "min_size": min_size,
    "bollinger_width": bollinger_width,
    "price_varv_min": price_varv_min,
    "spike_threshold": spike_threshold,
    "prev_spike": prev_spike,
    "price_prev": price_prev,
}

# Combine the price variables into a dictionary
ema_dict = {
    "price_ema": price_ema,
    "volume_ema": volume_ema,
    "price_emav": price_emav,
    "price_var": price_var,
    "price_varv": price_varv,
    "price_vol": price_vol,
}

# Create a DataFrame to hold the price data
price_dict = {
    "timestamp": time_stamp,
    "symbol": symbol,
    "price": new_price,
    "trade_size": trade_size,
    "ema_price": price_ema,
    "volatility": price_vol,
}
price_frame = pd.DataFrame([price_dict])



# --------- Create the utility functions --------

# Plot function to plot the EMA price and Bollinger Bands
def plot_ema(price_frame, control_params, file_names):
    
    # Keep only last max_frame_size records to limit memory usage
    max_frame_size = control_params["max_frame_size"]
    if len(price_frame) > max_frame_size:
        price_frame = price_frame.tail(max_frame_size).reset_index(drop=True)

    # Convert the timestamp to datetime
    price_frame["timestamp"] = pd.to_datetime(price_frame["timestamp"])
    # Add upper and lower Bollinger Bands to the price frame
    bollinger_width = control_params["bollinger_width"]
    price_frame["upper_band"] = price_frame["ema_price"] + bollinger_width * price_frame["volatility"]
    price_frame["lower_band"] = price_frame["ema_price"] - bollinger_width * price_frame["volatility"]
    
    # Plot the EMA price and the Bollinger Bands
    plt.figure(figsize=(20, 12))
    plt.plot(price_frame["timestamp"], price_frame["price"], label="Price", color="blue")
    plt.plot(price_frame["timestamp"], price_frame["ema_price"], label="EMA Price", color="red")
    plt.plot(price_frame["timestamp"], price_frame["upper_band"], label=f"Upper + {bollinger_width} STDV", color="orange", linestyle='--')
    plt.plot(price_frame["timestamp"], price_frame["lower_band"], label=f"Lower - {bollinger_width} STDV", color="orange", linestyle='--')
    plt.title(file_names["plot_title"], fontsize=20)
    plt.xlabel("Time", fontsize=16)
    plt.ylabel("Price", fontsize=16)
    # plt.xticks(fontsize=10) # For x-axis tick labels
    # plt.yticks(fontsize=10) # For y-axis tick labels
    # Change the font size of the x and y axis labels
    plt.tick_params(axis="both", which="major", labelsize=14)
    plt.legend(fontsize=16) # Add legend
    # Adjust layout
    plt.tight_layout()

    # Save the plot to a file
    plot_file = file_names["plot_file"]
    plt.savefig(plot_file)
    plt.close()  # Close the plot to free memory
    print(f"Plot saved to {plot_file}")



# Function to calculate the EMA price and variance
def calc_ema(new_price, trade_size, time_stamp, price_frame):

            global alpha_params, ema_dict, control_params
            # Update the EMA price using the latest trade price
            # price_emav = ema_dict["price_emav"]
            # price_emav = alpha_param * price_emav + alpha1 * trade_size * new_price
            # ema_dict["price_emav"] = price_emav
            # Update the EMA volume using the latest trade size
            # volume_ema = ema_dict["volume_ema"]
            # volume_ema = alpha_param * volume_ema + alpha1 * trade_size
            # ema_dict["volume_ema"] = volume_ema
            # The EMA price is the price-volume divided by the EMA volume
            # price_ema = price_emav / volume_ema
            price_ema = ema_dict["price_ema"]
            price_ema = alpha_param * price_ema + alpha1 * new_price
            ema_dict["price_ema"] = price_ema
            # Update the price variance using the latest prices
            # global price_varv
            # price_varv = alpha_squared * price_varv + alpha2 * trade_size * (new_price - price_ema) ** 2
            # price_var = price_varv / volume_ema
            price_var = ema_dict["price_var"]
            price_var = alpha_squared * price_var + alpha2 * (new_price - price_ema) ** 2
            price_var = max(price_var, price_varv_min) # Apply minimum variance
            ema_dict["price_var"] = price_var
            # Print the updated EMA price and volume
            # time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
            price_vol = sqrt(price_var) # The price volatility is the square root of the price variance
            ema_dict["price_vol"] = price_vol
            print(f"{time_stamp} {symbol} Price: {round(new_price, ndigits=2)}, Size: {trade_size}, EMA price: {round(price_ema, ndigits=2)}, Volatility: {round(price_vol, ndigits=4)}")

            # Append the price data to the CSV file
            price_dict = {
                "timestamp": time_stamp,
                "symbol": symbol,
                "price": new_price,
                "trade_size": trade_size,
                "ema_price": price_ema,
                "volatility": price_vol,
            }
            single_frame = pd.DataFrame([price_dict])
            # Append single_frame to data_file
            single_frame.to_csv(data_file, mode="a", header=not os.path.exists(data_file), index=False)
            # Append single_frame to price_frame
            price_frame = pd.concat([price_frame, single_frame], ignore_index=True)
            return price_frame

# End of function calc_ema



# --------- Define the callback function --------

print("The live and EMA prices:\n")

# The callback function is called after each new trade price arrives
async def handle_prices(last_trade):

    trade_size = last_trade.size

    # Check if the trade size is above the minimum size
    if trade_size >= min_size:
        # Get the latest trade price and size
        # last_trade = last_trade[symbol] # Uncomment if last_trade is a dict for multiple symbols
        symbol = last_trade.symbol
        time_stamp = last_trade.timestamp.astimezone(tzone).strftime("%Y-%m-%d %H:%M:%S")
        new_price = last_trade.price

        # Get the spike detection parameters
        global ema_dict, control_params, price_frame
        prev_spike = control_params["prev_spike"]
        spike_threshold = control_params["spike_threshold"]
        price_prev = control_params["price_prev"]
        price_vol = ema_dict["price_vol"]
        # Check if an isolated price spike was detected
        price_spike = abs(new_price - price_prev) > spike_threshold * price_vol
        if price_spike and not prev_spike:
            # A price spike was detected, print a message
            print(f"{time_stamp} {symbol} Price spike detected: {new_price} (previous price: {price_prev})")
            # Set the flag to indicate that a price spike was detected
            control_params["prev_spike"] = True
            # return # The current price is a spike, so we do not update the EMA price or variance
        elif (not price_spike) or (price_spike and prev_spike):
            # The current price is not a spike
            # Or
            # price_spike is True but prev_spike is also True, which means that the price has returned to the pre-spike value
            # The current price is not a spike because it has returned to the pre-spike value - reset the flag
            control_params["prev_spike"] = False
            # Update the previous price for the next iteration
            control_params["price_prev"] = new_price
            # Calculate the EMA price and the variance using the latest trade price
            price_frame = calc_ema(new_price, trade_size, time_stamp, price_frame)
            # Increment the number of ticks processed
            control_params["num_ticks"] += 1
            # Increment the number of shares traded
            control_params["num_shares_traded"] += trade_size
            # Every num_ticks_max ticks, plot the EMA
            # if num_ticks > num_ticks_max:
            if control_params["num_shares_traded"] > control_params["num_shares_max"]:
                # Reset the number of shares traded
                control_params["num_shares_traded"] = 0
                # print("Plotting the EMA price and volume...")
                price_frame = plot_ema(price_frame, control_params, file_names)

# End of callback function handle_prices


# --------- Run the websocket stream --------

# Subscribe to quote or trade updates
# data_client.subscribe_quotes(handle_quote, symbol)
data_client.subscribe_trades(handle_prices, symbol)

# Subscribe to OHLCV bar updates and pass them to the callback function
# data_client.subscribe_bars(handle_prices, symbol)

# Run the stream with error handling and auto-restart
try:
    data_client.run()
except Exception as e:
    time_stamp = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
    error_text = f"{time_stamp} WebSocket error: {e}. Restarting connection in 5 seconds..."
    print(error_text)
    with open(error_file, "a") as f: f.write(error_text)
    time.sleep(5)

print("Stream stopped by user.")


# --------- Handle Ctrl-C interrupt --------

# The code below stops the stream when the user presses Ctrl-C

def signal_handler(sig, frame):
    """Handle Ctrl-C (SIGINT) gracefully"""
    print("\n\nCtrl-C pressed! Exiting gracefully...")
    # Stop the stream client before exiting
    try:
        data_client.stop()
    except:
        pass
    sys.exit(0)

# Set up signal handler for Ctrl-C
print("Press Ctrl-C to stop the stream... \n")
signal.signal(signal.SIGINT, signal_handler)


