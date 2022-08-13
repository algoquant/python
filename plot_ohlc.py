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

## Load OHLC data from csv file and format the time index

symbol = "GOOGL"
# ohlc = pd.read_csv('/Users/jerzy/Develop/data/SPY_daily.csv', parse_dates=True, date_parser=pd.to_datetime, index_col='Date')
ohlc = pd.read_csv('/Volumes/external/Develop/data/SP500_2020/GOOGL.csv', parse_dates=True, date_parser=pd.to_datetime, index_col='index')

# Or load raw data and parse dates by hand
# Convert the Date column from string into datetime object 
# ohlc['Date'] = pd.to_datetime(ohlc['Date']) 
# Create datetime index passing the datetime series
# datetime_index = pd.DatetimeIndex(ohlc['Date'].values)
# ohlc = ohlc.set_index(datetime_index)
# Remove the Date column
# ohlc.drop('Date', axis=1, inplace=True)


# Print column names
ohlc.columns
# Rename columns
# ohlc.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
# Calculate log stock prices
ohlc[['Open', 'High', 'Low', 'Close']] = np.log(ohlc[['Open', 'High', 'Low', 'Close']])

ohlc.head()
ohlc.tail()

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
closep = ohlc['Close']
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
# fram_e = px.data.stocks()
# Create line time series of prices from data frame
plotfig = px.line(closep['2020'])
plotdata = plotfig.update_layout(title=symbol+' Log Prices', yaxis_title='Log Price', xaxis_rangeslider_visible=True)
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename='stock_prices.html', auto_open=True)
plotfig.show()

# Create bar plot of volumes
plotfig = px.bar(ohlc['Volume']['2020'])
plotdata = plotfig.update_layout(title=symbol+' Volume', yaxis_title='Volume', xaxis_rangeslider_visible=False)
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename='stock_volumes.html', auto_open=True)
plotfig.show()


## Plotly dynamic interactive time series plots using plotly.graph_objects

import plotly.graph_objects as go

# Select time slice of data
ohlcsub = ohlc['2019':'2020']

# Create plotly line graph object from data frame
plotfig = go.Figure([go.Scatter(x=ohlcsub.index, y=ohlcsub['Close'])])
plotdata = plotfig.update_layout(title=symbol, yaxis_title='Log Price', xaxis_rangeslider_visible=False, 
            title_font_size=12)
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename='stock_prices.html', auto_open=True)
plotfig.show()


## Plotly simple candlestick with moving average

plotfig = go.Figure(data=[go.Candlestick(x=ohlcsub.index,
                open=ohlcsub.Open, high=ohlcsub.High, low=ohlcsub.Low, close=ohlcsub.Close, 
                name=symbol+' Log OHLC Prices', showlegend=False)])
plotdata = plotfig.update_layout(title=symbol+' Log OHLC Prices', 
                                title_font_size=24, title_font_color="blue", 
                                yaxis_title='Prices', font_color="black", font_size=18,
                                xaxis_rangeslider_visible=False)
# Calculate moving average stock prices
closep = ohlc['Close']
lookback = 55
rollingp = closep.ewm(span=lookback).mean()
# Add moving average
plotdata = plotfig.add_trace(go.Scatter(x=ohlcsub.index, y=rollingp[ohlcsub.index], 
                            name="Moving Average", line=dict(color="blue")))
# Customize legend
plotdata = plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal",
                      font=dict(family="sans-serif", size=18, color="blue")))
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename='stock_candlesticks.html', auto_open=True)
plotfig.show()


## Plotly candlestick with volumes using plotly subplots
# https://stackoverflow.com/questions/62287001/how-to-overlay-two-plots-in-same-figure-in-plotly

from plotly.subplots import make_subplots

# Select time slice of data
ohlcsub = ohlc['2019':'2020']
# Create line of prices from data frame
# trace1 = go.Scatter(x=ohlcsub.index, y=ohlcsub['Close'], name='Prices', showlegend=False)
# Create candlestick time series from data frame
trace1 = go.Candlestick(x=ohlcsub.index,
                open=ohlcsub.Open, high=ohlcsub.High, low=ohlcsub.Low, close=ohlcsub.Close, 
                name=symbol+' Log OHLC Prices', showlegend=False)
# Create bar plot of volumes
trace2 = go.Bar(x=ohlcsub.index, y=ohlcsub['Volume'], name='Volumes', showlegend=False)
# Create empty plot layout
plotfig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        subplot_titles=[' Log Price', 'Volume'], row_heights=[450, 150])
# Add plots to layout
plotdata = plotfig.add_trace(trace1, row=1, col=1)
plotdata = plotfig.add_trace(trace2, row=2, col=1)
# Add titles and reduce margins
plotdata = plotfig.update_layout(title=symbol+' Prices and Volume', 
                       # yaxis_title=['Log Price', 'Volume'], 
                      margin=dict(l=0, r=10, b=0, t=30), 
                      xaxis_rangeslider_visible=True)
# plotdata = plotfig.update_xaxes(automargin=TRUE)
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename='stock_ohlc_volume.html', auto_open=True)
plotfig.show()


## Create a dash app with simple candlestick in browser - needs separate file
# https://plotly.com/python/candlestick-charts/

import dash
from dash import dcc
from dash import html

plotfig = go.Figure(data=[go.Candlestick(x=ohlcsub.index,
                open=ohlcsub.Open, high=ohlcsub.High, low=ohlcsub.Low, close=ohlcsub.Close, 
                name=symbol+' Log OHLC Prices', showlegend=False)])
plotdata = plotfig.update_layout(title=symbol+' Log OHLC Prices', yaxis_title='Prices', 
                        width=1500, height=900, xaxis_rangeslider_visible=False)

app = dash.Dash()
app.layout = html.Div([
    dcc.Graph(figure=plotfig)
])

# Turn off reloader if inside Jupyter
app.run_server(debug=True, use_reloader=False, port='8051')

# End dash app


## matplotlib alternative to plotly - not interactive

import matplotlib.pyplot as plt

# Calculate the moving average
lookback = 55
rollingp = closep.ewm(span=lookback).mean()

# Set plot style
plt.style.use('fivethirtyeight')
# Set plot dimensions
plt.figure(figsize = (12, 6))
# Plot price and MA lines:
plt.plot(closep, label=symbol, linewidth=1, color='blue')
plt.plot(rollingp, label= str(lookback) + ' day moving average', color='red', linewidth=2)
# Add title and labeles on the axes, making legend visible:
plt.title(symbol + 'Stock Price with a ' + str(lookback) + ' day Moving Average')
plt.xlabel('Date')
plt.ylabel('Price')
plt.legend()
# plt.margins(0.1)
plt.show()
# Close all plots in memory
plt.close('all')



## Matplotlib moving average plot with subplots

# Calculate the fast and slow moving averages
closep = ohlc['Close']
backf = 10
rollfast = closep.rolling(window=backf).mean()
backs = 50
rollslow = closep.rolling(window=backs).mean()

start_date = '2019-01-01'
end_date = '2020-04-17'

# Unpack the plot figure and axes objects
# https://stackoverflow.com/questions/34162443/why-do-many-examples-use-fig-ax-plt-subplots-in-matplotlib-pyplot-python
fig, ax = plt.subplots(figsize=(16,9))
# Add plots
ax.plot(closep[start_date:end_date], label=symbol + ' Stock', color='blue')
ax.plot(rollslow[start_date:end_date], label=str(backs) + '-days MA', color='green')
ax.plot(rollfast[start_date:end_date], label=str(backf) + '-days MA', color='red')
ax.set_ylabel('Price')
ax.set_title(symbol + ' Stock Price and Moving Averages')
# Add legend
ax.legend(loc='best')
# Render the plot
plt.show()
# Close all plots in memory
plt.close('all')


## mplfinance add-on to matplotlib for plotting financial data

import mplfinance as mpf
# Print mplfinance version
print(mpf.__version__)
# from mplfinance import candlestick_ohlc
# import matplotlib.dates as mpdates

# plt.style.use('dark_background') 
mpf.plot(ohlc.loc['2014':'2015'], type='candle', style='charles', title=symbol)
# Or with two moving averages
mpf.plot(ohlc.loc['2020'], type='candle', figratio=(18, 10), mav=(11, 31), 
        # linecolor=['green', 'red'],
        style='charles', title=symbol)
# Or with volume
mpf.plot(ohlc.loc['2020'], type='candle', style='charles', title=symbol, 
         volume=True, ylabel='Log Price', ylabel_lower='Volume')
# Or save to file
mpf.plot(ohlc.loc['2014':'2015'], type='candle', style='charles', title=symbol,
            ylabel='Log Price', ylabel_lower='Shares \nTraded', volume=True, 
            mav=(3, 6, 9), 
            savefig='test-mplfiance.png')

# ema_15 = ohlc['2020']['Close'].ewm(span=15).mean()
# fig, ax = plt.subplots(figsize = (12,6))


# Create Subplots 
# fig, ax = plt.subplots() 
  
# Plot the data 
# mpf.candlestick_ohlc(ax, ohlc.values, width = 0.6, 
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

