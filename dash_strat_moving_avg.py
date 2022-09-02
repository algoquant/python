""" This is a Dash web app of plots of rolling average stock prices with a slider. """
""" The stock prices are downloaded from Polygon. """
""" Adapted from: """
""" https://plotly.com/python/dropdowns/ """

# Run this Dash app as follows:
# In a terminal run:
# python3 /Users/jerzy/Develop/Python/dash_slider.py
# Then in the browser open the url:
# http://127.0.0.1:8050/


import datetime
import pandas as pd
import numpy as np

import plotly.graph_objects as go

import dash
from dash import dcc
from dash import html
# import dash_core_components as dcc
# import dash_html_components as html
from dash.dependencies import Input, Output

from utils import get_symbol
from strategies import run_movavg


# Load OHLC data from CSV file
# For example:
# ohlc = read_csv('/Users/jerzy/Develop/data/BTC_minute.csv')

# Define parameters
symbol = "SPY"
range = "day"
startd = datetime.date(2000, 1, 1)
endd = datetime.date.today()
# Download stock prices from Polygon for the symbol
ohlc = get_symbol(symbol=symbol, startd=startd, endd=endd, range=range)
# Calculate log stock prices
ohlc[["Open", "High", "Low", "Close"]] = np.log(ohlc[["Open", "High", "Low", "Close"]])
# Select time slice of data
# startd = pd.to_datetime("2019").date()
# endd = pd.to_datetime("2022").date()
ohlcsub = ohlc.loc[startd:endd]
# ohlcsub = ohlc.loc["2019":"2022"]

# Extract time index
datev = ohlcsub.index

# Calculate log asset returns
closep = ohlcsub.Close
returnts = np.log(closep).diff()
# Calculate cumulative returns
asset_cum_returns = returnts.cumsum()


## Create the Dash web app
app = dash.Dash(__name__)

# Define the Dash app UI layout in HTML
app.layout = html.Div([
  # Create a title banner
  # html.H2(["Dash App With Candlestick Plot of Stock Prices and Moving Average", html.Br(), 
  #         "Select look-back interval in the slider below:"]),
  html.H2("Dash App for Moving Average Strategy"),
  html.H3("Select the look-back interval in the slider below:", style={"color": "red"}),
  # Create the slider
  html.Div(dcc.Slider(id="ma_slider", min=50, max=120, step=1, value=80, 
            # marks=dict((i, str(i)) for i in range(10, 61, 10))),
            # marks={str(h) : {"label" : str(h), "style":{"color":"red"}} for h in range(10, 61, 10)}),
            marks={50 : "50", 60 : "60", 70 : "70", 80 : "80", 90 : "90", 100 : "100", 110 : "110", 120 : "120"}),
            style={"width": "25%", "font_size": "18", "color": "red"}),
  # Create the plot
  dcc.Graph(id="time-series-chart")
])


# Define the Dash app server function
@app.callback(
    Output("time-series-chart", "figure"), 
    [Input("ma_slider", "value")]
    )
def display_time_series(lookback):
    ## Calculate the strategy returns
    strategy_cum_returns = run_movavg(closep, returnts, lookback)
    ## Plot the strategy returns
    plotfig = go.Figure()
    # Modify plot aesthetics
    # https://plotly.com/python/reference/layout/
    plotfig.update_layout(title_text="Moving Average Strategy for: " + symbol, 
                          title_font_size=24, title_font_color="black", 
                          yaxis_title="Cumulative Returns", font_color="black", font_size=18,
                          xaxis_rangeslider_visible=False, width=1400, height=850)
    # Add trace for symbol
    plotfig.add_trace(go.Scatter(x=datev, y=asset_cum_returns,
      name=symbol, line=dict(color="blue")))
    # Add trace for strategy
    plotfig.add_trace(go.Scatter(x=datev, y=strategy_cum_returns,
      name="Strategy", line=dict(color="orange")))
    # Customize legend
    plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal", itemsizing="constant", 
                          font=dict(family="sans-serif", size=24, color="blue")))
    return plotfig


if __name__ == "__main__":
    # On Mac:
    app.run_server(debug=True)
    # On mini server:
    # app.run_server(debug=True, host="0.0.0.0")

