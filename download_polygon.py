#!/usr/bin/env python
# coding: utf-8

""" Script for downloading stock prices from Polygon. """

## Import packages

# Packages for exception handler
import sys
import linecache

# import numpy as np
import pandas as pd
# from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import datetime

from utils import get_symbol


## Set time variables
# Get today's date
to_day = datetime.date.today()
end_date = to_day
print("Today is:", to_day)

# Create a date from integers
start_date = datetime.date(2000, 1, 1)
print("Start date is:", start_date)

# range = "minute"
range = "day"

# Define the list of symbols to download
symbols = ["SPY", "VXX", "SVXY"]

## Download stock prices for all the symbols in a loop
print("Downloading stock prices for the symbols: ", symbols)
for symbol in symbols:
    # Download stock prices from Polygon for the symbol
    ohlc = get_symbol(symbol=symbol, start_date=start_date, end_date=end_date, range=range)
    # Write OHLC data to csv file
    filename = "/Users/jerzy/Develop/data/" + symbol + "_daily.csv"
    ohlc.to_csv(filename)
    print("Finished downloading", symbol)

print("Finished downloading stock prices for all the symbols")
