#!/usr/bin/env python
# coding: utf-8

"""
Script for loading OHLC data from a CSV file and plotting 
a candlestick plot and volume plot in two panes.

"""

# Import packages 
import numpy as np
import pandas as pd
# Print pandas version
print(pd.__version__)

## Load OHLC data from csv file and format the time index

symboln = "SPY"
filename = "/Users/jerzy/Develop/data/etfdaily/" + symboln + "_daily" + ".csv"
ohlc = pd.read_csv(filename, parse_dates=True, index_col="Index")

# Print column names
ohlc.columns
# Rename columns
ohlc.columns = ["Open", "High", "Low", "Close", "Volume"]
ohlc.head()
ohlc.tail()

# Log of OHLC prices
ohlc.iloc[:, 0:4] = np.log(ohlc.iloc[:, 0:4])

# Get ohlc dimensions (without time index)
ohlc.shape
# Get ohlc type
type(ohlc)
# Get column types
ohlc.dtypes

# Select first 6 rows
ohlc.iloc[0:5, :]
# Extract time index
indeks = ohlc.index

# Select series of Close prices
closep = ohlc["Close"]
# Or
# closep = ohlc.iloc[:, 3]
type(closep)


## Plotly dynamic interactive time series plots using plotly.express
# https://plotly.com/python/time-series/

# import plotly as py
# plotly.express for time series
import plotly.express as px
from plotly.offline import plot

# Import built-in time series data frame
# dframe = px.data.stocks()
# Create line time series of prices from data frame
plotfig = px.line(closep["2020"])
stuff = plotfig.update_layout(title="GOOG Price", yaxis_title="Price", xaxis_rangeslider_visible=True)
# Plot interactive plot in browser and save to html file
plot(plotfig, filename="stock_prices.html", auto_open=True)
# Show the plot - works only in Jupyter notebook
# plotfig.show()

# Create bar plot of volumes
plotfig = px.bar(ohlc["Volume"]["2020"])
stuff = plotfig.update_layout(title="GOOG Volume", yaxis_title="Volume", xaxis_rangeslider_visible=False)
# Plot interactive plot in browser and save to html file
plot(plotfig, filename="stock_volumes.html", auto_open=True)


## Plotly dynamic interactive time series plots using plotly.graph_objects

import plotly.graph_objects as go

# Select time slice of data
ohlcsub = ohlc["2019":"2020"]
# Create plotly graph object from data frame
plotfig = go.Figure([go.Scatter(x=ohlcsub.index, y=ohlcsub["Close"])])
stuff = plotfig.update_layout(title=symboln, yaxis_title="Price", xaxis_rangeslider_visible=False)
# Plot interactive plot in browser and save to html file
plot(plotfig, filename="stock_prices.html", auto_open=True)


## Plotly simple candlestick

plotfig = go.Figure(data=[go.Candlestick(x=ohlcsub.index,
                open=ohlcsub.Open, high=ohlcsub.High, low=ohlcsub.Low, close=ohlcsub.Close, 
                name="OHLC Prices", showlegend=False)])
stuff = plotfig.update_layout(title="OHLC Prices", yaxis_title="Prices", xaxis_rangeslider_visible=False)
# Plot interactive plot in browser and save to html file
plot(plotfig, filename="stock_candlesticks.html", auto_open=True)


## Plotly candlestick with volumes using plotly subplots
# https://stackoverflow.com/questions/62287001/how-to-overlay-two-plots-in-same-figure-in-plotly

from plotly.subplots import make_subplots

# Select time slice of data
ohlcsub = ohlc["2019":"2020"]
# Create line of prices from data frame
# trace_1 = go.Scatter(x=ohlcsub.index, y=ohlcsub["Close"], name="Prices", showlegend=False)
# Create candlestick time series from data frame
trace_1 = go.Candlestick(x=ohlcsub.index,
                open=ohlcsub.Open, high=ohlcsub.High, low=ohlcsub.Low, close=ohlcsub.Close, 
                name="OHLC Prices", showlegend=False)
# Create bar plot of volumes
trace_2 = go.Bar(x=ohlcsub.index, y=ohlcsub["Volume"], name="Volumes", showlegend=False)
# Create empty plot layout
plotfig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        subplot_titles=["Price", "Volume"], row_heights=[450, 150])
# Add plots to layout
stuff = plotfig.add_trace(trace_1, row=1, col=1)
stuff = plotfig.add_trace(trace_2, row=2, col=1)
# Add titles and reduce margins
stuff = plotfig.update_layout(title="GOOG Price and Volume", 
                       # yaxis_title=["Price", "Volume"], 
                      margin=dict(l=0, r=10, b=0, t=30), 
                      xaxis_rangeslider_visible=True)
# stuff = plotfig.update_xaxes(automargin=TRUE)
# Plot interactive plot in browser and save to html file
plot(plotfig, filename="stock_ohlc_volume.html", auto_open=True)


## Create a dash app with simple candlestick in browser
# https://plotly.com/python/candlestick-charts/

import dash
from dash import dcc
from dash import html

plotfig = go.Figure(data=[go.Candlestick(x=ohlcsub.index,
                open=ohlcsub.Open, high=ohlcsub.High, low=ohlcsub.Low, close=ohlcsub.Close, 
                name="OHLC Prices", showlegend=False)])
stuff = plotfig.update_layout(title="OHLC Prices", yaxis_title="Prices", xaxis_rangeslider_visible=False)

app = dash.Dash()
app.layout = html.Div([
    dcc.Graph(figure=plotfig)
])

# Turn off reloader if inside Jupyter
app.run_server(debug=True, use_reloader=False)

# End dash app


## Matplotlib static candlestick plots

# import matplotlib.pyplot as plt
import mplfinance as mpf
# Print mplfinance version
print(mpf.__version__)
# from mplfinance import candlestick_ohlc
# import matplotlib.dates as mpdates


# plt.style.use("dark_background") 
mpf.plot(ohlc.loc["2014":"2020"], type="candle", style="charles", title=symboln)
# Or with moving average
mpf.plot(ohlc.loc["2020"], type="candle", figratio=(18,10), mav=(11, 22), 
         mavcolors=["red", "green"], 
         style="charles", title=symboln)
# Or with volume
mpf.plot(ohlc.loc["2020-01":"2020-05"], type="candle", style="charles", title=symboln, 
         volume=True, ylabel="Price", ylabel_lower="Volume")
# Or save to file
mpf.plot(ohlc["2014":"2020"], type="candle", style="charles", title=symboln,
            ylabel="Price", ylabel_lower="Shares \nTraded", volume=True, 
            mav=(3,6,9), 
            savefig="test-mplfiance.png")

# ema15 = ohlc.loc["2020"]["Close"].ewm(span=15).mean()
# fig, ax = plt.subplots(figsize = (12,6))


# Create Subplots 
# fig, ax = plt.subplots() 
  
# Plot the data 
# mpf.candlestick_ohlc(ax, ohlc.values, width = 0.6, 
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

# Show the plot - works in Jupyter notebook
# plt.show()

