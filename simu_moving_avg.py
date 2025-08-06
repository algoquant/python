#!/usr/bin/env python
# coding: utf-8

"""
This is a script for simulating VWAP moving average crossover strategy.
https://www.learndatasci.com/tutorials/python-finance-part-yahoo-finance-api-pandas-matplotlib/
https://www.learndatasci.com/tutorials/python-finance-part-2-intro-quantitative-trading-strategies/
https://www.learndatasci.com/tutorials/python-finance-part-3-moving-average-trading-strategy/
"""

# Import packages
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import matplotlib.pyplot as plt
# import mplfinance as mpf
# from utils import read_csv


## Load OHLC data from csv file and format the time index

# Load OHLC data from csv file - the time index is formatted inside read_csv()
symbol = "SPY"
# range = "minute"
range = "daily"
filename = "/Users/jerzy/Develop/data/" + symbol + "_" + range + ".csv"
ohlc = pd.read_csv(filename, parse_dates=True, date_format="%Y-%m-%d", index_col="Date")
# isinstance(ohlc.index, pd.DatetimeIndex)
# ohlc.index = pd.to_datetime(ohlc.index)

# ohlc = pd.read_csv("/Users/jerzy/Develop/data/etfdaily/GOOGL.csv", parse_dates=True, index_col="Index")
# Rename the columns
ohlc.columns = ["Open", "High", "Low", "Close", "Volume"]
# Log of Open, High, Low, Close prices
ohlc.iloc[:,0:4] = np.log(ohlc.iloc[:,0:4])

# Calculate the Close price and date vector
closep = ohlc.Close
datev = ohlc.index
# Check if closep is numeric
print("Is closep numeric?", pd.api.types.is_numeric_dtype(closep))
print("Is ohlc a DataFrame?", isinstance(ohlc, pd.DataFrame))
print("Is closep a DataFrame?", isinstance(closep, pd.DataFrame))

# matplotlib of SPY
plt.figure(figsize=(10, 5))
plt.plot(closep.index, closep, label="SPY")
plt.xlabel("Date")
plt.ylabel("SPY")
plt.title("Time Series Plot")
plt.legend()
plt.show()


# Plotly of SPY
plotfig = go.Figure()
plotfig.add_trace(go.Scatter(x=closep.index, y=closep, mode="lines", name="Time Series Data"))
plotfig.update_layout(title="SPY Series Plot", xaxis_title="Date", yaxis_title="Log Price")
# Save the plot as an HTML file
plotfig.write_html("/Users/jerzy/Develop/Python/figure.html")
# Render the plot - but it doesn't open the browser and returns the figure object
plotfig.show()


## Plotly of dual fast and slow moving averages

# Calculate the fast and slow moving averages
mafast = closep.ewm(span=30, adjust=False).mean()
maslow = closep.ewm(span=100, adjust=False).mean()

# Create empty graph object
plotfig = go.Figure()
# Add trace for Close price
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=closep,
  name=symbol, line=dict(color="blue")))
# Add trace for slow moving average
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=maslow,
  name="Slow Moving Average", line=dict(color="green")))
# Add trace for fast moving average
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=mafast,
  name="Fast Moving Average", line=dict(color="orange")))
# Hide non-market periods
# plotfig = plotfig.update_xaxes(rangebreaks=[
#   dict(bounds=["sat", "mon"]), # Hide weekends
#   dict(bounds=[17, 9], pattern="hour"),  # Hide overnight hours 5PM to 9AM
#   # dict(values=["2015-12-25", "2016-01-01"])  # Hide Christmas and New Year"s
# ])
# Customize legend
plotfig = plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal", 
  itemsizing="constant", font=dict(family="sans-serif", size=18, color="black")))
# Save the plot as an HTML file
plotfig.write_html("/Users/jerzy/Develop/Python/figure.html")
# Render the plot - but it doesn't open the browser and returns the figure object
plotfig.show()


## Simulate a VWAP Moving Average Crossover Strategy

# Calculate rolling VWAP
vwap = ohlc.loc[:, "VWAP"]
volumev = ohlc.Volume
vwap = vwap*volumev
vwap = vwap.rolling(window=150).sum()
volumev = volumev.rolling(window=150).sum()
vwap = vwap/volumev

# Calculate differences between the prices and the VWAP timeseries
posit = closep - vwap
# Positions are equal to the sign of the differences
posit = posit.apply(np.sign)
# Lag the positions by 1 period
posit = posit.shift(1)

# Calculate the log percentage returns
retsp = np.log(closep).diff()

# Calculate the cumulative strategy returns
retstrat = posit*retsp
retsumstrat = retstrat.cumsum()
retsum = retsp.cumsum()


## Plot the strategy returns

# Create empty graph object
plotfig = go.Figure()
# Add trace for symbol
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=retsum,
  name=symbol, line=dict(color="blue")))
# Add trace for strategy
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=retsumstrat,
  name="Strategy", line=dict(color="orange")))
# Hide non-market periods
plotfig = plotfig.update_xaxes(rangebreaks=[
  dict(bounds=["sat", "mon"]), # Hide weekends
  # dict(bounds=[17, 9], pattern="hour"),  # Hide overnight hours 5PM to 9AM
  # dict(values=["2015-12-25", "2016-01-01"])  # Hide Christmas and New Year"s
])
# Customize legend
plotfig = plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal", 
  itemsizing="constant", font=dict(family="sans-serif", size=18, color="black")))
# Save the plot as an HTML file
plotfig.write_html("/Users/jerzy/Develop/Python/figure.html", auto_open=True)
# Render the plot - but it doesn't open the browser and returns the figure object
plotfig.show()


### Old version
# Create plot objects for plotting in two panels
# plotfig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18))

# Plot strategy cumulative returns
# ax1.plot(datev, retsum, label = "GOOG", linewidth = 2, color = "b")
# ax1.plot(datev, retsumstrat, label = "Strategy", linewidth = 2, color = "r")
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
