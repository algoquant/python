""" This is a Dash App for a Moving Average Crossover Strategy. """
""" The stock prices are loaded from a CSV file. """
""" Adapted from: https://plotly.com/python/dropdowns/ """

""" It uses Bootstrap Components for greater control of the slider layout. """
""" https://dash-bootstrap-components.opensource.faculty.ai/docs/components/layout/ """


# Run this Dash app as follows:
# In a terminal run:
# python3 /Users/jerzy/Develop/Python/dash_strat_moving_avg.py
# Then in the browser open the url:
# http://127.0.0.1:8050/


# Ignore FutureWarning
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# Suppress package info messages - doesn't work
# import logging
# logging.getLogger('werkzeug').setLevel(logging.ERROR)

# import datetime
import pandas as pd
import numpy as np

import plotly.graph_objects as go

import dash
from dash import dcc
from dash import html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

from utils import get_symbol, calc_sharpe
from strategies import strat_movavg

# Define marks for sliders
marklb = {i: {"label": str(i), "style": {"fontSize": "24px"}} for i in range(5, 300, 20)}
marklag = {i: {"label": str(i), "style": {"fontSize": "24px"}} for i in range(1, 8, 1)}
# marklag = {i: {"label": str(i), "style": {"transform": "scale(2.0)"}} for i in range(1, 7, 1)}


# Load OHLC stock prices from CSV file
# Define stock symbol
symboln = "SPY"
rangen = "daily"
# rangen = "minute"
filename = "/Users/jerzy/Develop/data/" + symboln + "_" + rangen + ".csv"
ohlc = pd.read_csv(filename)

# Download OHLC stock prices from Polygon for the symbol
# startd = datetime.date(2000, 1, 1)
# endd = datetime.date.today()
# ohlc = get_symbol(symbol=symboln, startd=startd, endd=endd, range=rangen)

# Calculate log stock prices
# ohlc[["Open", "High", "Low", "Close"]] = np.log(ohlc[["Open", "High", "Low", "Close"]])
# Select time slice of data
# startd = pd.to_datetime("2019").date()
# endd = pd.to_datetime("2022").date()
# ohlcsub = ohlc.loc[startd:endd]
# ohlcsub = ohlc.loc["2019":"2022"]

# Drop non-market data
# if (rangen == "minute"):
#   ohlc = ohlc.drop(ohlc.between_time("0:00", "9:00").index)
#   ohlc = ohlc.drop(ohlc.between_time("17:00", "23:59").index)

# Extract time index
# datev = ohlc.index
datev = ohlc.Date

# Calculate the log returns
closep = ohlc.Close
retp = np.log(closep).diff()

# Calculate the strategy returns and Sharpe ratio
retsum = retp.cumsum()
sharpev = round(calc_sharpe(retp), 3)


## Create the Dash web app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = dbc.Container([
  html.H1("Dash App for Moving Average Crossover Strategy"),
  html.Br(),
  dbc.Row([
    dbc.Col([
      # Create the look-back slider
      html.H3("Look-back interval (days):", style={"color": "blue"}),
      dcc.Slider(id="ma_slider", min=5, max=300, step=1, value=150, marks=marklb,
        tooltip={"placement": "top", "always_visible": True})
    ]),
    dbc.Col([
      # Create the lag slider
      html.H3("Lag amount (days):", style={"color": "blue"}),
      dcc.Slider(id="lag_slider", min=1, max=7, step=1, value=6, marks=marklag,
        tooltip={"placement": "top", "always_visible": True})
    ]),
  ],
  style={"width": "70%", "font-size": "24", "color": "red"}),
  html.Br(),
  print("Reading from sliders..."),
  # Create the plot
  dcc.Graph(id="time_series_chart")
], fluid=True)


# Define the Dash app server function
@app.callback(
    Output("time_series_chart", "figure"), 
    [Input("ma_slider", "value"),
     Input("lag_slider", "value")]
    )

def display_time_series(lookback, lagv):
    ## Calculate the strategy returns
    retstrat = strat_movavg(closep, retp, lookback, lagv)
    # Calculate the strategy Sharpe ratio
    sharpestrat = calc_sharpe(retstrat)
    textv = "Strategy Sharpe = " + str(round(sharpestrat, 3)) + "<br>" + \
      symboln + " Sharpe = " + str(sharpev) + "<br>" + \
      "lookback = " + str(lookback) + "<br>" + \
      "lagv = " + str(lagv)
    
    ## Plot the strategy returns
    # Create an empty plot object
    plotfig = go.Figure()
    # Modify the plot aesthetics
    # https://plotly.com/python/reference/layout/
    plotfig.update_layout(title_text="Moving Average Crossover Strategy for: " + symboln, 
                          title_font_size=34, title_font_color="black", 
                          yaxis_title="Cumulative Returns", font_color="black", font_size=18,
                          xaxis_rangeslider_visible=False, width=1400, height=850)
    plotfig.add_annotation(text=textv, font=dict(family="bold", size=18), align="left",
                           showarrow=False, xref='paper', yref='paper', x=0.5, y=0.9)
    # Add trace for the stock
    plotfig.add_trace(go.Scatter(x=datev, y=retsum,
      name=symboln, line=dict(color="blue")))
    # Add trace for the strategy
    plotfig.add_trace(go.Scatter(x=datev, y=retstrat.cumsum(),
      name="Strategy", line=dict(color="red")))
    # Customize legend
    plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal", itemsizing="constant", 
                          font=dict(family="sans-serif", size=18, color="blue")))
    return plotfig


if __name__ == "__main__":
    # On Mac:
    app.run_server(debug=True, port=8050)
    # On mini server:
    # app.run_server(debug=True, host="0.0.0.0")

