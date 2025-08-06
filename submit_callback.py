### Submits a trade order using the Alpaca SDK, and waits for a confirmation via the WebSocket.
# It checks for the available shares to trade, and submits a market or limit order only for the amount of shares that are available.
# It then listens for trade updates and fills via the WebSocket.

# You can submit a trade order by running this script in the terminal:
# python3 submit_callback.py symbol, type, side, num_shares, delta
# 
# The delta is the adjustment to the limit price, compared to the ask or bid price.
# For example, if the ask price is $100, and the delta is $0.5,
# the limit price will be set to $99.5 for a buy order, or $100.5 for a sell order.
# 
# Example:
# python3 submit_callback.py SPY limit buy 1 0.5


import os
import sys
import io
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.stream import TradingStream
from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockQuotesRequest, StockLatestQuoteRequest, StockBarsRequest
from alpaca.data.enums import DataFeed
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from dotenv import load_dotenv
from utils import convert_to_nytzone, get_position



# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

# Create the SDK trading client
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)
# Create the SDK confirm trading update client
confirm_stream = TradingStream(TRADE_KEY, TRADE_SECRET)


# --------- Create the utility functions --------



# --------- Get the trading parameters from the command line arguments --------

# Get the symbol, type, side, shares_per_trade, and delta from the command line arguments
if len(sys.argv) > 5:
    symbol = sys.argv[1].strip().upper()
    type = sys.argv[2].strip().lower()
    side_input = sys.argv[3].strip().lower()
    shares_per_trade = float(sys.argv[4])
    delta = float(sys.argv[5])
else:
    # If not provided, prompt the user for input
    symbol = input("Enter symbol: ").strip().upper()
    type = input("Enter order type (market/limit): ").strip().lower()
    side_input = input("Enter side (buy/sell): ").strip().lower()
    shares_input = input("Enter number of shares to trade (default 1): ").strip()
    shares_per_trade = float(shares_input) if shares_input else 1
    delta_input = input("Enter price adjustment (default 0.5): ").strip()
    delta = float(delta_input) if delta_input else 0.5

# Convert side_input to OrderSide
if side_input == "buy":
    side = OrderSide.BUY
elif side_input == "sell":
    side = OrderSide.SELL
else:
    raise ValueError("Side must be 'buy' or 'sell'")

print(f"Trading parameters: symbol={symbol}, type={type}, side={side}, shares_per_trade={shares_per_trade}, limit delta={delta}\n")

# Get the trading parameters
# symbol = "SPY"
# shares_per_trade = 1  # Number of shares
# type = "market"
# type = "limit"
# side = OrderSide.BUY  # Set to BUY or SELL as needed
# side = OrderSide.SELL
# Adjustment to the limit price to make it below the ask or above the bid
# delta = 0.1


# --------- Check if there are available shares to trade for the symbol --------

position_broker = 0  # The number of shares owned according to the broker
# Get the current position from the broker and the number of available shares to trade for the symbol
position_broker = get_position(trading_client, symbol)
if position_broker is None:
    # There is no open position - set the available shares to the number of shares traded per each order
    shares_available = shares_per_trade
    position_broker = 0
else:
    # Get the number of available shares to trade from the broker
    shares_available = float(position_broker.qty_available)
    position_broker = float(position_broker.qty)


print(f"The shares available to trade for {symbol}: available={shares_available} but requested {shares_per_trade} shares.")
# Calculate the shares available to trade based on the side of the order
if (side == OrderSide.BUY) and (shares_available < 0):
    # The number of shares available is negative, because of a short position
    shares_available = min(abs(shares_available), shares_per_trade)
elif (side == OrderSide.BUY) and (shares_available > 0):
    # The number of shares available is positive, because of a long position
    # The number of shares available is not limited by the broker
    shares_available = shares_per_trade
elif (side == OrderSide.SELL) and (shares_available > 0):
    # The number of shares sell is positive, because of a long position
    shares_available = min(abs(shares_available), shares_per_trade)
elif (side == OrderSide.SELL) and (shares_available < 0):
    # The number of shares sell is negative, because of a short position
    # The number of shares sell is not limited by the broker
    shares_available = shares_per_trade


if (shares_available == 0):
    print(f"No shares available to trade for {symbol}: available={shares_available} but requested {shares_per_trade} shares.")
    exit(1)  # Exit if no shares are available


# --------- Create the file names --------

# Define the file names for the submitted trade orders and the fills
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
date_today = time_now.strftime("%Y-%m-%d")
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("data_dir_name")
submits_file = f"{dir_name}submits_{date_short}.csv"
fills_file = f"{dir_name}fills_{symbol}_{date_short}.csv"
canceled_file = f"{dir_name}canceled_orders_" + date_short + ".csv"
# Create file name for the websocket errors
error_file = f"{dir_name}error_{symbol}_{date_short}.csv"
print(f"The submits file is: {submits_file}")
print(f"The fills file is: {fills_file}")
print(f"The canceled file is: {canceled_file}")
print(f"The error file is: {error_file}\n")


# --------- Specify the order parameters based on the order type --------

if type == "market":
    # Submit market order
    order_params = MarketOrderRequest(
        symbol = symbol,
        qty = shares_available,
        side = side,
        type = type,
        time_in_force = TimeInForce.DAY
    ) # end order_params
    print(f"Submitting a {type} {side} order for {shares_available} shares of {symbol}")
elif type == "limit":
    # Get the limit order price based on the latest bid/ask prices
    # Create the SDK data client for live and historical stock data
    data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)
    # Create the request parameters for live stock prices - SIP for comprehensive data, or IEX for free data.
    quote_params = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.SIP)
    # Get the latest bid/ask price quotes - as a dictionary
    latest_quotes = data_client.get_stock_latest_quote(quote_params)
    price_quotes = latest_quotes[symbol]
    ask_price = price_quotes.ask_price
    bid_price = price_quotes.bid_price
    print(f"Latest quotes for {symbol}: Ask = {price_quotes.ask_price}, Bid = {price_quotes.bid_price}")
    if side == OrderSide.BUY:
        # Submit a limit order to buy at the current ask price minus a small adjustment
        limit_price = round(ask_price - delta, 2)
    elif side == OrderSide.SELL:
        # Submit a limit order to sell at the current bid price plus a small adjustment
        limit_price = round(bid_price + delta, 2)
    # Define the limit order parameters
    order_params = LimitOrderRequest(
        symbol = symbol,
        qty = shares_available,
        side = side,
        type = type,
        limit_price = limit_price,
        extended_hours = True,
        time_in_force = TimeInForce.DAY
    ) # end order_params
    print(f"Submitting a {type} {side} order for {shares_available} shares of {symbol} at {limit_price}")



# --------- Submit the trade order --------

order_response = None  # Initialize response variable
order_id = None  # Initialize order_id variable

try:
    order_response = trading_client.submit_order(order_data = order_params)
    # Remember the order ID to get the order status later
    order_id = str(order_response.id)
    # print(f"Submitted limit order {order_id} for {shares_available} {symbol} at {limit_price}")
    print(f"Submitted {side} order for {shares_available} shares of {symbol} with the order-id: {order_id}")
    # Append the submitted orders to a CSV file
    order_frame = order_response.model_dump()  # or order_response._raw for some SDKs
    order_frame = convert_to_nytzone(order_frame)
    order_frame = pd.DataFrame([order_frame])
    # Append to CSV (write header only if file does not exist)
    order_frame.to_csv(submits_file, mode="a", header=not os.path.exists(submits_file), index=False)
    print(f"Order appended to {submits_file}")
except Exception as e:
    # Convert error to string and save to CSV
    error_msg = pd.DataFrame([{"timestamp: ": time_now, "symbol: ": symbol, "side: ": side, "error: ": str(e)}])
    error_msg = convert_to_nytzone(error_msg)
    error_msg.to_csv(error_file, mode="a", header=not os.path.exists(error_file), index=False)
    print(f"Trade order rejected: {e}")
    exit(1)  # Exit if order submission fails



# --------- Define the callback function to handle the trade updates and trade confirms --------

async def handle_trade_update(event_data):
    if order_response and str(event_data.order.id) == order_id:
        event_dict = event_data.model_dump()  # Convert to dictionary
        event_dict = convert_to_nytzone(event_dict)
        event_name = str(event_dict["event"]).lower()  # Get the event name
        time_stamp = event_dict["timestamp"]
        orderinfo = event_dict["order"]
        # Remove the "order" key from the event_dict
        event_dict.pop("order", None)
        symbol = orderinfo["symbol"]
        type = orderinfo["order_type"]
        side = orderinfo["side"]
        qty_filled = orderinfo["qty"]
        price = orderinfo.get("filled_avg_price", 0)
        # event_dict = event_dict | orderinfo  # Combine dictionaries
        event_dict.update(orderinfo)  # This adds order fields to event_dict while preserving the "order" key
        time_now = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")
        # Process the event data based on the event type
        if (event_name == "fill") or (event_name == "partial_fill"):
            print(f"Order {order_id} filled at {time_now} at price {price}")
            # Unpack the event_data into a dictionary
            # Process the fill data FIRST before stopping
            print(f"{time_stamp} Filled {type} {side} order for {qty_filled} shares of {symbol} at {price}")
            position_fill = event_dict.get("position_qty", 0)
            print(f"Position from broker after the fill: {position_fill} shares of {symbol}")
            # Append to CSV (write header only if file does not exist)
            event_frame = pd.DataFrame([event_dict])
            event_frame.to_csv(fills_file, mode="a", header=not os.path.exists(fills_file), index=False)
            print(f"Fill appended to {fills_file}")
            # STOP the stream AFTER processing the fill
            print("Stopping WebSocket stream after fill...")
            await confirm_stream.stop_ws()
        elif (event_name == "pending_new") or (event_name == "new") or (event_name == "accepted"):
            # Do nothing on pending_new or new events
            # pass # Will implement later
            print(f"Event {event_name} received for order {order_id} at {time_now}")
            # print("New order event received")
            # event_frame = pd.DataFrame([event_dict])
            # event_frame.to_csv(submits_file, mode="a", header=not os.path.exists(submits_file), index=False)
            # print(f"{time_stamp} New {type} {side} order for {qty_filled} shares of {symbol}")
            # print(f"New trade appended to {submits_file}")
        elif event_name == "canceled":
            print(f"Order {order_id} canceled at {time_now}")
            # Append to CSV (write header only if file does not exist)
            event_frame = pd.DataFrame([event_dict])
            event_frame.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
            print(f"Canceled order appended to {canceled_file}")
            await confirm_stream.stop_ws()  # Stop on cancel too
        elif event_name == "replaced":
            print(f"Replace event: {event_dict}")
        else:
            print(f"Unknown event: {event_name}")
        print(f"Finished processing the {event_name} update for order {order_id} at {time_now}")

# End of handle_trade_update function



# --------- Run the WebSocket to handle trade updates and confirms, and exceptions and Ctrl-C interrupt --------

# Subscribe to the trade updates and confirms, and handle them using handle_trade_update()
confirm_stream.subscribe_trade_updates(handle_trade_update)

# Define the main function to run the confirm_stream until the order is filled
async def main():
    try:
        print("Starting WebSocket connection...")
        await confirm_stream._run_forever()
    except Exception as e:
        pass  # Handle exceptions here if needed
        # print(f"WebSocket error: {e}")
    finally:
        print("\nClosing WebSocket connection...")
        try:
            await confirm_stream.close()
        except:
            pass  # Ignore errors when closing


# Check whether the script is being run directly or is imported as a module
if __name__ == "__main__":
    if order_response:  # Only run if order was successfully submitted
        print("Starting WebSocket stream to listen for trade updates...")
        
        # Simplified event loop handling
        try:
            asyncio.run(main())
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                print("Running in existing event loop/Users/jerzy/Develop/Python/.environment...")
                # Create a task in the existing loop
                loop = asyncio.get_event_loop()
                task = loop.create_task(main())
                # You might need to await this task manually in Jupyter
            else:
                # Suppress traceback for other RuntimeErrors
                print(f"Runtime error: {str(e)}")
        except KeyboardInterrupt:
            print("\nProgram interrupted by user")
        except Exception as e:
            # Suppress full traceback, just show error message
            print(f"Error occurred: {str(e)}")
    else:
        print("No order was submitted, skipping WebSocket stream.")


