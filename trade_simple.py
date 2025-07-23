# Trade a single stock.

import pandas as pd
import schedule
import time
import pytz
from datetime import datetime, timezone, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.requests import StockQuotesRequest, StockLatestQuoteRequest

from alpaca.data.timeframe import TimeFrame
from alpaca.data import StockHistoricalDataClient
from alpaca.data.enums import DataFeed


import alpaca_trade_api as tradeapi
import requests
from dotenv import load_dotenv
import os

# Load API keys from .env file
load_dotenv(".env")
# Data keys
DATA_KEY = os.getenv("DATA_KEY")
DATA_SECRET = os.getenv("DATA_SECRET")
# Trade keys
TRADE_KEY = os.getenv("TRADE_KEY")
TRADE_SECRET = os.getenv("TRADE_SECRET")

BASE_URL = "https://paper-api.alpaca.markets"

data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)
trade_api = tradeapi.REST(TRADE_KEY, TRADE_SECRET, BASE_URL, api_version="v2")

from alpaca.trading.client import TradingClient
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)

# Define the trading symbol
symbol = "SPY"
# Define the number of shares to trade
qty = 1  # Number of shares 
# Define the request parameters for live stock prices
headers = {
    "APCA-API-KEY-ID": DATA_KEY,
    "APCA-API-SECRET-KEY": DATA_SECRET
}
params = {"symbols": symbol, "feed": "sip"}


# Define the trading function
def fetch_and_trade():
    # Use try-except to handle errors
    try:
        # Perform the trading logic
        print("Running trading script...")  # Debugging output
        
        # Define NY timezone
        ny_timezone = pytz.timezone("America/New_York")
        # Get current NY time
        current_time = datetime.now(ny_timezone)
        # Run only between allowed hours (4 AM - 8 PM EST)
        if current_time.hour < 4 or current_time.hour >= 20:
            print("Current time is outside of trading hours. Exiting script.")
            exit()
                                            
        # Print current date and time
        print("Date and time: ", current_time.strftime("%Y-%m-%d %H:%M:%S"))

        # Get the latest OHLCV bar of prices
        response = requests.get(
            "https://data.alpaca.markets/v2/stocks/bars/latest",
            headers=headers,
            params=params
        )
        bar_data = response.json()
        bar = bar_data["bars"][symbol]
        close_price = bar['c']
        vwap = bar['vw']
        print(f"Last close price: {close_price}, VWAP: {vwap}")
        # print(f"Latest price bar for {symbol}: {bar}")
        print(f"Open: {bar['o']}, High: {bar['h']}, Low: {bar['l']}, Close: {bar['c']}, Volume: {bar['v']}, VWAP: {bar['vw']}")

        # Calculate the trading signal
        signal = "Hold"
        if last_vwap_signal > 0:
            signal = "Buy"
        elif last_vwap_signal < 0:
            signal = "Sell"
#        print(signal)


        std_vol_change = df["vol_change"].std()
        std_vol_change = int(std_vol_change)
        print(f"Std dev vol change: {std_vol_change}")  # Log standard deviation of volume change
        vol_signal = "No trade"
        if last_volume > 2 * std_vol_change:
            vol_signal = "trade" 
#        print(vol_signal)
        
        # Get all open positions
        # portfolio = trading_client.get_all_positions()
        # print(type(portfolio))  # Check if it's a list or object
        # #print(portfolio)  # View the actual data
        # for portfolio in portfolio:
        #     print(portfolio.qty)  # Iterate over each position
        #     # positionqty = int(portfolio)
        #     positionqty = portfolio.qty

        # long_limit = 200        
        # short_limit = -200 
        
        # Get the latest bid/ask prices
        headers = {
            "APCA-API-KEY-ID": DATA_KEY,
            "APCA-API-SECRET-KEY": DATA_SECRET
        }
        params = {"symbols": symbol}
        response = requests.get(
            "https://data.alpaca.markets/v2/stocks/quotes/latest", 
            headers = headers, 
            params = params)
        json_data = response.json()
        ask = json_data['quotes']['SPY']['ap']
        bid = json_data['quotes']['SPY']['bp']
        spread = (ask - bid) * 1000
        spread = int(spread)
        spreadlimit = 61  # Set a limit for the spread

        print(f"Ask: {ask}, Bid: {bid}, Spread: {spread}")  # Log ask and bid prices
        # Place an order if conditions are met

        # Place an order if conditions are met
        order = 'no order placed because conditions were not met'
        print(f"Signal: {signal}, Volume Signal: {vol_signal}, Spread: {spread}")  # Log signals
            
        if signal == "Buy" and vol_signal == "trade" and spread < spreadlimit:
        #if signal == "Buy" and vol_signal == "trade" and spread < spreadlimit and positionqty < long_limit:
            # Check if the position limit is reached
            order = trade_api.submit_order(
                symbol = symbol,
                qty = qty,
                side = "buy",
                type = "limit",
                limit_price = ask,
                extended_hours = True,
                time_in_force = "day"
            )
            print(f"Order placed at {ask}: {order.client_order_id}")
        
        elif signal == "Sell" and vol_signal == "trade" and spread < spreadlimit:
        #elif signal == "Sell" and vol_signal == "trade" and spread < spreadlimit and position.qty > short_limit:
            order = trade_api.submit_order(
                symbol = symbol,
                qty = qty,
                side = "sell",
                type = "limit",
                limit_price = bid,
                extended_hours = True,
                time_in_force = "day"
            )
            print(f"Order placed at {bid}: {order.client_order_id}")
        

    except Exception as e:
        print(f"Error in fetch_and_trade: {e}")  # Log errors   

# schedule.every(1).minutes.do(fetch_and_trade)
schedule.every(10).seconds.do(fetch_and_trade)

while True:
    try:
        schedule.run_pending()
        time.sleep(1)  # Prevent CPU overload
    except Exception as e:
        print(f"Loop error: {e}")  # Log loop errors


