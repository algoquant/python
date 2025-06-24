# This is a Shiny app that plots stock prices using a date range slider.

# Run this Shiny app in VS Code by clicking the "Run" button in the top right corner of the editor.
#
# Or in a terminal run:
# shiny run --reload --launch-browser /Users/jerzy/Develop/Python/app_slider.py

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
# import yfinance as yf
from shiny import App, render, ui
# from shiny.express import input, render, ui
from datetime import date

# Load OHLC stock prices from CSV file
# Define stock symbol
symboln = "SPY"
rangen = "daily"
# rangen = "minute"
filename = "/Users/jerzy/Develop/data/" + symboln + "_" + rangen + ".csv"
ohlc = pd.read_csv(filename, parse_dates=["Date"])
# Convert Date column from datetime64[ns] to date type
ohlc.Date = ohlc.Date.dt.date
# Drop the Seconds column
ohlc = ohlc.drop("Seconds", axis=1)
# Set the time index as the data frame index
ohlc.set_index("Date", inplace=True)
# Log of Open, High, Low, Close prices
ohlc.iloc[:, 0:4] = np.log(ohlc.iloc[:, 0:4])
closep = ohlc.Close
# closep = yf.download("AAPL", start=startd, end=endd)

# Set the date range for the slider
startd = ohlc.index.min()
endd = ohlc.index.max()
# startd = date(2020, 1, 1)
# endd = date(2023, 1, 1)
# Download prices from Yahoo Finance (if needed)
# closep = yf.download("AAPL", start=startd, end=endd)


# Create the Shiny UI
app_ui = ui.page_fluid(
    ui.div(
        # ui.HTML("&nbsp;&nbsp;&nbsp;"), # Adds spaces
        # ui.tags.div(style="margin-left: 20px;"),  # Add left margin

        ui.input_slider(
            "datev",
            "Select Date Range:",
            min=startd,
            max=endd,
            value=(startd, endd),  # Initial range selection
            # style="margin-left: 20px;"  # Add a 20px left margin
            # style="background-color: lightblue;"
        )),
    ui.output_plot("plotobj")
)


# Create the Shiny server
def server(input, output, session):
    @render.plot
    def plotobj():
        # Filter data based on slider input
        pricev = closep[(closep.index >= input.datev()[0]) &
                        (closep.index <= input.datev()[1])]
        # Create plot
        fig, ax = plt.subplots(figsize = (16, 9))
        ax.plot(pricev.index, pricev)
        ax.set_xlabel("Date")
        ax.set_ylabel("Close Price")
        ax.set_title(symboln + " Stock Price")
        return fig


# Create the Shiny app from the app_ui and the server
app = App(app_ui, server)
