"""
Strategy trades a single stock using the streaming real-time stock price bars from the Alpaca API.
The strategy is based on the Z-score, equal to the difference between the stock's price minus its Moving Average Price (EMA), divided by the volatility.

    Z-score = (price - EMA) / volatility

The strategy uses streaming bar prices and streaming confirms via the Alpaca websocket API.

The strategy either takes profit if the unrealized P&L is above a certain threshold, or it executes the contrarian rule based on the Z-score.

The strategy uses the contrarian rule based on the Bollinger Bands concept, where the Z-score indicates if the stock is cheap or rich (expensive).

You can run the strategy by executing this script with the appropriate parameters in the terminal:
    python3 strat_bollinger_bars_vwap.py symbol num_shares type alpha vol_floor risk_premium take_profit_factor
Example:
    python3 strat_bollinger_bars_ema.py SPY 1 limit 0.3 0.1 2.0 20.0

The num_shares parameter specifies the number of shares for each trade.

The type parameter specifies the order type, either "market" or "limit".

The alpha parameter is the EMA decay parameter (0 < alpha <= 1).
It's used to calculate the Exponential Moving Average (EMA) of the stock price.
Larger alpha values apply more weight to past prices, with more smoothing, and a slower response to new prices.
Smaller alpha values provide less smoothing and a faster response to new prices.

The vol_floor is the minimum value of the dollar volatility used in the Z-score calculations.
This prevents division by very small numbers when the price volatility is low.
Typical values range from 0.01 to 0.2 depending on the asset and the time horizon.

The risk_premium parameter serves two purposes:
1. It adjusts the limit price for limit orders.
2. It serves as the threshold for the Z-score.

The risk_premium parameter is used to determine the limit price, compared to the ask or bid price.
The limit price adjustment pa is equal to the risk_premium parameter times the volatility.
For example, if the risk_premium is 2.0 and the volatility is $0.1, then the price adjustment pa is $0.2.
If the ask price is $100, then the limit buy price is set to $99.8.
If the bid price is $99, then the limit sell price is set to $99.2.
The subsequent limit order prices are spread apart by the price adjustment pa, to avoid submitting multiple limit orders at the same price.
If another limit order is submitted, then its price is set based on the previous limit order price and the risk_premium parameter.
For example, the next limit buy price after $99.8 would be set to $99.6.
This is to avoid submitting multiple limit orders at the same price.

The risk_premium serves as the threshold level for the Z-score.
If the Z-score is between -risk_premium and risk_premium, then the strategy does not trade.
If the Z-score is below -risk_premium, then it buys the stock.
If the Z-score is above +risk_premium, then it sells the stock.
It submits either limit or market orders when the Z-score is above +risk_premium or below -risk_premium.

The take_profit_factor is used to determine the take profit level for the strategy.
It is a multiplier applied to the average cost basis of the position.
For example, if the take_profit_factor is 2.0 and the average cost basis is $100, then the take profit level is set to $102.

NOTE:
This script is only for illustration purposes, and not a real trading strategy.
This is only an illustration how to use the streaming real-time data from the Alpaca websocket. 
"""


import os
import sys
import asyncio
import signal
import time
import math
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
from utils import get_position, cancel_orders, submit_order, convert_to_nytzone, calc_unrealized_pnl, EMACalculator


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
data_client = StockDataStream(DATA_KEY, DATA_SECRET, feed=DataFeed.SIP)
# Create the SDK trading client
trading_client = TradingClient(ALPACA_TRADE_KEY, ALPACA_TRADE_SECRET)
# Create the SDK trade update and confirmation client
confirm_stream = TradingStream(ALPACA_TRADE_KEY, ALPACA_TRADE_SECRET)


# --------- Get the trading parameters from the command line arguments --------

# Get the symbol, type, shares_per_trade, risk_premium, alpha, and vol_floor from the command line arguments
if len(sys.argv) > 7:
    symbol = sys.argv[1].strip().upper()  # Symbol to trade
    shares_per_trade = float(sys.argv[2])  # Number of shares to trade
    type = sys.argv[3].strip().lower()  # Order type (market/limit)
    alpha = float(sys.argv[4])  # EMA alpha parameter
    vol_floor = float(sys.argv[5])  # Volatility floor
    risk_premium = float(sys.argv[6])  # Limit price adjustment
    take_profit_factor = float(sys.argv[7])  # Take profit level
elif len(sys.argv) > 6:
    symbol = sys.argv[1].strip().upper()
    shares_per_trade = float(sys.argv[2])
    type = sys.argv[3].strip().lower()
    alpha = float(sys.argv[4])
    vol_floor = float(sys.argv[5])  # Volatility floor
    risk_premium = float(sys.argv[6])  # Limit price adjustment
    take_profit_factor = 20.0  # Default take profit level
elif len(sys.argv) > 5:
    symbol = sys.argv[1].strip().upper()
    shares_per_trade = float(sys.argv[2])  # Number of shares to trade
    type = sys.argv[3].strip().lower()  # Order type (market/limit)
    alpha = float(sys.argv[4])
    vol_floor = float(sys.argv[5])  # Volatility floor
    risk_premium = 2.0  # Default risk_premium value
    take_profit_factor = 20.0  # Default take profit level
elif len(sys.argv) > 4:
    symbol = sys.argv[1].strip().upper()
    shares_per_trade = float(sys.argv[2])  # Number of shares to trade
    type = sys.argv[3].strip().lower()  # Order type (market/limit)
    alpha = float(sys.argv[4])
    vol_floor = 0.1  # Default vol_floor value
    risk_premium = 2.0  # Default risk_premium value
    take_profit_factor = 20.0  # Default take profit level
else:
    # If not provided, prompt the user for input
    symbol = input("Enter symbol: ").strip().upper()
    shares_input = input("Enter number of shares to trade (default 1): ").strip()
    shares_per_trade = float(shares_input) if shares_input else 1
    type = input("Enter order type (market/limit): ").strip().lower()
    alpha_input = input("Enter EMA alpha parameter (default 0.1): ").strip()
    alpha = float(alpha_input) if alpha_input else 0.1
    risk_premium_input = input("Enter price adjustment (default 0.5): ").strip()
    risk_premium = float(risk_premium_input) if risk_premium_input else 0.5
    vol_floor_input = input("Enter volatility floor (default 0.05): ").strip()
    vol_floor = float(vol_floor_input) if vol_floor_input else 0.05
    take_profit_input = input("Enter take profit level (default 2.0): ").strip()
    take_profit_factor = float(take_profit_input) if take_profit_input else 2.0

print(f"Trading parameters: symbol={symbol}, type={type}, shares_per_trade={shares_per_trade}, alpha={alpha}, risk_premium={risk_premium}, vol_floor={vol_floor}, take_profit_factor={take_profit_factor}\n")


# --------- Specify the strategy parameters --------

# symbol = "SPY"
# Specify the strategy name
# Add to the strategy name its parameters.
# For example: "StratBoll001_SPY_limit_1_0.5_0.9_0.05"
strategy_name = f"StratBoll_{symbol}_ns{shares_per_trade}_{type}al{alpha}rp{risk_premium}vf{vol_floor}tp{take_profit_factor}"
# Specify the trading parameters
# shares_per_trade = 1  # Number of shares to trade per each order
# type = "market"
# type = "limit"
# trade_side = OrderSide.BUY  # Set to BUY or SELL as needed
# The risk_premium parameter, for the Z-score threshold and for setting the limit price
# risk_premium = 2.0  # The risk_premium parameter

# Initialize the strategy state variables
# The position_list is a list of prices paid or received for each stock position.
# Negative prices indicate long positions, and positive prices indicate short positions.
# Because when we buy a stock we pay for it, which is a negative cash flow, and when we sell it, we receive the market price, which is a positive cash flow.
# Initialize list of stock positions with fill prices
position_list = []  # List of stock positions with fill prices: negative for buys, positive for sells
position_shares = 0  # The number of shares currently owned (positive for long positions, negative for short positions)
position_broker = None  # The number of shares owned according to the broker

# A negative shares_available value indicates that there is a short position.
# A positive shares_available value indicates that there is a long position.
shares_available = 0  # The number of available shares to trade, according to the broker
pnl_real = 0  # The realized PnL of the strategy
pnl_unreal = 0  # The unrealized PnL of the strategy
# Initialize the order response variable
order_response = None
order_id = None  # Initialize order_id variable
# Initialize last limit price tracking for staggered orders
last_buy_price = None  # Track the last buy limit price submitted
last_sell_price = None  # Track the last sell limit price submitted
# Initialize list to track pending order IDs
open_orders = []  # List of pending limit order IDs
# Initialize the cumulative realized P&L
total_realized_pnl = 0.0  # The cumulative realized P&L from closed positions
unrealized_pnl = 0.0  # The unrealized PnL from open positions
price_vol = vol_floor  # The price volatility
# The price adjustment for limit orders
price_adjustment = risk_premium * price_vol
# The take profit level
take_profit_level = take_profit_factor * price_vol

# Create an instance of the EMACalculator for calculating the EMA prices and Z-scores
EMAC = EMACalculator()


# --------- Create the file names --------

# Create file names with today's NY date
tzone = ZoneInfo("America/New_York")
time_now = datetime.now(tzone)
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




# --------- Calculate the number of shares to trade to take profit on the unrealized P&L --------

# Calculate the trade side and the number of shares to trade based on the Z-score and the available shares.
# Returns trade_side = None if no trade is to be made.
def take_profit(position_shares, price_last, shares_per_trade, shares_available, last_buy_price, last_sell_price, price_adjustment):

    # Initialize the trade buy/sell side variable and the limit price
    trade_side = None
    limit_price = None
    shares_to_trade = 0  # Initialize shares_to_trade to 0

    if position_shares > 0:
        # If the position is long stock - submit a sell trade order
        trade_side = OrderSide.SELL
        # The limit price is equal to the last sell price plus the price_adjustment adjustment
        if last_sell_price is None:
            limit_price = round(price_last + price_adjustment, 2)
        else:
            limit_price = round(max(price_last, last_sell_price) + price_adjustment, 2)
        last_sell_price = limit_price

    else: # position_shares < 0
        # The position is short stock - submit a buy trade order
        trade_side = OrderSide.BUY
        # The limit price is equal to the last buy price minus the price_adjustment adjustment
        if last_buy_price is None:
            limit_price = round(price_last - price_adjustment, 2)
        else:
            limit_price = round(min(price_last, last_buy_price) - price_adjustment, 2)
        last_buy_price = limit_price

    # The number of shares to trade is limited by the shares_available
    shares_to_trade = min(abs(shares_available), shares_per_trade)

    return trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price

# End of take_profit



# --------- Calculate the number of shares to trade based on the Z-score --------

# Calculate the trade side and the number of shares to trade based on the Z-score and the available shares.
# Returns trade_side = None if no trade is to be made.
def calc_shares_to_trade(zscore, price_last, shares_per_trade, shares_available, last_buy_price, last_sell_price, risk_premium, price_adjustment):

    # Initialize the trade buy/sell side variable and the limit price
    trade_side = None
    limit_price = None
    shares_to_trade = 0  # Initialize shares_to_trade to 0

    # A negative shares_available value indicates that there is a short position.
    # In that case, the strategy can only buy back the shares it has sold short.
    # But it can sell more shares without limitation.

    # A positive shares_available value indicates that there is a long position.
    # In that case, the strategy can only sell the shares it owns.
    # But it can buy more shares without limitation.

    # If the Z-score is greater than the risk_premium, then submit a sell order
    # If the price is significantly different from the EMA price
    if zscore > risk_premium:
        # Submit a sell order if the price is significantly above the EMA price
        trade_side = OrderSide.SELL
        # The limit price is equal to the last sell price plus the price_adjustment adjustment
        if last_sell_price is None:
            limit_price = round(price_last + price_adjustment, 2)
        else:
            limit_price = round(max(price_last, last_sell_price) + price_adjustment, 2)
        last_sell_price = limit_price
        if shares_available > 0:
            # The number of shares to trade is limited by the shares_available
            shares_to_trade = min(abs(shares_available), shares_per_trade)
        else:
            # The number of shares to trade is equal to the shares_per_trade
            shares_to_trade = shares_per_trade

    # If the Z-score is less than minus the risk_premium, then submit a buy order
    elif zscore < (-risk_premium):
        # Submit a buy order if the price is significantly below the EMA price
        trade_side = OrderSide.BUY
        # The limit price is equal to the last buy price minus the price_adjustment adjustment
        if last_buy_price is None:
            limit_price = round(price_last - price_adjustment, 2)
        else:
            limit_price = round(min(price_last, last_buy_price) - price_adjustment, 2)
        last_buy_price = limit_price
        if shares_available < 0:
            # The number of shares to trade is limited by the shares_available
            shares_to_trade = min(abs(shares_available), shares_per_trade)
        else:
            # The number of shares to trade is equal to the shares_per_trade
            shares_to_trade = shares_per_trade

    else:
        # If the Z-score is not significant, do not trade
        print(f"No trade for {symbol} - the Z-score = {zscore:.2f} is not significant compared to the risk premium = {risk_premium}")
        shares_to_trade = 0

    return trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price

# End of calc_shares_to_trade



# --------- Define the trading function - the callback handler for the price bars --------
# The trading function receives the price bars and submits the trade orders

async def trade_bars(bar):

    global order_response, order_id, position_shares, position_broker, last_buy_price, last_sell_price, open_orders, position_list, unrealized_pnl, total_realized_pnl

    ### Get the latest price and volume from the price bar
    # print(f"Bar price: {bar}")
    # print(f"Symbol: {bar.symbol}, Open: {bar.open}, High: {bar.high}, Low: {bar.low}, Close: {bar.close}, Volume: {bar.volume}, Trade_count: {bar.trade_count}, VWAP: {bar.vwap}")
    price_last = bar.close
    volume_last = bar.volume
    timestamp = bar.timestamp.astimezone(tzone)
    date_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")


    ### Calculate the Z-score, EMA price, and price volatility
    zscore, ema_price, price_vol = EMAC.calc_zscorew(price_last, volume_last, alpha, vol_floor)
    # The price adjustment for limit orders
    price_adjustment = risk_premium * price_vol

    ### Calculate the unrealized P&L and update the stock positions
    position_shares, unrealized_pnl = calc_unrealized_pnl(position_list, price_last)

    print(f"Time: {date_time}, Symbol: {bar.symbol}, Z-score: {zscore:.2f}, Price: {price_last}, EMA: {ema_price:.2f}, Vol: {price_vol:.4f}")
    print(f"Position: {position_shares} shares, Pending orders: {len(open_orders)}, Unrealized P&L: ${unrealized_pnl:.2f}, Realized P&L: ${total_realized_pnl:.2f}")
    # Print the current position list
    print(f"Current position list: {position_list}")
    # Print the current pending order IDs
    print(f"Current pending order IDs: {open_orders}")


    ### Get the current position from the broker and the number of available shares to trade for the symbol
    position_broker = get_position(trading_client, symbol)
    if position_broker is None:
        # There is no open position - set the available shares to the number of shares traded per each order
        shares_available = shares_per_trade
        # position_shares = 0
    else:
        # Get the number of available shares to trade from the broker
        shares_available = float(position_broker.qty_available)
        position_broker = float(position_broker.qty)


    ### Cancel all the open limit orders if there are no available shares for the symbol
    if (shares_available == 0):  # No shares available
        # Cancel all the open limit orders
        print(f"\nNo shares available for {symbol}")
        # print(f"\nNo shares available for {symbol} - Canceling all open limit orders")
        # open_orders = cancel_orders(trading_client, symbol, canceled_file, open_orders)
        # last_sell_price = None  # Reset the last sell limit price
        # last_buy_price = None  # Reset the last buy limit price


    ### Cancel all the open limit orders if the limit prices are too far apart
    if (last_buy_price is not None) and (last_sell_price is not None):
        if (last_sell_price - last_buy_price) > (10 * price_adjustment):
            # Cancel all the open limit orders
            print(f"\nThe limit prices are too far apart for {symbol} - Canceling all open limit orders")
            open_orders = cancel_orders(trading_client, symbol, canceled_file, open_orders)
            last_sell_price = None  # Reset the last sell limit price
            last_buy_price = None  # Reset the last buy limit price


    ### Either take profit on the unrealized P&L or execute the contrarian rule based on the Z-score
    # If the position is long and the price is above the EMA price by the take profit level, then sell the position

    # Initialize the trade side
    trade_side = None
    # Update the take profit level
    take_profit_level = take_profit_factor * price_vol

    # Apply the take-profit rule
    if unrealized_pnl > take_profit_level:
        print(f"\nTake profit triggered for {symbol}: Selling the position\n")
        print(f"Unrealized PnL = {unrealized_pnl} and Take profit level = {take_profit_level}\n")
        trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price = take_profit(position_shares, price_last, shares_per_trade, shares_available, last_buy_price, last_sell_price, price_adjustment)

    # Apply the contrarian rule based on the Z-score
    else:
        print(f"\nTake profit not triggered for {symbol} - Applying contrarian rule\n")
        # Calculate the trade side and the number of shares to trade based on the Z-score and the available shares.
        trade_side, limit_price, shares_to_trade, last_buy_price, last_sell_price = calc_shares_to_trade(zscore, price_last, shares_per_trade, shares_available, last_buy_price, last_sell_price, risk_premium, price_adjustment)


    ### Submit the trade order if the trade side is not None
    if trade_side is not None:

        print(f"Z-score: {zscore:.2f}, Side: {trade_side}, Limit price: {limit_price}, Shares to trade: {shares_to_trade}")
        order_response = None
        order_response = submit_order(trading_client, symbol, shares_to_trade, trade_side, type, limit_price, submits_file, error_file)

        # If the order submission failed, cancel all the open limit orders for the symbol and submit the order again
        if order_response is None:
            print(f"Trade order submission failed for {symbol}")
            print(f"Canceling all open orders for {symbol}")
            open_orders = cancel_orders(trading_client, symbol, canceled_file, open_orders)
            last_sell_price = None  # Reset the last sell limit price
            last_buy_price = None  # Reset the last buy limit price
            # Submit the trade order again
            print(f"Submitting the trade order again for {symbol}")
            order_response = submit_order(trading_client, symbol, shares_to_trade, trade_side, type, limit_price, submits_file, error_file)

        # Add the order ID to the pending orders list
        if order_response is not None:
            # Extract the order ID from the order_response
            order_id = str(order_response.id)
            open_orders.append(order_id)
            print(f"Added order ID {order_id} to pending list. Total pending orders: {len(open_orders)}")
            # Print the current pending order IDs
            # print(f"Current pending order IDs: {open_orders}")
        else:
            print("Failed to submit order after retry\n")
    else:
        trade_side = None # No trade executed, side remains None


    ### Save the strategy state to the CSV file
    state_data = {
        "date_time": date_time,
        "symbol": bar.symbol,
        "price": bar.close,
        "volatility": (bar.high - bar.low),
        "zscore": zscore,
        "order": trade_side,
        "position_shares": position_shares,
        "pnlReal": total_realized_pnl,
        "pnlUnreal": unrealized_pnl,
    }
    state_data = pd.DataFrame([state_data])
    state_data.to_csv(state_file, mode="a", header=not os.path.exists(state_file), index=False)
    print("Done\n")

# End of callback function trade_bars



# --------- Define the callback handler for the trade updates and trade confirms --------

async def handle_trade_update(event_data):

    global position_shares, open_orders, position_list, total_realized_pnl

    # Get the event order ID from the event data
    order_id = str(event_data.order.id)
    
    ### Check if this order ID is in the pending list
    if order_id in open_orders:

        # Unpack the event_data into a dictionary
        event_dict = event_data.model_dump()  # Convert to dictionary
        event_dict = convert_to_nytzone(event_dict)
        event_name = str(event_dict["event"]).lower()  # Get the event name
        time_stamp = event_dict["timestamp"]
        orderinfo = event_dict["order"]
        # Remove the "order" key from the event_dict
        event_dict.pop("order", None)
        symbol = orderinfo["symbol"]
        # event_dict = event_dict | orderinfo  # Combine dictionaries
        event_dict.update(orderinfo)  # This adds order fields to event_dict while preserving the "order" key
        time_now = datetime.now(tzone).strftime("%Y-%m-%d %H:%M:%S")

        # Process the event data based on the event type
        if (event_name == "fill") or (event_name == "partial_fill"):
            type = orderinfo["order_type"]
            trade_side = orderinfo["side"]
            qty_filled = float(orderinfo["qty"])
            fill_price = float(orderinfo.get("filled_avg_price", 0))
            print(f"Order {order_id} filled at {time_now} at price {fill_price}")
            # Process the fill data FIRST before stopping
            print(f"{time_stamp} Filled {type} {trade_side} order for {qty_filled} shares of {symbol} at {fill_price}")

            # Update position_list and calculate realized P&L after the trade is filled
            if trade_side == "buy":
                
                # Check if there are existing positions and their direction
                if (not position_list) or all(price < 0 for price in position_list):
                    # Add new buy positions as negative prices
                    for _ in range(int(qty_filled)):
                        position_list.append(-fill_price)
                    print(f"Added {int(qty_filled)} buy positions at ${fill_price}")
                else:
                    # Existing positions are sells (positive) - closing short position
                    realized_pnl = 0.0
                    shares_to_close = int(qty_filled)
                    for _ in range(shares_to_close):
                        if position_list and position_list[0] > 0:  # Pop sell positions (positive prices)
                            position_price = position_list.pop(0)
                            # Realized P&L = sell price - buy price (for closing short)
                            realized_pnl += (position_price - fill_price)
                        else:
                            # No more short positions to close, add as new long position
                            position_list.append(-fill_price)
                    print(f"Closed {shares_to_close} short positions. Realized P&L: ${realized_pnl:.2f}")
                    total_realized_pnl += realized_pnl
                    
            elif trade_side == "sell":
                
                # Check if we have existing positions and their direction
                if not (position_list) or all(price > 0 for price in position_list):
                    # No existing positions - add new sell positions as positive prices
                    # All existing positions are sells (positive) - add to short position
                    for _ in range(int(qty_filled)):
                        position_list.append(fill_price)
                    print(f"Added {int(qty_filled)} sell positions at ${fill_price}")
                else:
                    # Existing positions are buys (negative) - closing long position
                    realized_pnl = 0.0
                    shares_to_close = int(qty_filled)
                    for _ in range(shares_to_close):
                        if position_list and position_list[0] < 0:  # Pop buy positions (negative prices)
                            position_price = position_list.pop(0)
                            # Realized P&L = sell price - buy price (for closing long)
                            realized_pnl += (position_price + fill_price)
                        else:
                            # No more long positions to close, add as new short position
                            position_list.append(fill_price)
                    print(f"Closed {shares_to_close} long positions. Realized P&L: ${realized_pnl:.2f}")
                    total_realized_pnl += realized_pnl
            # End Update position_list and calculate realized P&L after the trade is filled

            # Print the current position list
            print(f"Current position list: {position_list}")

            # Update the position_shares - the number of shares currently owned (positive for long positions, negative for short positions)
            if not position_list:
                position_shares = 0
            else:
                position_shares = -math.copysign(1, position_list[0]) * len(position_list)
            print(f"Position after the fill: {position_shares} shares of {symbol}")
            position_broker = event_dict.get("position_qty", 0)
            print(f"Position from broker after the fill: {position_broker} shares of {symbol}")
            
            # Remove the filled order ID from the pending list
            open_orders.remove(order_id)
            print(f"Removed order ID {order_id} from pending list. Remaining number of pending orders: {len(open_orders)}")
            print(f"Updated stock positions: {len(position_list)} total positions, current list: {position_list}")
            
            # Save fill data to CSV
            event_frame = pd.DataFrame([event_dict])
            event_frame.to_csv(fills_file, mode="a", header=not os.path.exists(fills_file), index=False)
            print(f"Fill appended to {fills_file}")

        elif (event_name == "pending_new") or (event_name == "new") or (event_name == "accepted"):
            # Do nothing on pending_new or new events
            # pass # Will implement later
            print(f"Event {event_name} received for order {order_id} at {time_now}")
            # print("New order event received")
            # event_frame = pd.DataFrame([event_dict])
            # event_frame.to_csv(submits_file, mode="a", header=not os.path.exists(submits_file), index=False)
            # print(f"{time_stamp} New {type} {trade_side} order for {qty_filled} shares of {symbol}")
            # print(f"New trade appended to {submits_file}")

        elif (event_name == "canceled") or (event_name == "expired") or (event_name == "rejected"):
            # print(f"Cancel event: {event_dict}")
            print(f"Order {order_id} canceled or expired at {time_now}")
            # Remove the canceled order ID from pending list
            open_orders.remove(order_id)
            print(f"Removed canceled order ID {order_id} from pending list. Remaining pending orders: {len(open_orders)}")
            # Append to CSV (write header only if file does not exist)
            event_frame = pd.DataFrame([event_dict])
            event_frame.to_csv(canceled_file, mode="a", header=not os.path.exists(canceled_file), index=False)
            print(f"Canceled order appended to {canceled_file}")
            # await confirm_stream.stop_ws()  # Stop on cancel too

        elif event_name == "replaced":
            print(f"Replace event: {event_dict}")
        else:
            print(f"Unknown event: {event_name}")
        print(f"Finished processing the {event_name} update for order {order_id} at {time_now}\n")
    else:
        # Order ID not in pending list - ignore or log
        pass # Will implement later?
        # print(f"Received update for order {order_id} which is not in pending list")

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

