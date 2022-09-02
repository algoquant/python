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
todayd = datetime.date.today()
endd = todayd
print("Today is:", todayd)

# Create a date from integers
startd = datetime.date(2000, 1, 1)
print("Start date is:", startd)

# range = "minute"
range = "day"

# Define the list of symbols to download
symbols = ["SPY", "VXX", "SVXY"]

## Download stock prices for all the symbols in a loop
print("Downloading stock prices for the symbols: ", symbols)
for symbol in symbols:
    # Download stock prices from Polygon for the symbol
    ohlc = get_symbol(symbol=symbol, startd=startd, endd=endd, range=range)
    # Write OHLC data to csv file
    filename = "/Users/jerzy/Develop/data/" + symbol + "_" + range + ".csv"
    ohlc.to_csv(filename)
    print("Finished downloading", symbol)

print("Finished downloading stock prices for all the symbols")
