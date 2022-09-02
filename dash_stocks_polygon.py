""" This is a Dash web app of plots of stock prices. """
""" The stock prices are downloaded from Polygon. """

# Run this Dash app as follows:
# In a terminal run:
# python3 /Users/jerzy/Develop/Python/dash_stocks_polygon.py
# Then in the browser open the url:
# http://127.0.0.1:8050/

import math
import datetime
import numpy as np
import pandas as pd

import plotly.graph_objects as go
# import plotly.express as px

from utils import get_symbol

import dash
from dash import dcc
from dash import html
# import dash_core_components as dcc
# import dash_html_components as html
from dash.dependencies import Input, Output

# Define the list of symbols to download
symbols = ["AAPL", "META", "SPY", "VXX", "SVXY"]
# df = px.data.stocks()

# range = "minute"
range = "day"

## Set time variables
# Create a date from integers
startd = datetime.date(2000, 1, 1)
# print("Start date is:", startd)
# Get today's date
endd = datetime.date.today()
# print("Today is:", endd)

# Create the Dash web app
app = dash.Dash(__name__)

# Define the Dash app UI layout in HTML
app.layout = html.Div([
  # Create a title banner
  html.H2(['This is a Dash app which plots OHLC stock prices downloaded from Polygon', html.Br(), 
          'Select a stock symbol from the menu below:']),
  # Create the dropdown menu
  dcc.Dropdown(id="symbol",
      options=[{"label": symbol, "value": symbol} for symbol in symbols],
      value=symbols[0],
      clearable=False,
      style={"width": "50%"}
      ),
  # Create the plot
  dcc.Graph(id="time-series-chart"),
])


# Define the Dash app server function
@app.callback(
    Output("time-series-chart", "figure"), 
    [Input("symbol", "value")]
    )
def display_time_series(symbol):
    # Download stock prices from Polygon for the symbol
    ohlc = get_symbol(symbol=symbol, startd=startd, endd=endd, range=range)
    # Calculate log stock prices
    ohlc[['Open', 'High', 'Low', 'Close']] = np.log(ohlc[['Open', 'High', 'Low', 'Close']])
    # closep = math.log(ohlc['Close'])
    # Candlestick plot of the log stock prices
    plotfig = go.Figure(data=[go.Candlestick(x=ohlc.index, open=ohlc.Open, high=ohlc.High, low=ohlc.Low, close=ohlc.Close, 
                name='Candlestick plot of Log OHLC Prices for: ' + symbol, showlegend=False)])
    # Modify plot aesthetics
    # https://plotly.com/python/reference/layout/
    plotdata = plotfig.update_layout(title_text='Candlestick plot of Log OHLC Prices for: ' + symbol, 
                                    title_font_size=24, title_font_color="blue", 
                                    yaxis_title='Prices', font_color="black", font_size=18,
                                    xaxis_rangeslider_visible=False, width=1600, height=800)
    # Line plot of the log stock prices
    # plotfig = px.line(ohlc, title='Log Stock Prices for: ' + symbol, y='Close', width=1700, height=900)
    return plotfig


if __name__ == "__main__":
    app.run_server(debug=True)
