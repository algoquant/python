### Liquidate all the open positions for some symbols or for all the symbols, 
# by submitting market orders using the Alpaca SDK.
# If there are open limit orders that prevent the positions from being liquidated,
# then cancel them and try again.
# https://alpaca.markets/sdks/python/trading.html
#
# For example, to liquidate all the positions for just SPY:
# python3 liquidate_positions_all.py SPY
#
# To liquidate positions for multiple symbols:
# python3 liquidate_positions_all.py AAPL MSFT TSLA
#
# To liquidate all the positions for all the symbols:
# python3 liquidate_positions_all.py

import sys
import os
import time
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus


# --------- Create the SDK clients --------

# Load the API keys from .env file
load_dotenv("/Users/jerzy/Develop/Python/.env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
ALPACA_TRADE_KEY = os.getenv("ALPACA_TRADE_KEY")
ALPACA_TRADE_SECRET = os.getenv("ALPACA_TRADE_SECRET")


# Create the SDK trading client
trading_client = TradingClient(ALPACA_TRADE_KEY, ALPACA_TRADE_SECRET)


# --------- Get the trading parameters from the command line arguments --------

# Get the symbols from the command line arguments
symbols = []
if len(sys.argv) > 1:
    symbols = [arg.strip().upper() for arg in sys.argv[1:]]


# --------- Get all the open positions and their symbols --------

# Get all the open positions, then filter for the specified symbols
all_positions = trading_client.get_all_positions()
positions = []
if symbols:
    positions = [pos for pos in all_positions if pos.symbol in symbols]
else:
    positions = all_positions

# Get the symbols from the positions
if positions:
    symbols = [pos.symbol for pos in positions]


# --------- Liquidate all the positions --------

if symbols:
    try:
        print(f"Liquidating all positions for symbols: {', '.join(symbols)}\n")
        
        # Close the positions for each symbol using close_position method
        for symbol in symbols:
            try:
                print(f"Closing the positions for {symbol}...")
                response = trading_client.close_position(symbol)
                print(f"Successfully initiated close for {symbol}")

            except Exception as e:
                print(f"Couldn't close the position for {symbol} or error: {e}")
                print(f"Cancelling all limit orders for {symbol}")
                from alpaca.trading.requests import GetOrdersRequest
                # Get all open orders for the symbol
                orders = trading_client.get_orders(
                    filter=GetOrdersRequest(
                        status=QueryOrderStatus.OPEN,
                        symbols=[symbol]
                    )
                )
                for order in orders:
                    if order.type == "limit":
                        print(f"Cancelling limit order {order.id} for {symbol}")
                        trading_client.cancel_order(order.id)
                            continue
                print(f"Closing the positions again for {symbol}...")
                response = trading_client.close_position(symbol)
        
        print("\nWaiting 2 seconds for positions to close...")
        time.sleep(2)
        
        # Check remaining positions for the specified symbols
        all_positions = trading_client.get_all_positions()
        remaining_symbols = []
        for position in all_positions:
            if position.symbol in symbols:
                remaining_symbols.append(position.symbol)
        if not remaining_symbols:
            print(f"All the positions closed successfully for symbols: {', '.join(symbols)}")
        else:
            print(f"There are still open positions for: {', '.join(remaining_symbols)}")
            
    except Exception as e:
        print(f"Error while liquidating positions: {e}")
        sys.exit(1)

# Close all the positions for all the symbols and also cancel all the open orders
# This will probably never run because if there are no symbols, that means there are no positions
elif positions:
    try:
        print(f"Liquidating all positions for all symbols\n")
        trading_client.close_all_positions(cancel_orders=True)
        print("Waiting 2 seconds for positions to close...")
        time.sleep(2)
        # Get all remaining positions
        position_broker = trading_client.get_all_positions()
        if not position_broker:
            print("All the positions for all symbols closed successfully.")
        else:
            print(f"There are still {len(position_broker)} open positions.")
    except Exception as e:
        print(f"No position found for any symbols or error: {e}")
        sys.exit(1)

