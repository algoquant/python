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

import numpy as np

# Load OHLC data from csv file - the time index is formatted inside read_csv()
# import os
# import sys

# if "__file__" in globals():
#     os.chdir(os.path.dirname(os.path.abspath(__file__)))
#     sys.path.insert(0, os.getcwd())

# from utils import read_csv

symbol = "SPY"
# range = "minute"
range = "daily"
filename = "/Users/jerzy/Develop/data/etfdaily/" + symbol + "_" + range + ".csv"
ohlc = pd.read_csv(filename, parse_dates=True, date_format="%Y-%m-%d", index_col="Index")
# ohlc.index = pd.to_datetime(ohlc.index)

# Drop non-market data
if (range == "minute"):
  ohlc = ohlc.drop(ohlc.between_time("0:00", "9:00").index)
  ohlc = ohlc.drop(ohlc.between_time("17:00", "23:59").index)


# ohlc = pd.read_csv("/Users/jerzy/Develop/data/SPY_day.csv", parse_dates=True, date_format=pd.to_datetime, index_col="Date")
# ohlc = pd.read_csv("/Volumes/external/Develop/data/SP500_2020/GOOGL.csv", parse_dates=True, date_format=pd.to_datetime, index_col="index")

# Or load raw data and parse dates by hand
# Convert the Date column from string into datetime object 
# ohlc["Date"] = pd.to_datetime(ohlc["Date"]) 
# Create datetime index passing the datetime series
# datetime_index = pd.DatetimeIndex(ohlc["Date"].values)
# ohlc = ohlc.set_index(datetime_index)
# Remove the Date column
# ohlc.drop("Date", axis=1, inplace=True)


# Print column names
ohlc.columns
# Rename the columns
ohlc.columns = ["Open", "High", "Low", "Close", "Volume"]
# Calculate the log stock prices
ohlc[["Open", "High", "Low", "Close"]] = np.log(ohlc[["Open", "High", "Low", "Close"]])

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

# Select series of Close prices
closep = ohlc.Close
# Or
# closep = ohlc.iloc[:, 3]
type(closep)

# Extract time index
datev = ohlc.index


## Plotly dynamic interactive time series plots using plotly.express - a simplified plotly
# https://plotly.com/python/time-series/

# import plotly as py
# plotly.express for time series
import plotly.express as px
# from plotly.offline import plot

# Import built-in time series data frame
# dframe = px.data.stocks()
# Create line time series of prices from data frame
plotfig = px.line(closep, render_mode="svg")
plotfig = plotfig.update_layout(title=symbol + " Log Prices", yaxis_title="Log Price", xaxis_rangeslider_visible=True)

# Hide non-market periods
plotfig = plotfig.update_xaxes(rangebreaks=[
  dict(bounds=["sat", "mon"]), # Hide weekends
  dict(bounds=[17, 9], pattern="hour"),  # Hide overnight hours 5PM to 9AM
  # dict(values=["2015-12-25", "2016-01-01"])  # Hide Christmas and New Year's
])

# Plot interactive plot in browser and save to html file
# plot(plotfig, filename="stock_prices.html", auto_open=True)
plotfig.show()

# Create bar plot of volumes
plotfig = px.bar(ohlc["Volume"]["2020"])
plotfig = plotfig.update_layout(title=symbol+" Volume", yaxis_title="Volume", xaxis_rangeslider_visible=False)
# Show the plot - works only in Jupyter notebook
plotfig.show()
# Plot interactive plot in browser and save to html file
mpf.plot(plotfig, filename="spy_vwap_strat.html", auto_open=True)


## Plotly dynamic interactive time series plots using plotly.graph_objects - doesn't use Python dictionaries?

import plotly.graph_objects as go

# Select time slice of data
ohlc = ohlc["2019":"2020"]
# Create plotly line graph object from data frame
plotfig = go.Figure([go.Scatter(x=datev, y=closep)])
plotfig = plotfig.update_layout(title=symbol, yaxis_title="Log Price", xaxis_rangeslider_visible=False, 
            title_font_size=12)
# Hide non-market periods - needs fixing
plotfig = plotfig.update_xaxes(rangebreaks=[
  dict(bounds=["sat", "mon"]), # Hide weekends
  dict(bounds=[17, 9], pattern="hour"),  # Hide overnight hours 5PM to 9AM
  # dict(values=["2015-12-25", "2016-01-01"])  # Hide Christmas and New Year's
])
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename="stock_prices.html", auto_open=True)
plotfig.show()


## Plotly line plot with moving average

# Calculate the moving average
lookback = 55
pricema = ohlc.Close.ewm(span=lookback, adjust=False).mean()

# Create empty graph object
plotfig = go.Figure()
# Add trace for Close price
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=closep,
  name=symbol, line=dict(color="blue")))
# Add trace for moving average
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=pricema,
  name="Moving Average", line=dict(color="orange")))
# Hide non-market periods - needs fixing
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


## Plotly simple candlestick with moving average

# Create empty graph object
plotfig = go.Figure()
# Add trace for candlesticks
plotfig = plotfig.add_trace(go.Candlestick(x=datev,
                open=ohlc.Open, high=ohlc.High, low=ohlc.Low, close=ohlc.Close, 
                name=symbol+" Log OHLC Prices", showlegend=False))
# Add trace for moving average
plotfig = plotfig.add_trace(go.Scatter(x=datev, y=pricema, 
                            name="Moving Average", line=dict(color="orange")))
# Hide non-market periods
plotfig = plotfig.update_xaxes(rangebreaks=[
  dict(bounds=["sat", "mon"]), # Hide weekends
  dict(bounds=[17, 9], pattern="hour"),  # Hide overnight hours 5PM to 9AM
  # dict(values=["2015-12-25", "2016-01-01"])  # Hide Christmas and New Year's
])
# Customize plot
plotfig = plotfig.update_layout(title=symbol + " Log OHLC Prices", 
                                title_font_size=24, title_font_color="blue", 
                                yaxis_title="Price", font_color="black", font_size=18,
                                xaxis_rangeslider_visible=False)
# Customize legend
plotfig = plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal", 
  itemsizing="constant", font=dict(family="sans-serif", size=18, color="orange")))
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename="stock_candlesticks.html", auto_open=True)
plotfig.show()


## Plotly candlestick with volumes using plotly subplots
# https://stackoverflow.com/questions/62287001/how-to-overlay-two-plots-in-same-figure-in-plotly

from plotly.subplots import make_subplots

# Select time slice of data
ohlc = ohlc["2019":"2020"]
# Create line of prices from data frame
# trace1 = go.Scatter(x=datev, y=closep, name="Prices", showlegend=False)
# Create candlestick time series from data frame
trace1 = go.Candlestick(x=datev,
                open=ohlc.Open, high=ohlc.High, low=ohlc.Low, close=ohlc.Close, 
                name=symbol+" Log OHLC Prices", showlegend=False)
# Create bar plot of volumes
trace2 = go.Bar(x=datev, y=ohlc["Volume"], name="Volumes", showlegend=False)
# Create empty plot layout
plotfig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        subplot_titles=[" Log Price", "Volume"], row_heights=[450, 150])
# Add plots to layout
plotfig = plotfig.add_trace(trace1, row=1, col=1)
plotfig = plotfig.add_trace(trace2, row=2, col=1)
# Add titles and reduce margins
plotfig = plotfig.update_layout(title=symbol+" Prices and Volume", 
                       # yaxis_title=["Log Price", "Volume"], 
                      margin=dict(l=0, r=10, b=0, t=30), 
                      xaxis_rangeslider_visible=True)
# plotfig = plotfig.update_xaxes(automargin=TRUE)
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename="stock_ohlc_volume.html", auto_open=True)
plotfig.show()


## Create a dash app with simple candlestick in browser - needs separate file
# https://plotly.com/python/candlestick-charts/

import dash
from dash import dcc
from dash import html

plotfig = go.Figure(data=[go.Candlestick(x=datev,
                open=ohlc.Open, high=ohlc.High, low=ohlc.Low, close=ohlc.Close, 
                name=symbol+" Log OHLC Prices", showlegend=False)])
plotfig = plotfig.update_layout(title=symbol+" Log OHLC Prices", yaxis_title="Prices", 
                        width=1500, height=900, xaxis_rangeslider_visible=False)

app = dash.Dash()
app.layout = html.Div([
    dcc.Graph(figure=plotfig)
])

# Turn off reloader if inside Jupyter
app.run_server(debug=True, use_reloader=False, port="8051")

# End dash app


## matplotlib alternative to plotly - not interactive

import matplotlib.pyplot as plt

# Calculate the moving average
lookback = 55
pricema = closep.ewm(span=lookback, adjust=False).mean()

# Set plot style
plt.style.use("fivethirtyeight")
# Set plot dimensions
plt.figure(figsize = (12, 6))
# Plot price and MA lines:
plt.plot(closep, label=symbol, linewidth=1, color="blue")
plt.plot(pricema, label= str(lookback) + " day moving average", color="red", linewidth=2)
# Add title and labeles on the axes, making legend visible:
plt.title(symbol + "Stock Price with a " + str(lookback) + " day Moving Average")
plt.xlabel("Date")
plt.ylabel("Price")
plt.legend()
# plt.margins(0.1)
plt.show()
# Close all plots in memory
plt.close("all")



## Matplotlib moving average plot with subplots

# Calculate the fast and slow moving averages
backf = 10
mafast = closep.rolling(window=backf).mean()
backs = 50
maslow = closep.rolling(window=backs).mean()

startd = "2019-01-01"
endd = "2020-04-17"

# Unpack the plot figure and axes objects
# https://stackoverflow.com/questions/34162443/why-do-many-examples-use-fig-ax-plt-subplots-in-matplotlib-pyplot-python
fig, ax = plt.subplots(figsize=(16,9))
# Add plots
ax.plot(closep[startd:endd], label=symbol + " Stock", color="blue")
ax.plot(maslow[startd:endd], label=str(backs) + "-day MA", color="green")
ax.plot(mafast[startd:endd], label=str(backf) + "-day MA", color="red")
ax.set_ylabel("Price")
ax.set_title(symbol + " Stock Price and Moving Averages")
# Add legend
ax.legend(loc="best")
# Render the plot
plt.show()
# Close all plots in memory
plt.close("all")


## mplfinance add-on to matplotlib for plotting financial data

import mplfinance as mpf
# Print mplfinance version
print(mpf.__version__)
# from mplfinance import candlestick_ohlc
# import matplotlib.dates as mpdates

# plt.style.use("dark_background") 
mpf.plot(ohlc.loc["2014":"2015"], type="candle", style="charles", title=symbol)
# Or with two moving averages
mpf.plot(ohlc.loc["2020"], type="candle", figratio=(18, 10), mav=(11, 31), 
        # linecolor=["green", "red"],
        style="charles", title=symbol)
# Or with volume
mpf.plot(ohlc.loc["2020"], type="candle", style="charles", title=symbol, 
         volume=True, ylabel="Log Price", ylabel_lower="Volume")
# Or save to file
mpf.plot(ohlc.loc["2014":"2015"], type="candle", style="charles", title=symbol,
            ylabel="Log Price", ylabel_lower="Shares \nTraded", volume=True, 
            mav=(3, 6, 9), 
            savefig="test-mplfiance.png")

# ema15 = ohlc["2020"]["Close"].ewm(span=15, adjust=False).mean()
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


## Lightweight Charts Python - Modern interactive financial charts
# https://github.com/louisnw01/lightweight-charts-python

from lightweight_charts import Chart

# Create chart instance
chart = Chart()

# Set the main candlestick data
chart.set(ohlc)
# Render the chart
chart.show()


# Create data frame from OHLC data for plotting
df = ohlc["Close"].reset_index()
df.columns = ['time', 'close']
# Add moving average column
df['ma'] = df['close'].rolling(window=5).mean()
df['time'] = df['time'].dt.strftime('%Y-%m-%d')  # Format for chart

# Melt into long format for charting
plot_df = df.melt(id_vars='time', value_vars=['close', 'ma'], var_name='series', value_name='value')
plot_df = plot_df.dropna()

chart = Chart()
chart.set(plot_df)
chart.show()



# Prepare data for lightweight charts
close_series = []
ma_series = []

for index, row in df.iterrows():
    if not pd.isna(row['close']):
        close_series.append({
            'time': row['time'],
            'value': float(row['close'])
        })
    
    if not pd.isna(row['ma']):
        ma_series.append({
            'time': row['time'],
            'value': float(row['ma'])
        })

# Initialize chart
chart = Chart()

# Plot close price as line
close_line = chart.create_line('Close Price', color='blue', width=2)
close_line.set(close_series)

# Plot moving average
ma_line = chart.create_line('Moving Average (5)', color='orange', width=2)
ma_line.set(ma_series)

# Show chart in browser
chart.show()


# Calculate moving averages for overlay
lookback_short = 20
lookback_long = 50
ma_short = ohlc.Close.rolling(window=lookback_short).mean()
ma_long = ohlc.Close.rolling(window=lookback_long).mean()

# Prepare moving average data
ma_short_data = []
ma_long_data = []

for index, value in ma_short.items():
    if not pd.isna(value):
        ma_short_data.append({
            'time': index.strftime('%Y-%m-%d'),
            'value': float(value)
        })

for index, value in ma_long.items():
    if not pd.isna(value):
        ma_long_data.append({
            'time': index.strftime('%Y-%m-%d'),
            'value': float(value)
        })

# Create line series for moving averages
line_short = chart.create_line(f'{lookback_short}-day MA', color='rgba(255, 165, 0, 0.8)', width=2)
line_long = chart.create_line(f'{lookback_long}-day MA', color='rgba(255, 0, 0, 0.8)', width=2)

# Set data for moving averages
line_short.set(ma_short_data)
line_long.set(ma_long_data)

# print(f"Created lightweight chart with {len(chart)} data points")

# Add volume histogram (optional)
try:
    volume_data = []
    for index, row in ohlc.iterrows():
        volume_data.append({
            'time': index.strftime('%Y-%m-%d'),
            'value': float(row['Volume']),
            'color': 'rgba(76, 175, 80, 0.5)' if row['Close'] > row['Open'] else 'rgba(255, 82, 82, 0.5)'
        })
    
    # Create volume histogram
    volume_hist = chart.create_histogram('Volume', price_scale_id='volume')
    volume_hist.set(volume_data)
    print("Added volume histogram")
    
except Exception as e:
    print(f"Could not add volume histogram: {e}")

# Configure chart appearance
try:
    chart.layout(background_color='#1e1e1e', text_color='white', font_size=12)
    chart.candle_style(
        up_color='#26a69a',
        down_color='#ef5350',
        wick_up_color='#26a69a',
        wick_down_color='#ef5350'
    )
    
    # Set chart title
    chart.set_title(f'{symbol} Stock Price with Moving Averages and Volume')
    print("Chart styling applied")
    
except Exception as e:
    print(f"Could not apply chart styling: {e}")

# Show the chart
print(f"Displaying {symbol} chart with lightweight-charts-python...")
chart.show(block=True)


## Lightweight Charts with custom indicators
# Note: This section is commented out due to the main lightweight charts setup above
# Uncomment and modify as needed once the main section is working

# # Create a new chart for technical analysis
# chart_tech = Chart()
# 
# # Set the main candlestick data
# chart_tech.set(chart_data)
# 
# # Calculate RSI (Relative Strength Index)
# def calculate_rsi(prices, period=14):
#     delta = prices.diff()
#     gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
#     loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
#     rs = gain / loss
#     rsi = 100 - (100 / (1 + rs))
#     return rsi
# 
# # Calculate MACD
# def calculate_macd(prices, fast=12, slow=26, signal=9):
#     ema_fast = prices.ewm(span=fast).mean()
#     ema_slow = prices.ewm(span=slow).mean()
#     macd = ema_fast - ema_slow
#     signal_line = macd.ewm(span=signal).mean()
#     histogram = macd - signal_line
#     return macd, signal_line, histogram
# 
# # Calculate indicators
# close_prices = ohlc.Close
# rsi = calculate_rsi(close_prices)
# macd, macd_signal, macd_histogram = calculate_macd(close_prices)
# 
# # Rest of technical analysis code...
# print("Technical analysis section commented out for now.")


## Lightweight Charts with real-time updates simulation
# Note: This section is commented out due to the main lightweight charts setup above
# Uncomment and modify as needed once the main section is working

# # Create a simple real-time simulation chart
# chart_realtime = Chart()
# 
# # Start with initial data
# initial_data = chart_data[:50]  # First 50 data points
# chart_realtime.set(initial_data)
# 
# # Configure real-time chart
# chart_realtime.layout(background_color='#1e1e1e', text_color='white', font_size=12)
# chart_realtime.set_title(f'{symbol} Real-time Simulation')
# 
# print(f"Real-time simulation chart for {symbol} - this would update with new data in a real application")
# chart_realtime.show(block=False)
# 
# # In a real application, you would update the chart with new data like this:
# # chart_realtime.update(new_data_point)
# 
# print("Lightweight Charts examples completed!")

print("Real-time simulation section commented out for now.")


## Simple lightweight charts example for testing

def create_simple_lightweight_chart():
    """Simple example to test lightweight charts functionality"""
    try:
        from lightweight_charts import Chart
        
        # Validate that chart_data exists and is not empty
        if 'chart_data' not in globals():
            print("Error: chart_data not found. Please run the main script first.")
            return
        
        if not chart_data or len(chart_data) == 0:
            print("Error: chart_data is empty.")
            return
        
        # Create a simple chart with sample data
        chart = Chart()
        
        # Use a subset of the data for testing
        test_data = chart_data[:100] if len(chart_data) > 100 else chart_data
        
        # Validate test_data format
        if not isinstance(test_data, list):
            print("Error: test_data should be a list")
            return
        
        # Check if data has the required format
        if len(test_data) > 0:
            required_keys = ['time', 'open', 'high', 'low', 'close']
            if not all(key in test_data[0] for key in required_keys):
                print(f"Error: Data missing required keys. Expected: {required_keys}")
                return
        
        print(f"Setting chart data with {len(test_data)} points...")
        
        # Set the data
        chart.set(test_data)
        
        # Basic styling
        chart.layout(background_color='#ffffff', text_color='#000000')
        chart.set_title(f'{symbol} - Simple Lightweight Chart Test')
        
        # Show the chart
        print("Opening simple lightweight chart...")
        chart.show(block=True)
        
    except ImportError:
        print("lightweight-charts not installed. Install with: pip install lightweight-charts")
    except Exception as e:
        print(f"Error creating chart: {e}")
        import traceback
        traceback.print_exc()

# Uncomment the line below to run the simple example
# create_simple_lightweight_chart()

