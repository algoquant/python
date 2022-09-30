## Utility functions

import math
import numpy as np
import pandas as pd

# Package for download
import requests


## Lag a numpy array and pad with zeros
def lagit(xs, n):
    e = np.empty_like(xs)
    if n >= 0:
        e[:n] = 0
        e[n:] = xs[:-n]
    else:
        e[n:] = 0
        e[:n] = xs[-n:]
    return e
# end lagit


## Calculate the rolling sum - output same length as input
# https://stackoverflow.com/questions/30399534/shift-elements-in-a-numpy-array
def calc_rollsum(a, lb=3):
    ret = np.cumsum(a)
    ret[lb:] = ret[lb:] - ret[:-lb]
    return ret
# end calc_rollsum



## Calculate the Sharpe ratio
def calc_sharpe(returnts, raterf=0.0):
    # Calculate mean returns
    meanret = returnts.mean()
    # Calculate standard deviation
    stdev = returnts.std()
    # Calculate daily Sharpe ratio
    sharper = (meanret-raterf)/stdev
    # Annualize Sharpe ratio
    sharper = math.sqrt(252)*sharper
    return sharper
# end calc_sharpe



## Load OHLC data from CSV file
# For example:
# ohlc = read_csv('/Users/jerzy/Develop/data/BTC_minute.csv')

def read_csv(filename):
    print("Loading data from: ", filename)
    ohlc = pd.read_csv(filename)
    ohlc.set_index('Date', inplace=True)
    ohlc.index = pd.to_datetime(ohlc.index, utc=True)
    return ohlc
# end read_csv


## Download OHLC time series from Polygon

# Set Polygon key - angry_hoover
polygon_key = "SDpnrBpiRzONMJdl48r6dOo0_mjmCu6r"

## Define exception handler function
def CatchException():
    exc_type, exc_obj, tb = sys.exc_info()
    f_err = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f_err.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f_err.f_globals)
    print ('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))


## get_symbol() downloads data from Polygon and returns an OHLC data frame
def get_symbol(symbol, startd, endd, range='day', polygon_key=polygon_key):
    print("Downloading", symbol)
    getstring = f'https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/{range}/{startd}/{endd}?adjusted=true&sort=asc&limit=50000&apiKey={polygon_key}'
    # Download the data from url
    response = requests.get(getstring)
    # Coerce url response to json
    jayson = response.json()
    try:
        bardata      = jayson['results']
        ticker       = jayson['ticker']
        queryCount   = jayson['queryCount']
        resultsCount = jayson['resultsCount']
        adjusted     = jayson['adjusted']
    except KeyError:
        pass
    except NameError:
        pass
    except:
        queryCount = 0
        CatchException()
        pass
    # Coerce json to data frame to OHLC data
    if queryCount > 1:
        ohlc = pd.DataFrame(bardata)
        # Create Date column equal to datetime - Polygon timestamp is in milliseconds
        ohlc["Date"] = pd.to_datetime(ohlc.t, unit='ms', utc=True)
        # Coerce column of type datetime to type date
        if (range == 'day'):
          ohlc.Date = ohlc.Date.dt.date
        # Convert Date column to ohlc index
        ohlc.set_index('Date', inplace=True)
        # Change time zone - doesn't work as expected
        # ohlc = ohlc.tz_localize('US/Eastern')
        # Drop columns
        ohlc.drop(columns=['n'], inplace=True)
        # Rename and rearrange columns
        ohlc.rename(columns={'t': 'Seconds', 'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume', 'vw': 'VWAP'}, inplace=True)
        ohlc = ohlc[['Seconds', 'Open', 'High', 'Low', 'Close', 'Volume', 'VWAP']]
        # Convert from milliseconds to seconds
        ohlc.Seconds = ohlc.Seconds / 1000
    # Return OHLC data
    return ohlc
# end get_symbol


