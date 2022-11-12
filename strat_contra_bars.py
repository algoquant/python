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

# ohlc = pd.read_csv("/Volumes/external/Develop/data/SP500_2020/GOOGL.csv", parse_dates=True, date_parser=pd.to_datetime, index_col="index")
symbol = "SPY"
ohlc = pd.read_csv("/Users/jerzy/Develop/data/SPY_minute.csv", parse_dates=True, date_parser=pd.to_datetime, index_col="Date")
# Rename columns
# ohlc.columns = ["Open", "High", "Low", "Close", "Volume"]

# Calculate the fast and slow-window simple moving averages
# mafast = ohlc.Close.rolling(window=20).mean()
# maslow = ohlc.Close.rolling(window=100).mean()
mafast = ohlc.Close.ewm(span=30, adjust=False).mean()
maslow = ohlc.Close.ewm(span=100, adjust=False).mean()

startd = "2022-07-29"
endd = "2022-08-25"

# Create plot objects
fig, ax = plt.subplots(figsize = (16, 9))

# Add plot objects
ax.plot(ohlc.loc[startd:endd, :].index, ohlc.loc[startd:endd, "Close"], label = symbol, linewidth = 2, color = "red")
ax.plot(maslow.loc[startd:endd].index, maslow.loc[startd:endd], label = "100-day EWMA", linewidth = 2, color = "green")
ax.plot(mafast.loc[startd:endd].index, mafast.loc[startd:endd], label = "30-day EWMA", linewidth = 2, color = "blue")
ax.set_ylabel("Price in $", size = 14)

# Add legend
legendo = ax.legend(loc="best", prop=dict(size=16))
# legendo.get_frame().set_facecolor("grey")

for line in legendo.get_lines():
    line.set_linewidth(10)

# Render the plot
plt.show()


## Simulate a Moving Average Crossover Strategy

# Calculate rolling VWAP
vwap = ohlc.Close
volumev = ohlc.Volume
vwap = vwap * volumev
vwap = vwap.rolling(window=150).sum()
volumev = volumev.rolling(window=150).sum()
vwap = vwap/volumev

# Calculate differences between the prices and the VWAP timeseries
posit = ohlc.Close - vwap
# Positions are equal to the sign of the differences
posit = posit.apply(np.sign)
# Lag the positions by 1 period
posit = posit.shift(1)

# Calculate asset log returns
retsp = np.log(ohlc.Close).diff()

# Calculate cumulative strategy returns
retstrat = posit*retsp
retsumstrat = retstrat.cumsum()
retsum = retsp.cumsum()

# Create plot objects for plotting in two panels
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18))

# Plot strategy cumulative returns
ax1.plot(ohlc.index, retsum, label = symbol, linewidth = 2, color = "b")
ax1.plot(ohlc.index, retsumstrat, label = "Strategy", linewidth = 2, color = "r")
ax1.set_ylabel("Cumulative log returns", size = 14)

# Add legend
legendo = ax1.legend(loc="best", prop=dict(size=16))
for line in legendo.get_lines():
    line.set_linewidth(10)

# Plot strategy positions
ax2.plot(ohlc.index, posit, label="Trading Positions")
ax2.set_ylabel("Trading Positions", size = 14)

# Render the plot
plt.show()
