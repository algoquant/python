# Run this Dash app as follows:
# In a terminal run:
# python3 /Users/jerzy/Develop/Python/dash_test.py
# Then in the browser open the url:
# http://127.0.0.1:8051/


import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

import datetime
import pandas as pd
import numpy as np

import plotly.graph_objects as go

import dash
from dash import dcc
from dash import html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

from utils import read_csv, get_symbol, calc_sharpe
from strategies import strat_movavg

# Define marks for sliders
marklb = {i: str(i) for i in range(50, 120, 10)}
marklag = {i: str(i) for i in range(1, 7, 1)}


# Define parameters
symbol = "SPY"
range = "day"
# range = "minute"

# Load OHLC stock prices from CSV file
filename = "/Users/jerzy/Develop/data/" + symbol + "_" + range + ".csv"
ohlc = read_csv(filename)

# Download OHLC stock prices from Polygon for the symbol
# startd = datetime.date(2000, 1, 1)
# endd = datetime.date.today()
# ohlc = get_symbol(symbol=symbol, startd=startd, endd=endd, range=range)

# Calculate log stock prices
# ohlc[["Open", "High", "Low", "Close"]] = np.log(ohlc[["Open", "High", "Low", "Close"]])
# Select time slice of data
# startd = pd.to_datetime("2019").date()
# endd = pd.to_datetime("2022").date()
# ohlcsub = ohlc.loc[startd:endd]
# ohlcsub = ohlc.loc["2019":"2022"]

# Drop non-market data
if (range == "minute"):
  ohlc = ohlc.drop(ohlc.between_time("0:00", "9:00").index)
  ohlc = ohlc.drop(ohlc.between_time("17:00", "23:59").index)

# Extract time index
datev = ohlc.index

# Calculate log asset returns
closep = ohlc.Close
returnts = np.log(closep).diff()
# Calculate the Sharpe ratio and cumulative returns
retsass = returnts.cumsum()
sharpass = round(calc_sharpe(returnts), 3)


## Create the Dash web app
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = dbc.Container([
  html.H2("Dash App for Moving Average Strategy"),
  dbc.Row([
    dbc.Col([
      # Create the look-back slider
      html.H3("Select the look-back interval:", style={"color": "red"}),
      html.Div(dcc.Slider(id="ma_slider", min=50, max=120, step=1, value=80, marks=marklb), 
               style={"width": "100%", "font_size": "24", "color": "red"})
    ], width=3),
    dbc.Col([
      # Create the lag slider
      html.H3("Select the lag amount:", style={"color": "red"}),
      html.Div(dcc.Slider(id="lag_slider", min=1, max=7, step=1, value=1, marks=marklag),
               style={"width": "100%", "font_size": "24", "color": "red"})
    ], width=3),
  ]),
  print("Reading from sliders..."),
  # Create the plot
  dcc.Graph(id="time-series-chart")
], fluid=True)


# Define the Dash app server function
@app.callback(
    Output("time-series-chart", "figure"), 
    [Input("ma_slider", "value"),
     Input("lag_slider", "value")]
    )

def display_time_series(lookback, lagv):
    ## Calculate the strategy returns
    retstrat = strat_movavg(closep, returnts, lookback, lagv)
    # Calculate the strategy Sharpe ratio
    sharpestrat = calc_sharpe(retstrat)
    textv = "Strategy Sharpe = " + str(round(sharpestrat, 3)) + "<br>" + symbol + " Sharpe = " + str(sharpass)
    # Calculate the cumulative strategy returns
    # retstrat = retstrat.cumsum()
    ## Plot the strategy returns
    plotfig = go.Figure()
    # Modify plot aesthetics
    # https://plotly.com/python/reference/layout/
    plotfig.update_layout(title_text="Moving Average Strategy for: " + symbol, 
                          title_font_size=24, title_font_color="black", 
                          yaxis_title="Cumulative Returns", font_color="black", font_size=18,
                          xaxis_rangeslider_visible=False, width=1400, height=850)
    plotfig.add_annotation(text=textv, font=dict(family="bold", size=18), align="left",
                           showarrow=False, xref='paper', yref='paper', x=0.5, y=0.9)
    # Add trace for symbol
    plotfig.add_trace(go.Scatter(x=datev, y=retsass,
      name=symbol, line=dict(color="blue")))
    # Add trace for strategy
    plotfig.add_trace(go.Scatter(x=datev, y=retstrat.cumsum(),
      name="Strategy", line=dict(color="orange")))
    # Customize legend
    plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal", itemsizing="constant", 
                          font=dict(family="sans-serif", size=18, color="blue")))
    return plotfig


if __name__ == "__main__":
    # On Mac:
    app.run_server(debug=True, port=8051)
    # On mini server:
    # app.run_server(debug=True, host="0.0.0.0")

