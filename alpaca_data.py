# https://alpaca.markets/sdks/python/

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data import CryptoHistoricalDataClient, StockHistoricalDataClient, OptionHistoricalDataClient

from datetime import date, datetime, timedelta


# No keys required.
# crypto_client = CryptoHistoricalDataClient()

# Alpaca data keys
DATA_KEY = "PKMIDDD0B792FZO6HF7E"
DATA_SECRET = "u89kQV6dRJyom4ONFgpWHOr7jho8fY3SrMTD6Fvs"

data_client = StockHistoricalDataClient(DATA_KEY, DATA_SECRET)
# option_client = OptionHistoricalDataClient("api-key",  "secret-key")

# Define the symbols
symbolv = ["SPY", "XLK", "IGV"]
multisymbol_request_params = StockLatestQuoteRequest(symbol_or_symbols=symbolv)

# Download the last quote prices for the symbols
last_quote = data_client.get_stock_latest_quote(multisymbol_request_params)

# Print all the last quote prices
last_quote

# Print the SPY last ask price quote
last_quote["SPY"].ask_price

# Print the timestamp - a datetime structure
timestamp = last_quote["SPY"].timestamp
# Print the year
timestamp.year
# Format datetime structure into string
local_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
timestamp.isoformat()



## Download stock historical bar prices

# https://medium.com/@trademamba/alpaca-algorithmic-trading-api-in-python-part-2-getting-historical-stock-data-1cdf7ca0e3a2
# https://alpaca.markets/sdks/python/market_data.html#market-data
# https://alpaca.markets/sdks/python/api_reference/data/stock/historical.html

from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.timeframe import TimeFrame
from alpaca.data.requests import StockBarsRequest


## Download daily price bars
# Create request parameters for daily price bars
request_params = StockBarsRequest(
    symbol_or_symbols=symbolv,
    timeframe=TimeFrame.Day,
    start=datetime(2025, 6, 1),
    end=datetime(2025, 6, 9)
) # end StockBarsRequest


## Download minute price bars
# Create start and end datetime object from the attributes: 
# year, month, day, hour, minute, second
startd = datetime(2025, 6, 10, 14, 58, 1)
endd = datetime(2025, 6, 10, 15, 1, 1)

# Create request parameters for minute price bars
request_params = StockBarsRequest(
    symbol_or_symbols=symbolv,
    timeframe=TimeFrame.Minute,
    start=startd,
    end=endd
) # end StockBarsRequest


# Download the historical bar prices for the symbols
stock_bars = data_client.get_stock_bars(request_params)

# Print the bar prices
barp = stock_bars["SPY"]  # All the SPY price bars
bar2 = barp[2]  # Second SPY price bar
bar2.close # Close price of the second SPY price bar
bar2.timestamp # Timestamp of the second SPY price bar


## Download crypto historical bar data

from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime



# No keys required for crypto data
client = CryptoHistoricalDataClient()

request_params = CryptoBarsRequest(
                        symbol_or_symbols=["BTC/USD", "ETH/USD"],
                        timeframe=TimeFrame.Day,
                        start=datetime(2022, 7, 1),
                        end=datetime(2022, 9, 1)
                 )

bars = client.get_crypto_bars(request_params)

# convert to dataframe
bars.df

# access bars as list - important to note that you must access by symbol key
# even for a single symbol request - models are agnostic to number of symbols
bars["BTC/USD"]
