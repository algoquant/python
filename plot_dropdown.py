""" This is a Plotly plot of rolling average stock prices with a dropdown menu. """
""" The stock prices are downloaded from Polygon. """

# Adapted from:
# https://plotly.com/python/dropdowns/


from utils import get_symbol

import datetime
import numpy as np
import pandas as pd

import plotly.graph_objects as go

# Load dataset
symbol = "SPY"
range = "day"
start_date = datetime.date(2000, 1, 1)
end_date = datetime.date.today()
# Download stock prices from Polygon for the symbol
ohlc = get_symbol(symbol=symbol, start_date=start_date, end_date=end_date, range=range)
# Calculate log stock prices
ohlc[['Open', 'High', 'Low', 'Close']] = np.log(ohlc[['Open', 'High', 'Low', 'Close']])
closep = ohlc['Close']

# Calculate rolling stock prices
rolling_fast = closep.ewm(span=11).mean()
rolling_slow = closep.ewm(span=51).mean()

## Initialize figure
plotfig = go.Figure()

## Add Traces - plots of Close and rolling prices

# Plot Close price
plotfig.add_trace(
    go.Scatter(x=list(ohlc.index),
               y=list(closep),
               name="Close",
               line=dict(color="blue")))

# Plot slow rolling price
plotfig.add_trace(
    go.Scatter(x=list(ohlc.index),
               y=list(rolling_slow),
               name="rolling slow",
               line=dict(color="green")))

# Plot fast rolling price
plotfig.add_trace(
    go.Scatter(x=list(ohlc.index),
               y=list(rolling_fast),
               name="rolling fast",
               line=dict(color="red")))

## Add dropdown menu
plotfig.update_layout(title_text = symbol + " rolling Prices",
                      title_font_size=24, title_font_color="blue", 
    updatemenus=[
      go.layout.Updatemenu(
          active=0,
          buttons=list([
                dict(label=symbol + " All",
                     method="update",
                     args=[{"visible": [True, True, True]},
                           {"title": symbol, 'showlegend':True}]),
                dict(label=symbol + " Close",
                     method="update",
                     args=[{"visible": [True, False, False]},
                           {"title": symbol, 'showlegend':True}]),
                dict(label=symbol + " rolling slow",
                     method="update",
                     args=[{"visible": [True, True, False]},
                           {"title": symbol + " rolling slow", 'showlegend':True}]),
                dict(label=symbol + " rolling fast",
                     method="update",
                     args=[{"visible": [True, False, True]},
                           {"title": symbol + " rolling fast", 'showlegend':True}])
        ]),  # end buttons
    )  # end Updatemenu
])  # end update_layout

## Render the plot
plotfig.show()
