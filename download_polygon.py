#!/usr/bin/env python
# coding: utf-8

""" Script for downloading stock prices from Polygon. """

## Import packages

# Packages for exception handler
import sys
import linecache

# Packages for download
import requests

# import numpy as np
import pandas as pd
# from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import datetime


## Define exception handler
def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f_err = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f_err.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f_err.f_globals)
    print ('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))



## Set time variables
# Get today's date
to_day = datetime.date.today()
end_date = to_day
print("Today is:", to_day)

# Create a date from integers
start_date = datetime.date(2000, 1, 1)
print("Start date is:", start_date)

# Set polygon_key
polygon_key = "0Q2f8j8CwAbdY4M8VYt_8pwdP0V4TunxbvRVC_" # NYU account
# range = "minute"
range = "day"

# Define the list of symbols to download
symbols = ["SPY", "VXX", "SVXY"]


for symbol in symbols:

    print("Downloading", symbol)

    getstring = f'https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/{range}/{start_date}/{end_date}?adjusted=true&sort=asc&limit=50000&apiKey={polygon_key}'
    # print(getstring)

    # Download the data from url
    response = requests.get(getstring)
    # print("Response:", resp.content)

    # Coerce url response to json
    jayson = response.json()
    # print("Response jayson:", jayson)

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
        PrintException()
        pass
    # print("ticker:", ticker, queryCount, resultsCount, adjusted)

    # Coerce json to data frame and write OHLC data to file
    if queryCount > 1:
        ohlc = pd.DataFrame(bardata)
        # Create Date column equal to datetime - Polygon timestamp is in milliseconds
        ohlc['Date'] = pd.to_datetime(ohlc['t'], unit='ms')
        # Coerce column of type datetime to type date
        ohlc['Date'] = ohlc['Date'].dt.date
        # Convert Date column to ohlc index
        ohlc.set_index('Date', inplace=True)
        # Change time zone - doesn't work as expected
        # ohlc = ohlc.tz_localize('US/Eastern')
        # Drop columns
        ohlc.drop(columns=['n'], inplace=True)
        # Rename and rearrange columns
        ohlc.rename(columns={'t': 'Seconds', 'o': 'Open', 'h': 'High', 'l': 'Low', 'c': 'Close', 'v': 'Volume', 'vw': 'VWAP'}, inplace=True)
        ohlc = ohlc[['Seconds', 'Open', 'High', 'Low', 'Close', 'Volume', 'VWAP']]
        # Write to csv file
        filename = "/Volumes/external/Develop/data/polygon/" + symbol + "_daily.csv"
        ohlc.to_csv(filename)

    print("Finished downloading", symbol)


print("Finished download")
