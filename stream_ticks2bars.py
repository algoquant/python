### Aggregates the streaming real-time stock price ticks from the Alpaca websocket into 1-second bar prices.
# Calculates the volume weighted EMA prices and variance from the streaming real-time tick stock prices.
# Saves the bar prices to a CSV file and plots the EMA prices with Bollinger Bands.

# You can run this script in the terminal:
# python3 stream_ticks2bars.py SPY


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
import os
import sys
import signal



# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv(".env")
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
stream_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=data_feed)
# Create the SDK trading client
# trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)


# --------- Get the trading parameters from the command line arguments --------

# Get the stock symbol
# symbol = "SPY"
if len(sys.argv) > 1:
    symbol = sys.argv[1].strip().upper()
else:
    symbol = input("Enter symbol: ").strip().upper()

print(f"This script calculates the volume weighted EMA prices and variance from streaming real-time stock prices for {symbol}\n")


# --------- Load the initial stock prices --------

print("Initializing the EMA prices\n")
# Get the latest trade price and size
request_params = StockLatestTradeRequest(symbol_or_symbols=symbol, feed=data_feed)
last_trade = hist_client.get_stock_latest_trade(request_params)
# Get the latest trade price and size
last_trade = last_trade[symbol]
# symbol = last_trade.symbol
tzone = ZoneInfo("America/New_York")
time_stamp = last_trade.timestamp.astimezone(tzone).replace(microsecond=0)
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
date_today = time_now.strftime("%Y-%m-%d")
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

# Threshold for spike detection - the number of standard deviations
spike_threshold = 10
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
min_size = 1
num_bars_max = 1000  # Maximum number of bars to keep in the bar frame

# The initial EMA price is the trade price
price_ema = new_price
# The initial EMA volume is the trade size
volume_ema = trade_size
# The initial EMA price-volume is the product of the trade price and size
price_emav = new_price * trade_size
# The initial price variance is the squared difference between the high and low prices of the latest bar
# Set a minimum variance because sometimes in the morning the high and low prices are the same
price_var_min = 0.0001 # Minimum price variance to avoid division by zero
# price_var = max((bar_prices["high"] - bar_prices["low"]) ** 2, price_var_min)
price_var = price_var_min
price_varv = price_var * trade_size  # The initial price variance is the product of the price variance and trade size
price_vol = sqrt(price_var) # The price volatility is the square root of the price variance
# Number of standard deviations for the Bollinger Bands
bollinger_width = 1.0


# Combine the file names into a dictionary
file_names = {
    "data_file": data_file,
    "error_file": error_file,
    "plot_file": plot_file,
    "plot_title": f"{symbol} EMA Prices and Bollinger Bands with α = {alpha_param} / {date_today}",
}


# Combine the control variables into a dictionary
control_params = {
    "num_ticks": num_ticks,
    "num_shares_traded": num_shares_traded,
    "num_shares_max": num_shares_max,
    "num_bars_max": num_bars_max,
    "min_size": min_size,
    "bollinger_width": bollinger_width,
    "price_var_min": price_var_min,
    "spike_threshold": spike_threshold,
    "prev_spike": prev_spike,
    "price_prev": price_prev,
}



# Initialize the current bar with the latest trade price and size
current_second = last_trade.timestamp.astimezone(tzone).replace(microsecond=0)
current_bar = {
    "bar_start_time": current_second,
    "open": new_price,
    "high": new_price,
    "low": new_price,
    "close": new_price,
    "price_ema": new_price,
    "vwap": trade_size * new_price,
    "volume": trade_size,
    "price_var": price_var_min,
    "tick_count": 1
}


# Create a bar frame to store the bar prices
price_dict = {
    "timestamp": current_second.strftime("%Y-%m-%d %H:%M:%S"),
    "symbol": symbol,
    "open": new_price,
    "high": new_price,
    "low": new_price,
    "close": new_price,
    "vwap": trade_size * new_price,
    "volume": trade_size,
    "ema_price": new_price,
    "volatility": sqrt(price_var_min),
    "num_ticks": 1,
}
bar_frame = pd.DataFrame([price_dict])


# --------- Create the utility functions --------

# Plot function to plot the EMA price and Bollinger Bands
def plot_ema(bar_frame, control_params, file_names):
    
    # Convert the timestamp to datetime
    bar_frame["timestamp"] = pd.to_datetime(bar_frame["timestamp"])
    # Add upper and lower Bollinger Bands to the price frame
    bollinger_width = control_params["bollinger_width"]
    bar_frame["upper_band"] = bar_frame["ema_price"] + bollinger_width * bar_frame["volatility"]
    bar_frame["lower_band"] = bar_frame["ema_price"] - bollinger_width * bar_frame["volatility"]
    
    # Plot the EMA price and the Bollinger Bands
    plt.figure(figsize=(20, 12))
    plt.plot(bar_frame["timestamp"], bar_frame["close"], label="Price", color="blue")
    plt.plot(bar_frame["timestamp"], bar_frame["ema_price"], label="EMA Price", color="red")
    plt.plot(bar_frame["timestamp"], bar_frame["upper_band"], label=f"Upper + {bollinger_width} STDV", color="orange", linestyle='--')
    plt.plot(bar_frame["timestamp"], bar_frame["lower_band"], label=f"Lower - {bollinger_width} STDV", color="orange", linestyle='--')
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
# End of function plot_ema



# Aggregate 1-second bars and calculate the EMA price and variance
def calc_bar(new_price, trade_size, time_stamp, bar_frame):

    global control_params, current_bar
    
    # Initialize or update current bar
    if (time_stamp == current_bar["bar_start_time"]):
       # Update the current bar with the new tick price

        # Update the EMA and the price variance using the new price
        price_ema = current_bar["price_ema"]
        price_ema = alpha_param * price_ema + alpha1 * new_price
        price_var = current_bar["price_var"]
        price_var = alpha_squared * price_var + alpha2 * (new_price - price_ema) ** 2
        price_var = max(price_var, price_var_min)

        # Update the current_bar
        current_bar["high"] = max(current_bar["high"], new_price)
        current_bar["low"] = min(current_bar["low"], new_price)
        current_bar["close"] = new_price
        current_bar["price_ema"] = price_ema
        current_bar["vwap"] += trade_size * new_price
        current_bar["volume"] += trade_size
        current_bar["price_var"] = price_var
        current_bar["tick_count"] += 1

    else:
        # Process the completed bar
        
        price_ema = current_bar["price_ema"]
        price_var = current_bar["price_var"]
        # Save bar data to CSV
        price_dict = {
            "timestamp": time_stamp.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "open": current_bar["open"],
            "high": current_bar["high"], 
            "low": current_bar["low"],
            "close": current_bar["close"],
            "vwap": current_bar["vwap"] / current_bar["volume"] if current_bar["volume"] > 0 else 0,
            "volume": current_bar["volume"],
            "ema_price": price_ema,
            "volatility": sqrt(price_var),
            "num_ticks": current_bar["tick_count"],
        }
        single_frame = pd.DataFrame([price_dict])
        single_frame.to_csv(data_file, mode="a", header=not os.path.exists(data_file), index=False)
        bar_frame = pd.concat([bar_frame, single_frame], ignore_index=True)
        
        # Print the completed bar data - print in single line with two significant digits
        print(single_frame)
        # price_dict = {k: f"{v:.2f}" if isinstance(v, (int, float)) else v for k, v in price_dict.items()}
        # print(f"Bar prices: {price_dict}")
        # print(", ".join([f"{key}: {value}" for key, value in price_dict.items()]))

        # Start new bar
        current_bar = {
            "bar_start_time": time_stamp,
            "open": new_price,
            "high": new_price,
            "low": new_price,
            "close": new_price,
            "price_ema": price_ema,
            "vwap": trade_size * new_price,
            "volume": trade_size,
            "price_var": price_var,
            "tick_count": 1
        }

    return bar_frame

# End of function calc_bar


# --------- Create the callback function --------

print("The live price bars:\n")

# The callback function is called after each new trade price arrives
async def handle_prices(last_trade):

    trade_size = last_trade.size

    # Check if the trade size is above the minimum size
    if trade_size >= min_size:
        # Get the latest trade price and size
        # last_trade = last_trade[symbol] # Uncomment if last_trade is a dict for multiple symbols
        symbol = last_trade.symbol
        time_stamp = last_trade.timestamp.astimezone(tzone).replace(microsecond=0)
        time_string = time_stamp.strftime("%Y-%m-%d %H:%M:%S")
        new_price = last_trade.price

        # Get the spike detection parameters
        global control_params, bar_frame
        prev_spike = control_params["prev_spike"]
        spike_threshold = control_params["spike_threshold"]
        price_prev = control_params["price_prev"]
        price_vol = sqrt(current_bar["price_var"])
        # Check if an isolated price spike was detected
        price_spike = abs(new_price - price_prev) > (spike_threshold * price_vol)
        if price_spike and not prev_spike:
            # A price spike was detected, print a message
            print(f"{time_string} {symbol} Price spike detected: {new_price} (previous price: {price_prev})")
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
            bar_frame = calc_bar(new_price, trade_size, time_stamp, bar_frame)
            # Increment the number of ticks processed
            control_params["num_ticks"] += 1
            # Increment the number of shares traded
            control_params["num_shares_traded"] += trade_size
            # Check if time to plot
            if control_params["num_shares_traded"] > control_params["num_shares_max"]:
                # Keep only the last num_bars_max bars to limit the memory usage
                if len(bar_frame) > num_bars_max:
                    bar_frame = bar_frame.tail(num_bars_max).reset_index(drop=True)
                control_params["num_shares_traded"] = 0
                plot_ema(bar_frame, control_params, file_names)

# End of callback function handle_prices


# --------- Run the websocket stream --------

# Subscribe to quote or trade updates
# stream_client.subscribe_quotes(handle_quote, symbol)
stream_client.subscribe_trades(handle_prices, symbol)

# Subscribe to OHLCV bar updates and pass them to the callback function
# stream_client.subscribe_bars(handle_prices, symbol)

# Run the stream with error handling and auto-restart
try:
    stream_client.run()
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
        stream_client.stop()
    except:
        pass
    sys.exit(0)

# Set up signal handler for Ctrl-C
print("Press Ctrl-C to stop the stream... \n")
signal.signal(signal.SIGINT, signal_handler)


