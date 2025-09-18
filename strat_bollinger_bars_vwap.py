### Strategy trades a single stock using the streaming real-time stock price bars from the Alpaca API.
# The strategy is based on the z-score, equal to the difference between the stock's closing price minus its Moving Average Price (EMA), divided by the volatility.
# The proxy for the EMA is the 1-minute VWAP from Alpaca.
# 
# The strategy uses streaming bar prices and streaming confirms via the Alpaca websocket API.
# 
# The strategy uses the Bollinger Bands concept, where the z-score indicates how far the price is from the EMA.
# If the z-score is between -1 and 1, then it does not trade.
# If the z-score is below -1, then it buys the stock.
# If the z-score is above 1, then it sells the stock.
# It submits a limit or market orders when the z-score is above 1 or below -1.

# You can submit a trade order by running this script in the terminal:
# python3 strat_bollinger_bars_vwap.py symbol, type, num_shares, delta
#
# The delta is the adjustment to the limit price, compared to the ask or bid price.
# For example, if the ask price is $100, and the delta is $0.5,
# the limit price will be set to $99.5 for a buy order, or $100.5 for a sell order.
# 
# Example:
# python3 strat_bollinger_bars_vwap.py SPY limit 1 0.5

# This is only an illustration how to use the streaming real-time data, using the Alpaca websocket. 
# This is only for illustration purposes, and not a real trading strategy.



import os
import sys
import asyncio
import signal
import time
from datetime import datetime
from zoneinfo import ZoneInfo
import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.stream import TradingStream
from alpaca.data.enums import DataFeed
from alpaca.data.live.stock import StockDataStream
from dotenv import load_dotenv
# sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import convert_to_nytzone
from AlpacaSDK import AlpacaSDK


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
ALPACA_TRADE_KEY = os.getenv("ALPACA_TRADE_KEY")
ALPACA_TRADE_SECRET = os.getenv("ALPACA_TRADE_SECRET")

# Create the SDK data client for live stock prices
# Create AlpacaSDK instance and initialize clients
alpaca_sdk = AlpacaSDK()
alpaca_sdk.create_trade_clients()

data_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=DataFeed.SIP)
# Get clients from SDK
trading_client = alpaca_sdk.get_trading_client()
confirm_stream = alpaca_sdk.get_confirm_stream()


# --------- Get the trading parameters from the command line arguments --------

# Get the symbol, type, side, shares_per_trade, and delta from the command line arguments
if len(sys.argv) > 4:
    symbol = sys.argv[1].strip().upper()
    type = sys.argv[2].strip().lower()
    # side_input = sys.argv[3].strip().lower()
    shares_per_trade = float(sys.argv[3])
    delta = float(sys.argv[4])
else:
    # If not provided, prompt the user for input
    symbol = input("Enter symbol: ").strip().upper()
    type = input("Enter order type (market/limit): ").strip().lower()
    # side_input = input("Enter side (buy/sell): ").strip().lower()
    shares_input = input("Enter number of shares to trade (default 1): ").strip()
    shares_per_trade = float(shares_input) if shares_input else 1
    delta_input = input("Enter price adjustment (default 0.5): ").strip()
    delta = float(delta_input) if delta_input else 0.5

print(f"Trading parameters: symbol={symbol}, type={type}, shares_per_trade={shares_per_trade}, limit delta={delta}\n")


# --------- Specify the strategy parameters --------

# symbol = "SPY"
# Specify the strategy name
strategy_name = "StratBoll001"
# Specify the trading parameters
# shares_per_trade = 1  # Number of shares to trade per each order
# type = "market"
# type = "limit"
# side = OrderSide.BUY  # Set to BUY or SELL as needed
# Adjustment to the limit price to make it below the ask or above the bid
# delta = 0.1  # The delta price adjustment for the limit order
vol_floor = 0.05  # The volatility floor
price_vol = vol_floor  # The price volatility, used to calculate the z-score

# Initialize the strategy state variables
position_shares = 0  # The number of shares currently owned
position_broker = None  # The number of shares owned according to the broker
shares_available = 0  # The number of available shares to trade, according to the broker
pnl_real = 0  # The realized PnL of the strategy
pnl_unreal = 0  # The unrealized PnL of the strategy
# Initialize the order response variable
order_response = None
order_id = None  # Initialize order_id variable
# Initialize last limit price tracking for staggered orders
last_limit_buy_price = None  # Track the last buy limit price submitted
last_limit_sell_price = None  # Track the last sell limit price submitted
# Initialize list to track pending order IDs
pending_order_ids = []  # List to track all pending limit order IDs
# Initialize persistent EMA and variance state variables
ema_price = None  # Persistent EMA price between calls
price_var = None  # Persistent price variance between calls
alpha1 = None  # Persistent alpha coefficient (1 - alpha)
alpha_squared = None  # Persistent alpha squared
alpha2 = None  # Persistent alpha2 coefficient for variance calculation


# --------- Define persistent Z-score calculation function --------

def calc_zscore(price, alpha):
    """
    Calculate the z-score of the current price relative to the EMA price with persistent state.
    
    Args:
        price (float): Current price to incorporate into EMA
        alpha (float): Decay parameter (0 < alpha <= 1)
                      Higher alpha = more weight to recent prices
                      Lower alpha = more smoothing (more weight to past prices)
    
    Returns:
        float: Z-score of current price relative to EMA
    """
    global ema_price, price_var, alpha1, alpha_squared, alpha2
    
    # Initialize persistent coefficients on first call
    if alpha1 is None:
        alpha1 = 1 - alpha
        alpha_squared = alpha * alpha
        alpha2 = alpha * alpha1  # alpha * (1 - alpha)
        print(f"Initialized persistent coefficients: alpha={alpha}, alpha1={alpha1}, alpha_squared={alpha_squared}, alpha2={alpha2}")
    
    if ema_price is None:
        # Initialize EMA and variance with first price
        ema_price = price
        price_var = vol_floor * vol_floor  # Initialize variance with vol_floor squared
        print(f"Initialized EMA with first price: {ema_price:.2f}, initial variance: {price_var:.6f}")
        zscore = 0.0  # First price has zero z-score
    else:
        # Update EMA: EMA = alpha * previous_EMA + (1 - alpha) * current_price
        ema_price = alpha * ema_price + alpha1 * price
        
        # Calculate price deviation from EMA
        price_deviation = price - ema_price
        
        # Update variance using exponential smoothing
        # Var = alpha^2 * previous_Var + alpha * (1 - alpha) * (price - EMA)^2
        price_var = alpha_squared * price_var + alpha2 * (price_deviation * price_deviation)
        
        # Ensure variance doesn't fall below vol_floor squared
        price_var = max(price_var, vol_floor * vol_floor)
        
        # Calculate z-score using current deviation and smoothed volatility
        price_vol_current = (price_var ** 0.5)  # Standard deviation from variance
        zscore = price_deviation / price_vol_current
    
    return zscore, ema_price, price_vol_current if 'price_vol_current' in locals() else vol_floor

# End of calc_zscore function


# --------- Create the file names --------

# Create file names with today's NY date
timezone = ZoneInfo("America/New_York")
time_now = datetime.now(timezone)
date_short = time_now.strftime("%Y%m%d")
dir_name = os.getenv("DATA_DIR_NAME")
# Create file name for the state variables
state_file = f"{dir_name}" + "state_" + f"{strategy_name}_{symbol}_{date_short}.csv"
# Create file name for the submitted trade orders
submits_file = f"{dir_name}" + "submits_" + f"{strategy_name}_{symbol}_{date_short}.csv"
# Create file name for the filled trade orders
fills_file = f"{dir_name}" + "fills_" + f"{strategy_name}_{symbol}_{date_short}.csv"
# Create file name for the canceled trade orders
canceled_file = f"{dir_name}" + "canceled_" + f"{strategy_name}_{symbol}_{date_short}.csv"
# Create file name for the websocket errors
error_file = f"{dir_name}" + "error_" + f"{strategy_name}_{symbol}_{date_short}.csv"



# --------- Define the callback trading function --------
# The trading function receives the price bars and submits the trade orders

async def trade_bars(bar):

    global order_response, order_id, position_shares, shares_available, position_broker, last_limit_buy_price, last_limit_sell_price, pending_order_ids
    # print(f"Bar price: {bar}")
    # print(f"Symbol: {bar.symbol}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}, Trade_count: {bar.trade_count}, VWAP: {bar.vwap}")
    price_last = bar.close
    timestamp = bar.timestamp.astimezone(timezone)
    date_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    # Calculate z-score, EMA, and current volatility using persistent function
    zscore, price_ema, price_vol_current = calc_zscore(price_last, alpha)
    
    print(f"Time: {date_time}, Symbol: {bar.symbol}, Price: {price_last}, EMA: {price_ema:.2f}, Vol: {price_vol_current:.4f}, Z-score: {zscore:.2f}, position: {position_shares}")

    # Get the current position from the broker and the number of available shares to trade for the symbol
    position_broker = alpaca_sdk.get_position(symbol)
    if position_broker is None:
        # There is no open position - set the available shares to the number of shares traded per each order
        shares_available = shares_per_trade
        # position_shares = 0
    else:
        # Get the number of available shares to trade from the broker
        shares_available = float(position_broker.qty_available)
        position_broker = float(position_broker.qty)

    # Print additional z-score information
    print(f"Z-score: {round(zscore, 2)}, Last price: {round(price_last, 2)}, EMA: {round(price_ema, 2)}, Vol: {round(price_vol_current, 4)} - no trade executed for {symbol}")
    # Initialize the side variable
    side = None

    # If the absolute value of the z-score is greater than 1, then submit a trade order
    if abs(zscore) > (1): # If the price is significantly different from the EMA price

        # Check if there are enough available shares
        if (shares_available == 0):
            print(f"No shares available to trade for {symbol}: available={shares_available} but requested {shares_per_trade} shares.")

        elif (zscore < (-1)) and (shares_available < 0):
            # Submit a buy order if the price is significantly below the EMA price
            side = OrderSide.BUY
            # The number of shares available is negative, because of a short position
            shares_available = min(abs(shares_available), shares_per_trade)
            # Limit price is equal to the last buy price minus the delta adjustment
            limit_price = round(min(price_last, last_limit_buy_price) - delta, 2)
            last_limit_buy_price = limit_price

        elif (zscore < (-1)) and (shares_available > 0):
            # Submit a buy order if the price is significantly below the EMA price
            side = OrderSide.BUY
            # The number of shares available is positive, because of a long position
            # The number of shares available is not limited by the broker
            shares_available = shares_per_trade
            # Limit price is equal to the last buy price minus the delta adjustment
            limit_price = round(min(price_last, last_limit_buy_price) - delta, 2)
            last_limit_buy_price = limit_price

        elif (zscore > 1) and (shares_available > 0):
            # Submit a sell order if the price is significantly above the EMA price
            side = OrderSide.SELL
            # The number of shares sell is positive, because of a long position
            shares_available = min(abs(shares_available), shares_per_trade)
            # Limit price is equal to the last sell price plus the delta adjustment
            limit_price = round(max(price_last, last_limit_sell_price) + delta, 2)
            last_limit_sell_price = limit_price

        elif (zscore > 1) and (shares_available < 0):
            # Submit a sell order if the price is significantly above the EMA price
            side = OrderSide.SELL
            # The number of shares sell is negative, because of a short position
            # The number of shares sell is not limited by the broker
            shares_available = shares_per_trade
            # Limit price is equal to the last sell price plus the delta adjustment
            limit_price = round(max(price_last, last_limit_sell_price) + delta, 2)
            last_limit_sell_price = limit_price

        # Submit the trade order if there are available shares
        if side is not None:

            print(f"Z-score: {zscore}, Side: {side}, Limit price: {limit_price}, Shares available: {shares_available}")
            order_response = alpaca_sdk.submit_order(symbol, shares_available, side, type, limit_price, submits_file, error_file)

            # If the order submission failed, cancel all the open limit orders for the symbol
            if order_response is None:
                print(f"Trade order submission failed for {symbol}")
                print(f"Cancelling all open orders for {symbol}")
                alpaca_sdk.cancel_orders(symbol, None, canceled_file)
                # Submit the trade order again
                order_response = alpaca_sdk.submit_order(symbol, shares_available, side, type, limit_price, submits_file, error_file)
            
            # Add the order ID to the pending orders list
            if order_response is not None:
                order_id = str(order_response.id)
                pending_order_ids.append(order_id)
                print(f"Added order ID {order_id} to pending list. Total pending orders: {len(pending_order_ids)}")
            else:
                print("Failed to submit order after retry")
    else:
        side = None # No trade executed, side remains None

    # Save the strategy state to the CSV file
    state_data = {
        "date_time": date_time,
        "symbol": bar.symbol,
        "price": bar.close,
        "volatility": (bar.high - bar.low),
        "zscore": zscore,
        "order": side,
        "position_shares": position_shares,
        "pnlReal": 0,
        "pnlUnreal": 0,
    }
    state_data = pd.DataFrame([state_data])
    state_data.to_csv(state_file, mode="a", header=not os.path.exists(state_file), index=False)
    print("Done\n")

# End of callback function trade_bars



# --------- Define the callback function to handle the trade updates and trade confirms --------

async def handle_trade_update(event_data):

    global position_shares, pending_order_ids
    filled_order_id = str(event_data.order.id)
    
    # Check if this order ID is in our pending list
    if filled_order_id in pending_order_ids:
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
        qty_filled = float(orderinfo["qty"])
        price = orderinfo.get("filled_avg_price", 0)
        # event_dict = event_dict | orderinfo  # Combine dictionaries
        event_dict.update(orderinfo)  # This adds order fields to event_dict while preserving the "order" key
        time_now = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S")
        # Process the event data based on the event type
        if (event_name == "fill") or (event_name == "partial_fill"):
            print(f"Order {filled_order_id} filled at {time_now} at price {price}")
            # Unpack the event_data into a dictionary
            # Process the fill data FIRST before stopping
            print(f"{time_stamp} Filled {type} {side} order for {qty_filled} shares of {symbol} at {price}")
            # Update position_shares after the trade is filled
            if side == "buy":
                position_shares += qty_filled
            elif side == "sell":
                position_shares -= qty_filled

            # Remove the filled order ID from pending list
            pending_order_ids.remove(filled_order_id)
            print(f"Removed order ID {filled_order_id} from pending list. Remaining pending orders: {len(pending_order_ids)}")
            
            position_fill = event_dict.get("position_qty", 0)
            print(f"Position from broker after the fill: {position_fill} shares of {symbol}")
            # Save fill data to CSV
            event_frame = pd.DataFrame([event_dict])
            event_frame.to_csv(fills_file, mode="a", header=not os.path.exists(fills_file), index=False)
            print(f"Fill appended to {fills_file}")

            # Only stop the stream if no more pending orders (optional - you may want to keep running)
            if len(pending_order_ids) == 0:
                print("No more pending orders. Stopping WebSocket stream...")
                await confirm_stream.stop_ws()
            else:
                print(f"Still waiting for {len(pending_order_ids)} pending orders to fill...")

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
            # print(f"Cancel event: {event_dict}")
            print(f"Order {filled_order_id} canceled at {time_now}")
            # Remove the canceled order ID from pending list
            pending_order_ids.remove(filled_order_id)
            print(f"Removed canceled order ID {filled_order_id} from pending list. Remaining pending orders: {len(pending_order_ids)}")
            # Append to CSV (write header only if file does not exist)
            event_frame = pd.DataFrame([event_dict])
            event_frame.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
            print(f"Canceled order appended to {canceled_file}")
            # await confirm_stream.stop_ws()  # Stop on cancel too

        elif event_name == "replaced":
            print(f"Replace event: {event_dict}")
        else:
            print(f"Unknown event: {event_name}")
        print(f"Finished processing the {event_name} update for order {filled_order_id} at {time_now}")
    else:
        # Order ID not in pending list - ignore or log
        print(f"Received update for order {filled_order_id} which is not in pending list")

# End of handle_trade_update function



# --------- Run the WebSocket to handle trade updates and confirmations, and exceptions and Ctrl-C interrupt --------
# --------- Run the data WebSocket stream --------

# Define the main function to run the WebSockets
async def main():

    try:
        # Subscribe to the price bar updates and pass them to the callback function
        data_client.subscribe_bars(trade_bars, symbol)
        # Subscribe to the trade updates and confirms, and handle them using handle_trade_update()
        confirm_stream.subscribe_trade_updates(handle_trade_update)
        # Run both WebSocket streams concurrently
        print("\nStarting the data WebSocket connection...")
        print("\nStarting the trade updates and confirmations WebSocket connection...")
        await asyncio.gather(
            data_client._run_forever(),
            confirm_stream._run_forever()
        )
    except Exception as e:
        pass  # Handle exceptions here if needed
        # print(f"WebSocket error: {e}")
    finally:
        print("\nClosing the trade updates and confirmations WebSocket connection...")
        try:
            await data_client.close()
            await confirm_stream.close()
        except:
            pass  # Ignore errors when closing


# Check whether the script is being run directly or is imported as a module
if __name__ == "__main__":
    # Perform simplified event loop handling
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "Cannot be called from a running event loop" in str(e):
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

