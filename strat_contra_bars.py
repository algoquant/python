#!/usr/bin/env python
# coding: utf-8

"""
Script for VWAP Moving Average Crossover Strategy
https://www.learndatasci.com/tutorials/python-finance-part-yahoo-finance-api-pandas-matplotlib/
https://www.learndatasci.com/tutorials/python-finance-part-2-intro-quantitative-trading-strategies/
https://www.learndatasci.com/tutorials/python-finance-part-3-moving-average-trading-strategy/
"""

# Import packages
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
# import mplfinance as mpf


## Load OHLC data from csv file and format the time index

# ohlc = pd.read_csv("/Volumes/external/Develop/data/SP500_2020/GOOGL.csv", parse_dates=True, date_format=pd.to_datetime, index_col="index")
symboln = "SPY"
filename = "/Users/jerzy/Develop/data/etfdaily/" + symboln + "_daily" + ".csv"
ohlc = pd.read_csv(filename, parse_dates=["Index"])
# ohlc = pd.read_csv(filename, parse_dates=True, date_format=pd.to_datetime, index_col="Date")
# Set the time index as the data frame index
ohlc.set_index("Index", inplace=True)
# Log of OHLC prices
ohlc.iloc[:, 0:4] = np.log(ohlc.iloc[:, 0:4])
# closep = ohlc[symboln + ".Close"]
# Rename columns
ohlc.columns = ["Open", "High", "Low", "Close", "Volume"]
closep = ohlc.Close

# Calculate the fast and slow-window simple moving averages
# mafast = closep.rolling(window=20).mean()
# maslow = closep.rolling(window=100).mean()
mafast = closep.ewm(span=30, adjust=False).mean()
maslow = closep.ewm(span=100, adjust=False).mean()

startd = "2010-07-29"
endd = "2026-08-25"
datev = ohlc.loc[startd:endd].index

# Create plot objects
fig, ax = plt.subplots(figsize = (16, 9))

# Add plot objects
ax.plot(datev, closep.loc[startd:endd], label = symboln, linewidth = 2, color = "red")
ax.plot(datev, maslow.loc[startd:endd], label = "100-day EWMA", linewidth = 2, color = "green")
ax.plot(datev, mafast.loc[startd:endd], label = "30-day EWMA", linewidth = 2, color = "blue")
ax.set_ylabel("Log Price", size = 14)

# Add legend
legendd = ax.legend(loc="best", prop=dict(size=16))
# legendd.get_frame().set_facecolor("grey")

# for line in legendd.get_lines():
#     line.set_linewidth(10)

# Render the plot
plt.show()


## Simulate a Moving Average Crossover Strategy

# Calculate rolling VWAP
vwap = closep
volumev = ohlc.Volume
vwap = vwap*volumev
vwap = vwap.rolling(window=150).sum()
volumev = volumev.rolling(window=150).sum()
vwap = vwap/volumev

# Calculate differences between the prices and the VWAP timeseries
posv = closep - vwap
# Positions are equal to the sign of the differences
posv = posv.apply(np.sign)
# Lag the positions by 1 period
posv = posv.shift(1)

# Calculate asset log returns
retp = closep.diff()

# Calculate cumulative strategy returns
retstrat = posv*retp
retsumstrat = retstrat.cumsum()
retsum = retp.cumsum()

# Create plot objects for plotting in two panels
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

# Plot strategy cumulative returns
ax1.plot(ohlc.index, retsum, label = symboln, linewidth = 2, color = "b")
ax1.plot(ohlc.index, retsumstrat, label = "Strategy", linewidth = 2, color = "r")
ax1.set_ylabel("Cumulative log returns", size = 14)

# Add legend
legendd = ax1.legend(loc="best", prop=dict(size=16))
# for line in legendd.get_lines():
#     line.set_linewidth(10)

# Plot strategy positions
ax2.plot(ohlc.index, posv, label="Trading Positions")
ax2.set_ylabel("Trading Positions", size = 14)

# Render the plot
plt.show()
