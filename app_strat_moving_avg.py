''' This is a Shiny App for a Moving Average Crossover Strategy. '''
''' The stock prices are loaded from a CSV file. '''
''' Adapted from: https://plotly.com/python/dropdowns/ '''

''' It uses Bootstrap Components for greater control of the slider layout. '''
''' https://dash-bootstrap-components.opensource.faculty.ai/docs/components/layout/ '''


# Run this Shiny app from the terminal as follows:
# shiny run --reload --launch-browser /Users/jerzy/Develop/Python/app_strat_moving_avg.py


# Ignore FutureWarning
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)

# Suppress package info messages - doesn't work
# import logging
# logging.getLogger('werkzeug').setLevel(logging.ERROR)


import shiny
# from shiny import render, ui
from shinywidgets import output_widget, render_widget
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# from utils import get_symbol, calc_sharpe
# from strategies import strat_movavg

# Load OHLC stock prices from CSV file
# Define stock symbol
symboln = 'SPY'
rangen = 'daily'
# rangen = 'minute'
filename = '/Users/jerzy/Develop/data/' + symboln + '_' + rangen + '.csv'
ohlc = pd.read_csv(filename, parse_dates=['Date'])
# Convert Date column from datetime64[ns] to date type
# ohlc.Date = ohlc.Date.dt.date
# Drop the Seconds column
ohlc = ohlc.drop('Seconds', axis=1)
# Set the time index as the data frame index
ohlc.set_index('Date', inplace=True)
# Log of Open, High, Low, Close prices
ohlc.iloc[:,0:4] = np.log(ohlc.iloc[:,0:4])

# plotfig = go.Figure(go.Scatter(x=ohlc.index, y=ohlc.Close,))
# plotfig = plotfig.update_layout(title='SPY', yaxis_title='Log Price', 
#             title_font_size=12)
# plotfig.show()

# Calculate the log returns
# closep = ohlc.Close
# retp = closep.diff()

# Extract time index
# datev = ohlc.index
# datev = ohlc.Date

# Calculate the strategy returns and Sharpe ratio
# retsum = retp.cumsum()
# sharpev = round(calc_sharpe(retp), 3)

# Create a dataframe for the strategy returns
# dframe = pd.DataFrame({
#     'date': ohlc.Date,
#     'value': retp.cumsum()
# })
# print(dframe.head())


# Create the Shiny UI
app_ui = shiny.ui.page_fluid(
    output_widget('tsplot')
)

# Create the Shiny server
def server(input, output, session):
    @output
    @render_widget
    def tsplot():
        plotfig = go.Figure(go.Scatter(x=ohlc.index, y=ohlc.Close))
        plotfig.update_layout(title='Time Series Plot')
        return plotfig

# Create the Shiny app from the app_ui and the server
app = shiny.App(app_ui, server)


