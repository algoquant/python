'''
Runs during extended hours (4:00 AM - 8 PM NY time) 
✅ Fetches real-time market data from Alpaca 
✅ Processes financial metrics for forecasting 
✅ Uses Nixtla to predict future price trends 
✅ Appends new data to CSV files every minute
'''

import pandas as pd
import schedule
import time
import pytz
from datetime import datetime, timedelta, timezone
from nixtla import NixtlaClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Initialize clients
# Initialize Nixtla client (replace with your API key)
nixtla_client = NixtlaClient(api_key="nixak-RZih4szstYW2TXtlkqT9EeEI6H5SdQCSVYUEFE0kfGYwz6ltQoIH7QOxdqPZeuhbR4jnAuCCCtmRFuEy")
client = StockHistoricalDataClient('PKMIDDD0B792FZO6HF7E', 'u89kQV6dRJyom4ONFgpWHOr7jho8fY3SrMTD6Fvs')

count = 0
print(count)


# Define NY timezone
ny_timezone = pytz.timezone("America/New_York")

# Function to run the trading script
def fetch_and_forecast():
    # Get current NY time
    current_time = datetime.now(ny_timezone)
    print(f"Current NY Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    # Check if current time is within market hours


    # Run only between market hours
    if current_time.hour < 4 or current_time.hour >= 20:
        return  
        exit()


 #   if current_time.hour == 9 and current_time.minute < 30:
 #       return  # Before 9:30 AM, skip execution
 #   if current_time.hour >= 16:
 #       return  # After 4 PM, skip execution



    # Define start and end time for Alpaca API
    # Get the timestamp one minute ago, formatted correctly
    start_time = (datetime.now(timezone.utc) - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
    end_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"Fetching data from {start_time} to {end_time}")

    request_params = StockBarsRequest(
        symbol_or_symbols=["SPY"],
        timeframe=TimeFrame.Minute,
        start=start_time,
        end=end_time,
        limit=1
    )

    bars = client.get_stock_bars(request_params)


    try:
        df = pd.DataFrame([bar.model_dump() for bar in bars["SPY"]])

    # Feature Engineering
        df["price_previous"] = df["close"].shift(1)
        df["vol_previous"] = df["volume"].shift(1)
        df["vwap_signal"] = df["vwap"] - df["close"]
        df["price_change"] = df["close"] - df["price_previous"]
        df["vol_change"] = df["volume"] - df["vol_previous"]
        df["ds"] = end_time
        df["y"] = df["close"]



    # Save DataFrame to CSV
        df.to_csv("spybars_nixtla.csv", index=False, mode="a", header=False)

    except Exception as e:
        print(f"Error fetching stock bars: {e}")
        bars = None  # Or assign a default value as needed


    if current_time.hour > 10:
       # Forecast using Nixtla
        forecast_df = nixtla_client.forecast(df, h=24, level=[80, 90])
        forecast_df.to_csv("forecast1.csv", index=False, mode="a", header=False)

    print(f"Logged data at {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
 
# This script fetches real-time market data for SPY from Alpaca, processes it, and uses Nixtla for forecasting.
# It appends the data to a CSV file every minute during market hours (4 AM - 8 PM NY time).\
# Note: The Nixtla API key and Alpaca API keys should be kept secure and not hard-coded in production code.
# Schedule the task to run every minute

# Schedule the task every minute
#schedule.every(5).seconds.do(fetch_and_forecast)
schedule.every(1).minutes.do(fetch_and_forecast)

while True:
    schedule.run_pending()
    time.sleep(1)
