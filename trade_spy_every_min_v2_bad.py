from alpaca.trading.client import TradingClient
import pandas as pd
import schedule
import time
import pytz
from datetime import datetime, timezone, timedelta
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

import alpaca_trade_api as tradeapi
import requests

# Data keys
DATA_KEY = "PKGDN9L1MYC1MJSRNVE1"
DATA_SECRET = "9Y1jYDuIl99fGW05NP4RF8h5FPgiYVSVhL4PZcmc"

# Trade keys
TRADE_KEY = "PKI8KON8MOVFWQNLLMWZ"
TRADE_SECRET = "dCYME7RcZenjoOihF61VM2KbHn9vU0XaiyvWHjD3"

BASE_URL = "https://paper-api.alpaca.markets"

data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)
trade_api = tradeapi.REST(TRADE_KEY, TRADE_SECRET, BASE_URL, api_version="v2")
trading_client = TradingClient(TRADE_KEY, TRADE_SECRET)

# Get current NY time
# Define NY timezone
ny_timezone = pytz.timezone("America/New_York")
current_time = datetime.now(ny_timezone)
print(current_time)



def fetch_and_trade():
    # print("Before try")  # Debugging output
    try:
        # Your trading logic...
        print("Running trading script...")  # Debugging output

        # Get current NY time
        current_time = datetime.now(ny_timezone)
        # Run only between allowed hours (4 AM - 8 PM EST)
        if current_time.hour < 4 or current_time.hour >= 20:
            print("Current time is outside of trading hours. Exiting script.")
            exit()
        print(current_time)

        # Calculate start time (10 minutes ago)
        start_time = datetime.now(timezone.utc) - timedelta(minutes=20)
        # start_time = (datetime.utcnow() - timedelta(minutes=20)).isoformat()
        start = start_time.strftime("%Y-%m-%d %H:%M:%S")
        print("Formatted start: ", start)

        # Get current UTC time
        utc_now = datetime.now(timezone.utc)

        end = utc_now.strftime("%Y-%m-%d %H:%M:%S")
        # print("Formatted End:", end)
        # exit()

        request_params = StockBarsRequest(
            symbol_or_symbols=["SPY"],
            timeframe=TimeFrame.Minute,
            start=start,
            end=end,
            limit=100
        )

        bars = data_client.get_stock_bars(request_params)
        df = pd.DataFrame([bar.model_dump() for bar in bars["SPY"]])
        print("Data = ", df.head())  # Debugging output to check data

        # Feature Engineering
        df["price_previous"] = df["close"].shift(1)
        df["vol_previous"] = df["volume"].shift(1)
        df["vwap_signal"] = df["vwap"] - df["close"]
        df["price_change"] = df["close"] - df["price_previous"]
        df["vol_change"] = df["volume"] - df["vol_previous"]

        # Save DataFrame to CSV
        df.to_csv("spybars.csv", index=False, mode="a", header=False)

        # Trading Signal
        last_row = df.iloc[-1]
        last_vwap_signal = float(last_row["vwap_signal"])
        last_volume = int(last_row["volume"])

        signal = "Hold"
        if last_vwap_signal > 0:
            signal = "Buy"
        elif last_vwap_signal < 0:
            signal = "Sell"
        # print(signal)

        std_vol_change = df["vol_change"].std()
        std_vol_change = int(std_vol_change)
        # Log standard deviation of volume change
        print(f"Std dev vol change: {std_vol_change}")
        vol_signal = "No trade"
        if last_volume > 2 * std_vol_change:
            vol_signal = "trade"
        # print(vol_signal)

        # Get all open positions
        portfolio = trading_client.get_all_positions()
        print(type(portfolio))  # Check if it's a list or object
        # print(portfolio)  # View the actual data
        for portfolio in portfolio:
            print(portfolio.qty)  # Iterate over each position
            # positionqty = int(portfolio)
            positionqty = portfolio.qty

        long_limit = 5
        short_limit = -5

        # Get latest bid/ask prices
        headers = {
            "APCA-API-KEY-ID": DATA_KEY,
            "APCA-API-SECRET-KEY": DATA_SECRET
        }
        params = {"symbols": "SPY"}
        response = requests.get(
            "https://data.alpaca.markets/v2/stocks/quotes/latest", headers=headers, params=params)
        json_data = response.json()
        ask = json_data['quotes']['SPY']['ap']
        bid = json_data['quotes']['SPY']['bp']
        spread = (ask - bid) * 1000
        spread = int(spread)
        spreadlimit = 61  # Set a limit for the spread

        # Log ask and bid prices
        print(f"Ask: {ask}, Bid: {bid}, Spread: {spread}")
        # Place an order if conditions are met

        # Place an order if conditions are met
        order = 'no order placed because conditions were not met'
        # Log signals
        print(
            f"Signal: {signal}, Volume Signal: {vol_signal}, Spread: {spread}")

        if signal == "Buy" and vol_signal == "trade" and spread < spreadlimit:
            # if signal == "Buy" and vol_signal == "trade" and spread < spreadlimit and positionqty < long_limit:
            # Check if the position limit is reached
            order = trade_api.submit_order(
                symbol="SPY",
                qty=1,
                side="buy",
                type="limit",
                limit_price=ask,
                extended_hours=True,
                time_in_force="day"
            )
            print(f"Order placed at {ask}: {order.client_order_id}")

        elif signal == "Sell" and vol_signal == "trade" and spread < spreadlimit:
            # elif signal == "Sell" and vol_signal == "trade" and spread < spreadlimit and position.qty > short_limit:
            order = trade_api.submit_order(
                symbol="SPY",
                qty=1,
                side="sell",
                type="limit",
                limit_price=bid,
                extended_hours=True,
                time_in_force="day"
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
