#!/usr/bin/env python
# coding: utf-8

"""
Script for loading OHLC data from a CSV file and plotting a candlestick plot.
"""

# Import packages 
import pandas as pd
# import matplotlib.pyplot as plt
import mplfinance as mpf
# Print mplfinance version
print(mpf.__version__)
# from mplfinance import candlestick_ohlc
# import matplotlib.dates as mpdates

# import plotly as py
import plotly.graph_objects as go
from plotly.offline import plot

# plt.style.use('dark_background') 

## Load OHLC data from csv file and format the index
se_ries = pd.read_csv('C:/Develop/data/SP500_2020/GOOGL.csv', parse_dates=True, date_parser=pd.to_datetime, index_col='index')
type(se_ries)
se_ries.dtypes
# Print column names
se_ries.columns
# Rename columns
se_ries.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
# se_ries = se_ries[['Open', 'High', 'Low', 'Close']]
se_ries.shape
se_ries.head()
se_ries.tail()

# Or parse dates by hand
# Convert the Date column from string into datetime object 
# se_ries['Date'] = pd.to_datetime(se_ries['Date']) 
# Create datetime index passing the datetime series
# datetime_index = pd.DatetimeIndex(se_ries['Date'].values)
# se_ries = se_ries.set_index(datetime_index)
# Remove the Date column
# se_ries.drop('Date', axis=1, inplace=True)


## Plotly dynamic interactive candlestick plots
# https://plotly.com/python/candlestick-charts/

# Select time slice of data
slic_e = se_ries['2019':'2020']

# Create OHLC time series from data frame
# fig_ure = go.Figure(data=go.Ohlc(x=slic_e.index, open=slic_e.Open, high=slic_e.High, low=slic_e.Low, close=slic_e.Close))
# Create candlestick time series from data frame
fig_ure = go.Figure(data=[go.Candlestick(x=slic_e.index,
                                         open=slic_e.Open, high=slic_e.High, low=slic_e.Low, close=slic_e.Close, 
                            showlegend=False)])
fig_ure.update_layout(title='GOOG', xaxis_rangeslider_visible=False)
# Plot interactive candlestick plot in browser and save to html file
plot(fig_ure, filename='stock_ohlc.html', auto_open=True)
# Show the plot - works only in Jupyter notebook
# fig_ure.show()


## Load AAPL OHLC data from csv file on github
se_ries = pd.read_csv('https://raw.githubusercontent.com/plotly/datasets/master/finance-charts-apple.csv')
type(se_ries)
se_ries.dtypes
se_ries.iloc[0:5, 3:6]
se_ries.shape
se_ries.head()
se_ries.tail()

# Select time slice of data
slic_e = se_ries['2019':'2020']

## Plotly dynamic interactive candlestick plots

fig_ure = go.Figure(data=[go.Candlestick(x=slic_e['Date'],
                open=slic_e['AAPL.Open'],
                high=slic_e['AAPL.High'],
                low=slic_e['AAPL.Low'],
                close=slic_e['AAPL.Close'])])

fig_ure.update_layout(title='APPL', yaxis_title='Price', xaxis_rangeslider_visible=False)
# Plot in browser
plot(fig_ure, auto_open=True)


## Attempt at dash plot - doesn't do anything

import dash
import dash_core_components as dcc
import dash_html_components as html

app = dash.Dash()
app.layout = html.Div([
    dcc.Graph(figure=fig_ure)
])

app.run_server(debug=True, use_reloader=False)  # Turn off reloader if inside Jupyter

# End dash plot - doesn't do anything


## Matplotlib static candlestick plots
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

