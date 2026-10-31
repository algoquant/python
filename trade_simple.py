# Trade a single stock.

import pandas as pd
import schedule
import time
import pytz
from datetime import datetime, timezone, timedelta
from alpaca.data.requests import StockLatestBarRequest, StockLatestQuoteRequest
from alpaca.data.enums import DataFeed
from alpaca.trading.enums import OrderSide
from MachineTrader.helpers.alpacasdk import AlpacAPI

alpaca_sdk = AlpacAPI()
alpaca_sdk.create_trade_clients()
data_client = alpaca_sdk.create_data_client()
trading_client = alpaca_sdk.get_trading_client()
symbol = "SPY"
# Define the number of shares to trade
qty = 1  # Number of shares 
# Define the request parameters for live stock prices
params = {"symbols": symbol, "feed": "sip"}


# Define the trading function
def fetch_and_trade():
    try:
        print("Running trading script...")

        ny_timezone = pytz.timezone("America/New_York")
        current_time = datetime.now(ny_timezone)
        if current_time.hour < 4 or current_time.hour >= 20:
            print("Current time is outside of trading hours. Exiting script.")
            return

        print("Date and time: ", current_time.strftime("%Y-%m-%d %H:%M:%S"))

        bar_request = StockLatestBarRequest(symbol_or_symbols=symbol, feed=DataFeed.SIP)
        bar_data = data_client.get_stock_latest_bar(bar_request)
        bar = bar_data[symbol].model_dump()
        close_price = bar["close"]
        vwap = bar["vwap"]
        print(f"Last close price: {close_price}, VWAP: {vwap}")
        print(f"Open: {bar['open']}, High: {bar['high']}, Low: {bar['low']}, Close: {bar['close']}, Volume: {bar['volume']}, VWAP: {bar['vwap']}")

        quote_request = StockLatestQuoteRequest(symbol_or_symbols=symbol, feed=DataFeed.SIP)
        quote_data = data_client.get_stock_latest_quote(quote_request)
        ask = quote_data[symbol].ask_price
        bid = quote_data[symbol].bid_price
        spread = int((ask - bid) * 1000)
        spreadlimit = 61

        signal = "Buy" if close_price > vwap else "Sell"
        vol_signal = "trade"

        print(f"Ask: {ask}, Bid: {bid}, Spread: {spread}")
        print(f"Signal: {signal}, Volume Signal: {vol_signal}, Spread: {spread}")

        if signal == "Buy" and spread < spreadlimit:
            order = alpaca_sdk.submit_order(
                symbol=symbol,
                shares_per_trade=qty,
                side=OrderSide.BUY,
                type="limit",
                limit_price=ask,
            )
            print(f"Order placed at {ask}: {order.client_order_id}")
        elif signal == "Sell" and spread < spreadlimit:
            order = alpaca_sdk.submit_order(
                symbol=symbol,
                shares_per_trade=qty,
                side=OrderSide.SELL,
                type="limit",
                limit_price=bid,
            )
            print(f"Order placed at {bid}: {order.client_order_id}")
    except Exception as e:
        print(f"Error in fetch_and_trade: {e}")

# schedule.every(1).minutes.do(fetch_and_trade)
schedule.every(10).seconds.do(fetch_and_trade)

while True:
    try:
        schedule.run_pending()
        time.sleep(1)  # Prevent CPU overload
    except Exception as e:
        print(f"Loop error: {e}")  # Log loop errors


