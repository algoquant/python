# https://alpaca.markets/sdks/python/

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest
from alpaca.data import CryptoHistoricalDataClient, StockHistoricalDataClient, OptionHistoricalDataClient

from datetime import date, datetime, timedelta


# No keys required.
# crypto_client = CryptoHistoricalDataClient()

# Alpaca keys required
stock_client = StockHistoricalDataClient("PK4UNYPVORMPX95M84XU",  "CMWHADdSiqSDqPHRRKrcjvtDttcL0tp0uiVH4MK8")
# option_client = OptionHistoricalDataClient("api-key",  "secret-key")

# Define the symbols
multisymbol_request_params = StockLatestQuoteRequest(symbol_or_symbols=["SPY", "XLK", "IGV"])

# Get the last quote prices for the symbols
last_quote = stock_client.get_stock_latest_quote(multisymbol_request_params)

# Get the SPY last ask price quote
last_quote["SPY"].ask_price

# Get the timestamp - a datetime structure
timestamp = last_quote["SPY"].timestamp
# Get the year
timestamp.year
# Format datetime structure into string
local_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
timestamp.isoformat()

local_time = datetime.fromtimestamp(timestamp)



# gld_latest_ask_price = last_quote["GLD"].ask_price



## Get historical bar data

from alpaca.data.historical import CryptoHistoricalDataClient
from alpaca.data.requests import CryptoBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime

# no keys required for crypto data
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
