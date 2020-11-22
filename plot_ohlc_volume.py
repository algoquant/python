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
# import matplotlib.pyplot as plt
import mplfinance as mpf
# Print mplfinance version
print(mpf.__version__)
# from mplfinance import candlestick_ohlc
# import matplotlib.dates as mpdates

# import plotly as py
# plotly.express for time series
import plotly.express as px
from plotly.offline import plot


## Load OHLC data from csv file and format the time index

se_ries = pd.read_csv('C:/Develop/data/SP500_2020/GOOGL.csv', parse_dates=True, date_parser=pd.to_datetime, index_col='index')

# Print column names
se_ries.columns
# Rename columns
se_ries.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
se_ries.head()
se_ries.tail()

# Get column types
type(se_ries)
se_ries.dtypes

# Get dimensions
se_ries.shape

# Subset
se_ries.iloc[0:5, :]
# Extract time index
in_dex = se_ries.index

# Select Close prices
clos_e = se_ries['Close']
# Or
# clos_e = se_ries.iloc[:, 3]
type(clos_e)


## Plotly dynamic interactive time series plots using plotly.express
# https://plotly.com/python/time-series/

# Import built-in time series data frame
# fram_e = px.data.stocks()
# Create line time series of prices from data frame
fig_ure = px.line(clos_e['2020'])
fig_ure.update_layout(title='GOOG Price', yaxis_title='Price', xaxis_rangeslider_visible=True)
# Plot interactive plot in browser and save to html file
plot(fig_ure, filename='stock_prices.html', auto_open=True)
# Show the plot - works only in Jupyter notebook
# fig_ure.show()

# Create bar plot of volumes
vol_ume = se_ries['Volume']
fig_ure = px.bar(vol_ume['2020'])
fig_ure.update_layout(title='GOOG Volume', yaxis_title='Volume', xaxis_rangeslider_visible=False)
# Plot interactive plot in browser and save to html file
plot(fig_ure, filename='stock_volumes.html', auto_open=True)


## Plotly dynamic interactive time series plots using plotly.graph_objects

import plotly.graph_objects as go

# Select time slice of data
slic_e = se_ries['2019':'2020']
# Create plotly graph object from data frame
fig_ure = go.Figure([go.Scatter(x=slic_e.index, y=slic_e['Close'])])
fig_ure.update_layout(title='GOOG', yaxis_title='Price', xaxis_rangeslider_visible=False)
# Plot interactive plot in browser and save to html file
plot(fig_ure, filename='stock_prices.html', auto_open=True)


## Plotly with prices and volumes using plotly subplots
# https://stackoverflow.com/questions/62287001/how-to-overlay-two-plots-in-same-figure-in-plotly

import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Select time slice of data
slic_e = se_ries['2019':'2020']
# Create line of prices from data frame
# trace_1 = go.Scatter(x=slic_e.index, y=slic_e['Close'], name='Prices', showlegend=False)
# Create candlestick time series from data frame
trace_1 = go.Candlestick(x=slic_e.index,
                open=slic_e.Open, high=slic_e.High, low=slic_e.Low, close=slic_e.Close, 
                name='OHLC Prices', showlegend=False)
# Create bar plot of volumes
trace_2 = go.Bar(x=slic_e.index, y=slic_e['Volume'], name='Volumes', showlegend=False)
# Create empty plot layout
fig_ure = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        subplot_titles=['Price', 'Volume'], row_heights=[450, 150])
# Add plots to layout
fig_ure.add_trace(trace_1, row=1, col=1)
fig_ure.add_trace(trace_2, row=2, col=1)
# Add titles and reduce margins
fig_ure.update_layout(title='GOOG Price and Volume', 
                       # yaxis_title=['Price', 'Volume'], 
                      margin=dict(l=0, r=10, b=0, t=30), 
                      xaxis_rangeslider_visible=True)
# Plot interactive plot in browser and save to html file
plot(fig_ure, filename='stock_ohlc_volume.html', auto_open=True)


## Attempt at dash plot - doesn't do anything

import dash
import dash_core_components as dcc
import dash_html_components as html

app = dash.Dash()
app.layout = html.Div([
    dcc.Graph(figure=fig_ure)
])

# Turn off reloader if inside Jupyter
app.run_server(debug=True, use_reloader=False)

# End dash plot - doesn't do anything


## Matplotlib static candlestick plots
# plt.style.use('dark_background') 
mpf.plot(se_ries['2014':'2020'], type='candle', style='charles', title='GOOG')
# Or with moving average
mpf.plot(se_ries['2020'], type='candle', figratio=(18,10), mav=(11, 22), style='charles', title='GOOG')
# Or with volume
mpf.plot(se_ries['2020'], type='candle', style='charles', title='GOOG', 
         volume=True, ylabel='Price', ylabel_lower='Volume')
# Or save to file
mpf.plot(se_ries['2014':'2020'], type='candle', style='charles', title='GOOG',
            ylabel='Price', ylabel_lower='Shares \nTraded', volume=True, 
            mav=(3,6,9), 
            savefig='test-mplfiance.png')

# ema_15 = se_ries['2020']['Close'].ewm(span=15).mean()
# fig, ax = plt.subplots(figsize = (12,6))


# Create Subplots 
# fig, ax = plt.subplots() 
  
# Plot the data 
# mpf.candlestick_ohlc(ax, se_ries.values, width = 0.6, 
                 # colorup = 'green', colordown = 'red',  
                 # alpha = 0.8) 
  
# allow grid 
# ax.grid(True) 

# Setting labels  
# ax.set_xlabel('Date') 
# ax.set_ylabel('Price') 

# setting title 
# plt.title('Prices For the Period 01-07-2020 to 15-07-2020') 

# Formatting Date 
# date_format = mpdates.DateFormatter('%d-%m-%Y') 
# ax.xaxis.set_major_formatter(date_format) 
# fig.autofmt_xdate() 

# fig.tight_layout() 

# Show the plot - works in Jupyter notebook
# plt.show()

