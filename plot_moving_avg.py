#!/usr/bin/env python
# coding: utf-8

"""
Script for loading OHLC data from a CSV file and plotting 
a candlestick plot and volume plot in two panes.

"""

# Import packages
import pandas as pd
# Print pandas version
print(pd.__version__)
import matplotlib.pyplot as plt
import mplfinance as mpf
# Print mplfinance version
print(mpf.__version__)
# from mplfinance import candlestick_ohlc
# import matplotlib.dates as mpdates

# import plotly as py
# plotly.express for time series
import plotly.express as px
from plotly.offline import plot


## Load OHLC data from csv file and format the index
tseries = pd.read_csv("/Users/jerzy/Develop/data/etfdaily/SPY_daily.csv", parse_dates=True, date_format="%Y-%m-%d", index_col="Index")
tseries.index = pd.to_datetime(tseries.index)
isinstance(tseries.index, pd.DatetimeIndex)

type(tseries)
tseries.dtypes
# Print column names
tseries.columns
# Rename columns
tseries.columns = ["Open", "High", "Low", "Close", "Volume"]
# tseries = tseries[["Open", "High", "Low", "Close"]]
tseries.shape
tseries.iloc[0:5, :]
tseries.head()
tseries.tail()
# Extract time index
indeks = tseries.index

# Select Close prices
closep = tseries["Close"]
# Or
# closep = tseries.iloc[:, 3]
type(closep)

ema15 = closep.ewm(span=15).mean()

# Set plot style
plt.style.use("fivethirtyeight")
# Set plot dimensions
plt.figure(figsize = (12, 6))
# Plot price and SMA lines:
plt.plot(closep, label="SPY", linewidth = 2)
plt.plot(ema15, label="15 day rolling SMA", linewidth = 1.5)
# Add title and labeles on the axes, making legend visible:
plt.xlabel("Date")
plt.ylabel("Adjusted closing price ($)")
plt.title("Price with a Simple Moving Average")
plt.legend()
plt.show()


## Plotly dynamic interactive time series plots using plotly.express
# https://plotly.com/python/time-series/

# Import built-in time series data frame
# dframe = px.data.stocks()
# Create line time series of prices from data frame
plotfig = px.line(closep["2020"])
plotfig.update_layout(title="SPY Price", yaxis_title="Price", xaxis_rangeslider_visible=True)
# Plot interactive plot in browser and save to html file
plot(plotfig, filename="stock_prices.html", auto_open=True)
# Show the plot
# plotfig.show()

# Create bar plot of volumes
volumev = tseries["Volume"]
plotfig = px.bar(volumev["2020"])
plotfig.update_layout(title="SPY Volume", yaxis_title="Volume", xaxis_rangeslider_visible=False)
# Plot interactive plot in browser and save to html file
plot(plotfig, filename="stock_volumes.html", auto_open=True)


## Plotly dynamic interactive time series plots using plotly.graph_objects

import plotly.graph_objects as go

# Select time slice of data
pricev = tseries["2019":"2020"]
# Create plotly graph object from data frame
plotfig = go.Figure([go.Scatter(x=pricev.index, y=pricev["Close"])])
plotfig.update_layout(title="SPY", yaxis_title="Price", xaxis_rangeslider_visible=False)
# Plot interactive plot in browser and save to html file
plot(plotfig, filename="stock_prices.html", auto_open=True)


## Plotly with prices and volumes using plotly subplots
# https://stackoverflow.com/questions/62287001/how-to-overlay-two-plots-in-same-figure-in-plotly

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Select time slice of data
pricev = tseries["2019":"2020"]
# Create line of prices from data frame
# trace1 = go.Scatter(x=pricev.index, y=pricev["Close"], name="Prices", showlegend=False)
# Create candlestick time series from data frame
trace1 = go.Candlestick(x=pricev.index,
                open=pricev.Open, high=pricev.High, low=pricev.Low, close=pricev.Close, 
                name="OHLC Prices", showlegend=False)
# Create bar plot of volumes
trace2 = go.Bar(x=pricev.index, y=pricev["Volume"], name="Volumes", showlegend=False)
# Create empty plot layout
plotfig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        subplot_titles=["Price", "Volume"], row_heights=[450, 150])
# Add plots to layout
plotfig.add_trace(trace1, row=1, col=1)
plotfig.add_trace(trace2, row=2, col=1)
# Add titles and reduce margins
plotfig.update_layout(title="SPY Price and Volume", 
                       # yaxis_title=["Price", "Volume"], 
                      margin=dict(l=0, r=10, b=0, t=30), 
                      xaxis_rangeslider_visible=True)
# Plot interactive plot in browser and save to html file
plot(plotfig, filename="stock_ohlc_volume.html", auto_open=True)


## Attempt at dash plot - doesn"t do anything

import dash
import dash_core_components as dcc
import dash_html_components as html

app = dash.Dash()
app.layout = html.Div([
    dcc.Graph(figure=plotfig)
])

# Turn off reloader if inside Jupyter
app.run_server(debug=True, use_reloader=False)

# End dash plot - doesn"t do anything


## Matplotlib static candlestick plots

# Select time slice of data
pricev = tseries["2019":"2020"]

# Calculate the short and long-window simple moving averages
short_rolling = tseries.rolling(window=20).mean()
long_rolling = tseries.rolling(window=100).mean()

startd = "2019-01-01"
endd = "2020-04-17"

fig, ax = plt.subplots(figsize=(16,9))

ax.plot(tseries.loc[startd:endd, :].index, tseries.loc[startd:endd, :], label="Close")
ax.plot(long_rolling.loc[startd:endd, :].index, long_rolling.loc[startd:endd, :], label = "100-day SMA")
ax.plot(short_rolling.loc[startd:endd, :].index, short_rolling.loc[startd:endd, :], label = "20-day SMA")

ax.legend(loc="best")
ax.set_ylabel("Price in $")
# ax.xaxis.set_major_formatter(my_year_month_fmt)


# ema15 = pricev["2020"]["Close"].ewm(span=15).mean()
# fig, ax = plt.subplots(figsize = (12,6))


# plt.style.use("dark_background") 
mpf.plot(pricev["2014":"2020"], type="candle", style="charles", title="SPY")
# Or with moving average
mpf.plot(pricev["2020"], type="candle", figratio=(18,10), mav=(11, 22), style="charles", title="SPY")
# Or with volume
mpf.plot(pricev["2020"], type="candle", style="charles", title="SPY", 
         volume=True, ylabel="Price", ylabel_lower="Volume")
# Or save to file
mpf.plot(pricev["2014":"2020"], type="candle", style="charles", title="SPY",
            ylabel="Price", ylabel_lower="Shares \nTraded", volume=True, 
            mav=(3,6,9), 
            savefig="test-mplfiance.png")


# Create Subplots 
# fig, ax = plt.subplots() 
  
# Plot the data 
# mpf.candlestick_ohlc(ax, tseries.values, width = 0.6, 
                 # colorup = "green", colordown = "red",  
                 # alpha = 0.8) 
  
# allow grid 
# ax.grid(True) 
  
# Setting labels  
# ax.set_xlabel("Date") 
# ax.set_ylabel("Price") 
  
# setting title 
# plt.title("Prices For the Period 01-07-2020 to 15-07-2020") 
  
# Formatting Date 
# date_format = mpdates.DateFormatter("%d-%m-%Y") 
# ax.xaxis.set_major_formatter(date_format) 
# fig.autofmt_xdate() 
  
# fig.tight_layout() 
  
# Show the plot
# plt.show()

