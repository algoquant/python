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
import plotly.express as px
# import matplotlib.pyplot as plt
# import mplfinance as mpf
from utils import read_csv


## Load OHLC data from csv file and format the time index

# Load OHLC data from csv file - the time index is formatted inside read_csv()
symbol = "SPY"
ohlc = read_csv("/Users/jerzy/Develop/data/" + symbol + "_minute.csv")
# ohlc = pd.read_csv("C:/Develop/data/SP500_2020/GOOGL.csv", parse_dates=True, date_parser=pd.to_datetime, index_col="index")
# Rename columns
# ohlc.columns = ["Open", "High", "Low", "Close", "Volume"]

# Calculate the fast and slow moving averages
closep = ohlc.Close
datev = ohlc.index
mafast = closep.ewm(span=30, adjust=False).mean()
maslow = closep.ewm(span=100, adjust=False).mean()

# startd = "2019-01-01"
# endd = "2020-04-17"
startd = datev.min()
endd = datev.max()

# Create empty graph object
plotfig = go.Figure()
# Add trace for Close price
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=closep,
  name=symbol, line=dict(color="blue")))
# Add trace for slow moving average
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=maslow[datev],
  name="Slow Moving Average", line=dict(color="green")))
# Add trace for fast moving average
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=mafast[datev],
  name="Fast Moving Average", line=dict(color="orange")))
# Hide non-market periods
plotfig = plotfig.update_xaxes(rangebreaks=[
  dict(bounds=["sat", "mon"]), # Hide weekends
  dict(bounds=[17, 9], pattern="hour"),  # Hide overnight hours 5PM to 9AM
  # dict(values=["2015-12-25", "2016-01-01"])  # Hide Christmas and New Year's
])
# Customize legend
plotfig = plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal", 
  itemsizing="constant", font=dict(family="sans-serif", size=18, color="black")))
# Render the plot
plotfig.show()


## Simulate a Moving Average Crossover Strategy

# Calculate rolling VWAP
vwap = ohlc.Close
volumev = ohlc.Volume
vwap = vwap * volumev
vwap = vwap.rolling(window=150).sum()
volumev = volumev.rolling(window=150).sum()
vwap = vwap / volumev

# Calculate differences between the prices and the VWAP timeseries
posit = closep - vwap
# Positions are equal to the sign of the differences
posit = posit.apply(np.sign)
# Lag the positions by 1 period
posit = posit.shift(1)

# Calculate log asset returns
returnts = np.log(closep).diff()

# Calculate the cumulative strategy returns
strategy_returns = posit * returnts
strategy_cum_returns = strategy_returns.cumsum()
asset_cum_returns = returnts.cumsum()


## Plot the strategy returns

# Create empty graph object
plotfig = go.Figure()
# Add trace for symbol
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=asset_cum_returns[datev],
  name=symbol, line=dict(color="blue")))
# Add trace for strategy
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=strategy_cum_returns[datev],
  name="Strategy", line=dict(color="orange")))
# Hide non-market periods
plotfig = plotfig.update_xaxes(rangebreaks=[
  dict(bounds=["sat", "mon"]), # Hide weekends
  dict(bounds=[17, 9], pattern="hour"),  # Hide overnight hours 5PM to 9AM
  # dict(values=["2015-12-25", "2016-01-01"])  # Hide Christmas and New Year's
])
# Customize legend
plotfig = plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal", 
  itemsizing="constant", font=dict(family="sans-serif", size=18, color="black")))
# Render the plot
plotfig.show()


### Old version
# Create plot objects for plotting in two panels
# fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18))

# Plot strategy cumulative returns
# ax1.plot(datev, asset_cum_returns, label = "GOOG", linewidth = 2, color = "b")
# ax1.plot(datev, strategy_cum_returns, label = "Strategy", linewidth = 2, color = "r")
# ax1.set_ylabel("Cumulative log returns", size = 14)

# Add legend
# legendo = ax1.legend(loc="best", prop=dict(size=16))
# for line in legendo.get_lines():
#     line.set_linewidth(10)

# Plot strategy positions
# ax2.plot(datev, posit, label="Trading Positions")
# ax2.set_ylabel("Trading Positions", size = 14)

# Render the plot
# plt.show()
