""" This is a Shiny App for a Moving Average Crossover Strategy. """
""" The stock prices are loaded from a CSV file. """
""" Adapted from: https://plotly.com/python/dropdowns/ """

""" It uses Bootstrap Components for greater control of the slider layout. """
""" https://dash-bootstrap-components.opensource.faculty.ai/docs/components/layout/ """


# Run this Shiny app as follows:
# shiny run --reload --launch-browser /Users/jerzy/Develop/Python/app_strat_moving_avg.py
# In a terminal run:
# python3 /Users/jerzy/Develop/Python/app_strat_moving_avg.py
# Then in the browser open the url:
# http://127.0.0.1:8050/


# Ignore FutureWarning
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# Suppress package info messages - doesn't work
# import logging
# logging.getLogger('werkzeug').setLevel(logging.ERROR)


import shiny
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from utils import get_symbol, calc_sharpe
from strategies import strat_movavg

# Load OHLC stock prices from CSV file
# Define stock symbol
symboln = "SPY"
rangen = "daily"
# rangen = "minute"
filename = "/Users/jerzy/Develop/data/" + symboln + "_" + rangen + ".csv"
ohlc = pd.read_csv(filename)

# Calculate the log returns
closep = ohlc.Close
retp = np.log(closep).diff()

# Extract time index
# datev = ohlc.index
datev = ohlc.Date

# Calculate the strategy returns and Sharpe ratio
# retsum = retp.cumsum()
# sharpev = round(calc_sharpe(retp), 3)

# Create a dataframe for the strategy returns
dframe = pd.DataFrame({
    "date": datev,
    "value": retp.cumsum()
})
# print(dframe.head())


app_ui = shiny.ui.page_fluid(
    shiny.ui.output_plot("ts_plot")
)

def server(input, output, session):
    @output
    @shiny.render.plot
    def ts_plot():
        fig = go.Figure(dframe=go.Scatter(x=dframe["date"], y=dframe["value"]))
        fig.update_layout(title="Time Series Plot")
        return fig

app = shiny.App(app_ui, server)


