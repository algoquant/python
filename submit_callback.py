### Submits a trade order using the Alpaca SDK, and waits for a confirmation via the WebSocket.
# It checks for the available shares to trade, and submits a market or limit order only for the amount of shares that are available.
# It then listens for trade updates and fills via the WebSocket.

# You can submit a trade order by running this script in the terminal:
# python3 submit_callback.py symbol, type, side, num_shares, price_adjustment
# 
# The price_adjustment is the adjustment to the limit price, compared to the ask or bid price.
# For example, if the ask price is $100, and the price_adjustment is $0.5,
# the limit price will be set to $99.5 for a buy order, or $100.5 for a sell order.
# 
# Example:
# python3 submit_callback.py SPY limit buy 1 0.5

import os
import sys
import io
import asyncio
from datetime import datetime
import pandas as pd
from alpaca.data.enums import DataFeed
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from AlpacaSDK import AlpacaSDK
from MachineTrader import CreateStrategy
from utils import convert_to_nytzone


# --------- Create the SDK clients --------

# Create AlpacaSDK instance and initialize clients
alpaca_sdk = AlpacaSDK()
trading_client, confirm_stream = alpaca_sdk.create_trade_clients()
data_client = alpaca_sdk.create_data_client()


# --------- Get the trading parameters from the command line arguments --------

# Get the symbol, type, side, shares_per_trade, and price_adjustment from the command line arguments
if len(sys.argv) > 5:
    symbol = sys.argv[1].strip().upper()
    type = sys.argv[2].strip().lower()
    side_input = sys.argv[3].strip().lower()
    shares_per_trade = float(sys.argv[4])
    price_adjustment = float(sys.argv[5])
else:
    # If not provided, prompt the user for input
    symbol = input("Enter symbol: ").strip().upper()
    type = input("Enter order type (market/limit): ").strip().lower()
    side_input = input("Enter side (buy/sell): ").strip().lower()
    shares_input = input("Enter number of shares to trade (default 1): ").strip()
    shares_per_trade = float(shares_input) if shares_input else 1
    price_adjustment_input = input("Enter price adjustment (default 0.5): ").strip()
    price_adjustment = float(price_adjustment_input) if price_adjustment_input else 0.5

# Convert side_input to OrderSide
if side_input == "buy":
    side = OrderSide.BUY
elif side_input == "sell":
    side = OrderSide.SELL
else:
    raise ValueError("Side must be 'buy' or 'sell'")

print(f"Trading parameters: symbol={symbol}, type={type}, side={side}, shares_per_trade={shares_per_trade}, limit price_adjustment={price_adjustment}\n")

# Get the trading parameters
# symbol = "SPY"
# shares_per_trade = 1  # Number of shares
# type = "market"
# type = "limit"
# side = OrderSide.BUY  # Set to BUY or SELL as needed
# side = OrderSide.SELL
# Adjustment to the limit price to make it below the ask or above the bid
# price_adjustment = 0.5


# --------- Check if there are available shares to trade for the symbol --------

# Get the current position from the broker and the number of available shares to trade for the symbol
position_broker = alpaca_sdk.get_position(symbol)
if position_broker is None:
    # There is no open position - set the available shares to the number of shares traded per each order
    shares_available = shares_per_trade
else:
    # Get the number of available shares to trade from the broker
    shares_available = float(position_broker.qty_available)
    position_broker = float(position_broker.qty)


if (shares_available == 0):
    print(f"No shares available to trade for {symbol}: available={shares_available} but requested {shares_per_trade} shares.")
    exit(1)  # Exit if no shares are available


print(f"The shares available to trade for {symbol}: available={shares_available} but requested {shares_per_trade} shares.")
# Calculate the shares available to trade based on the side of the order
if (side == OrderSide.BUY) and (shares_available < 0):
    # The number of shares available is negative, because of a short position
    shares_to_trade = min(abs(shares_available), shares_per_trade)
elif (side == OrderSide.BUY) and (shares_available > 0):
    # The number of shares available is positive, because of a long position
    # The number of shares available is not limited by the broker
    shares_to_trade = shares_per_trade
elif (side == OrderSide.SELL) and (shares_available > 0):
    # The number of shares sell is positive, because of a long position
    shares_to_trade = min(abs(shares_available), shares_per_trade)
elif (side == OrderSide.SELL) and (shares_available < 0):
    # The number of shares sell is negative, because of a short position
    # The number of shares sell is not limited by the broker
    shares_to_trade = shares_per_trade



# --------- Create the file names using MachineTrader --------

# Create a Strategies instance to use file creation methods
strategy_instance = CreateStrategy(symbol=symbol, strategy_name="submit_callback")
file_names = strategy_instance.create_file_names()

submits_file = file_names["submits_file"]
fills_file = file_names["fills_file"]
canceled_file = file_names["canceled_file"]
error_file = file_names["error_file"]

print(f"The submits file is: {submits_file}")
print(f"The fills file is: {fills_file}")
print(f"The canceled file is: {canceled_file}")
print(f"The error file is: {error_file}\n")


# --------- Specify the order parameters based on the order type --------

# Submit market order
if type == "market":
    order_params = MarketOrderRequest(
        symbol = symbol,
        qty = shares_to_trade,
        side = side,
        type = type,
        time_in_force = TimeInForce.DAY
    ) # end order_params
    # print(f"Submitting a {type} {side} order for {shares_to_trade} shares of {symbol}")

# Submit limit order
elif type == "limit":
    # Get the limit order price based on the latest bid/ask prices
    # Use the data_client created by create_data_client
    # Create the request parameters for live stock prices - SIP for comprehensive data, or IEX for free data.
    request_params = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.SIP)
    # Get the latest bid/ask price quotes - as a dictionary
    try:
        latest_quotes = data_client.get_stock_latest_quote(request_params)
        price_quotes = latest_quotes[symbol]
        ask_price = price_quotes.ask_price
        bid_price = price_quotes.bid_price
        print(f"Latest quotes for {symbol}: Ask = {price_quotes.ask_price}, Bid = {price_quotes.bid_price}")
    except Exception as e:
        print(f"Failed to get stock quotes for {symbol}: {e}")
        # Convert error to string and save to CSV
        time_now = datetime.now(strategy_instance.timezone)
        error_msg = pd.DataFrame([{"timestamp: ": time_now, "symbol: ": symbol, "side: ": side, "error: ": str(e)}])
        error_msg = convert_to_nytzone(error_msg)
        error_msg.to_csv(error_file, mode="a", header=not os.path.exists(error_file), index=False)
        print("Exiting due to quote data failure...")
        exit(1)
    
    if side == OrderSide.BUY:
        # Submit a limit order to buy at the current ask price minus a small adjustment
        limit_price = round(ask_price - price_adjustment, 2)
    elif side == OrderSide.SELL:
        # Submit a limit order to sell at the current bid price plus a small adjustment
        limit_price = round(bid_price + price_adjustment, 2)
    # Define the limit order parameters
    order_params = LimitOrderRequest(
        symbol = symbol,
        qty = shares_to_trade,
        side = side,
        type = type,
        limit_price = limit_price,
        extended_hours = True,
        time_in_force = TimeInForce.DAY
    ) # end order_params
    # print(f"Submitting a {type} {side} order for {shares_to_trade} shares of {symbol} at {limit_price}")



# --------- Submit the trade order --------

order_response = None  # Initialize response variable
order_id = None  # Initialize order_id variable

try:
    # Use submit_order from AlpacaSDK SDK instead of direct SDK call
    order_response = alpaca_sdk.submit_order(symbol, shares_to_trade, side, type, limit_price, submits_file, error_file)
    # Remember the order ID to get the order status later
    order_id = str(order_response.id)
    print(f"✅ Submitted {side} order for {shares_to_trade} shares of {symbol} with the order-id: {order_id}")
    print(f"📁 Order appended to {submits_file}")
except Exception as e:
    # Convert error to string and save to CSV
    time_now = datetime.now(strategy_instance.timezone)
    error_msg = pd.DataFrame([{"timestamp: ": time_now, "symbol: ": symbol, "side: ": side, "error: ": str(e)}])
    error_msg = convert_to_nytzone(error_msg)
    error_msg.to_csv(error_file, mode="a", header=not os.path.exists(error_file), index=False)
    print(f"❌ Trade order rejected: {e}")
    exit(1)  # Exit if order submission fails



# --------- Define the callback function to handle the trade updates and trade confirms --------

async def handle_trade_update(event_data):
    if (order_response is not None) and (order_id == str(event_data.order.id)):
        # Use the MachineTrader approach for consistent event handling
        event_dict = event_data.model_dump()  # Convert to dictionary
        event_dict = convert_to_nytzone(event_dict)
        event_name = str(event_dict["event"]).lower()  # Get the event name
        time_stamp = event_dict["timestamp"]
        orderinfo = event_dict["order"]
        # Remove the "order" key from the event_dict
        event_dict.pop("order", None)
        symbol = orderinfo["symbol"]
        event_dict.update(orderinfo)  # This adds order fields to event_dict
        time_now = datetime.now(strategy_instance.timezone).strftime("%Y-%m-%d %H:%M:%S")

        # Process the event data based on the event type
        if (event_name == "fill") or (event_name == "partial_fill"):
            order_type = orderinfo["order_type"]
            trade_side = orderinfo["side"]
            qty_filled = float(orderinfo["qty"])
            fill_price = float(orderinfo.get("filled_avg_price", 0))
            print(f"✅ Order {order_id} filled at {time_now} at price {fill_price}")
            print(f"💸 {time_stamp} Filled {order_type} {trade_side} order for {qty_filled} shares of {symbol} at {fill_price}")
            
            position_fill = event_dict.get("position_qty", 0)
            print(f"📊 Position from broker after the fill: {position_fill} shares of {symbol}")
            
            # Append to CSV (write header only if file does not exist)
            event_frame = pd.DataFrame([event_dict])
            event_frame.to_csv(fills_file, mode="a", header=not os.path.exists(fills_file), index=False)
            print(f"📁 Fill appended to {fills_file}")
            
            # STOP the stream AFTER processing the fill
            print("🛑 Stopping WebSocket stream after fill...")
            await confirm_stream.stop_ws()
            
        elif (event_name == "pending_new") or (event_name == "new") or (event_name == "accepted"):
            print(f"📋 Event {event_name} received for order {order_id} at {time_now}")
            
        elif event_name == "canceled":
            print(f"❌ Order {order_id} canceled at {time_now}")
            # Append to CSV (write header only if file does not exist)
            event_frame = pd.DataFrame([event_dict])
            event_frame.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
            print(f"📁 Canceled order appended to {canceled_file}")
            await confirm_stream.stop_ws()  # Stop on cancel too
            
        elif event_name == "replaced":
            print(f"🔄 Replaced event: {event_dict}")
            await confirm_stream.stop_ws()
            
        elif event_name == "expired":
            print(f"⏰ Expired event: {event_dict}")
            await confirm_stream.stop_ws()
            
        else:
            print(f"❓ Unknown event: {event_name}")
            
        print(f"✅ Finished processing the {event_name} update for order {order_id} at {time_now}")

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
    if (order_response is not None):  # Only run if order was successfully submitted
        print("Starting WebSocket stream to listen for trade updates...")
        
        # Simplified event loop handling
        try:
            asyncio.run(main())
        except RuntimeError as e:
            if "cannot be called from a running event loop" in str(e):
                print("Running in existing event loop...")
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


