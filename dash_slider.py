""" This is a Dash web app of plots of rolling average stock prices with a slider. """
""" The stock prices are downloaded from Polygon. """
""" Run in terminal: python3 dash_slider.py """

# Adapted from:
# https://plotly.com/python/dropdowns/


from utils import get_symbol

import datetime
import numpy as np
import pandas as pd

import plotly.graph_objects as go

import dash
from dash import dcc
from dash import html
# import dash_core_components as dcc
# import dash_html_components as html
from dash.dependencies import Input, Output


# Load dataset
symbol = "SPY"
range = "day"
start_date = datetime.date(2000, 1, 1)
end_date = datetime.date.today()
# Download stock prices from Polygon for the symbol
ohlc = get_symbol(symbol=symbol, start_date=start_date, end_date=end_date, range=range)
# Calculate log stock prices
ohlc[['Open', 'High', 'Low', 'Close']] = np.log(ohlc[['Open', 'High', 'Low', 'Close']])
# Select time slice of data
startd = pd.to_datetime("2019").date()
endd = pd.to_datetime("2022").date()
ohlcsub = ohlc.loc[startd:endd]
# ohlcsub = ohlc.loc['2019':'2022']
closep = ohlcsub['Close']
indeks = ohlcsub.index


## Create the Dash web app
app = dash.Dash(__name__)

# Define the Dash app UI layout in HTML
app.layout = html.Div([
  # Create a title banner
  # html.H2(['Dash App With Candlestick Plot of Stock Prices and Moving Average', html.Br(), 
  #         'Select look-back interval in the slider below:']),
  html.H2('Dash App With Candlestick Plot of Stock Prices and Moving Average'),
  html.H3('Select the look-back interval in the slider below:', style={'color': 'red'}),
  # Create the slider
  html.Div(dcc.Slider(id='ma_slider', min=10, max=60, step=1, value=10, 
            # marks=dict((i, str(i)) for i in range(10, 61, 10))),
            # marks={str(h) : {'label' : str(h), 'style':{'color':'red'}} for h in range(10, 61, 10)}),
            marks={10 : '10', 20 : '20', 30 : '30', 40 : '40', 50 : '50', 60 : '60'}),
            style={'width': '25%', "font_size": '18', 'color': 'red'}),
  # Create the plot
  dcc.Graph(id="time-series-chart")
])


# Define the Dash app server function
@app.callback(
    Output("time-series-chart", "figure"), 
    [Input("ma_slider", "value")]
    )
def display_time_series(value):
    ## Initialize candlestick plot of the log stock prices
    plotfig = go.Figure(data=[go.Candlestick(x=indeks, open=ohlcsub.Open, high=ohlcsub.High, low=ohlcsub.Low, close=ohlcsub.Close, 
                name='Candlestick Plot and Moving Average of Log OHLC Prices for: ' + symbol, showlegend=False)])
    # Modify plot aesthetics
    # https://plotly.com/python/reference/layout/
    plotdata = plotfig.update_layout(title_text='Candlestick Plot and Moving Average of Log OHLC Prices for: ' + symbol, 
                                title_font_size=24, title_font_color="blue", 
                                yaxis_title='Prices', font_color="black", font_size=18,
                                xaxis_rangeslider_visible=False, width=1700, height=900)
    # Calculate moving average stock prices
    rollingp = closep.ewm(span=value).mean()
    # Add moving average
    plotfig.add_trace(go.Scatter(x=indeks, y=rollingp, name="Moving Average", line=dict(color="blue")))
    # Customize legend
    plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal",
                          font=dict(family="sans-serif", size=24, color="blue")))
    return plotfig


if __name__ == "__main__":
    # On Mac:
    app.run_server(debug=True)
    # On mini server:
    # app.run_server(debug=True, host="0.0.0.0")

