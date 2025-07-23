# A Shiny app for the exponential moving average prices with Bollinger bands.

# Created using the Shiny Assistant prompt: "plot brownian motion combined with EMA"
# https://gallery.shinyapps.io/assistant/

# Run this Shiny app in VS Code by clicking the "Run" button in the top right corner of the editor.
#
# Or in a terminal run:
# shiny run --reload --launch-browser app_bollinger.py
# Launch browser URL:
# http://127.0.0.1:8000/


import os
from shiny import App, reactive, render, ui
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
# from matplotlib.figure import Figure
from datetime import date

# Setup

# Title text
textv = "Exponential Moving Average Prices With Bollinger Bands"

# Get the current working directory
os.getcwd()
# Change the current working directory
os.chdir("/Users/jerzy/Develop/Python")

# List files in the data directory
dirname = "/Users/jerzy/Develop/data/etfdaily/"
filev = os.listdir(dirname)
# Extract symbols from the file names
symbolv = [(lambda x: ((x.split("."))[0].split("_")[0]))(x) for x in filev]

# Load SPY stock prices from CSV file
symboln = "SPY"
filename = dirname + symboln + "_daily" + ".csv"
ohlc = pd.read_csv(filename, parse_dates=["Index"])
# Convert Date column from datetime64[ns] to date type
ohlc.Index = ohlc.Index.dt.date
# Set the time index as the data frame index
ohlc.set_index("Index", inplace=True)

# Date range for the date slider
startd = date(1999, 1, 1)
# Last date of SPY data
endd = ohlc.index[-1]


# End Setup


# Create the Shiny UI
app_ui = ui.page_fluid(
    ui.HTML("<br>"),  # Add two line breaks for spacing
    ui.div(
        ui.h1(textv),
        style="display: flex; justify-content: center; align-items: center;"
    ),  # end title div
    ui.HTML("<br><br>"),  # Add two line breaks for spacing
    # ui.h3(textv, _add_wsp=True),  # Add non-breaking space after the title

    # Attempt to use math formulas - but they don't render
    # ui.HTML('<div>more math here $$\sqrt{2}$$</div>'),
    # ui.h2("MathJax Examples"),
    # ui.p("An irrational number $\\sqrt{2}$ and a fraction $1-\\frac{1}{2}$"),
    # ui.p(
    #     "and a fact about $\\pi$:$\\frac2\\pi = \\frac{\\sqrt2}2 \\cdot. \\frac{\\sqrt{2+\\sqrt2}}2 \\cdot. \\frac{\\sqrt{2+\\sqrt{2+\\sqrt2}}}2 \\cdots$"
    # ),
    # ui.output_ui("ex1"),

    # Some text about alpha parameter
    # ui.HTML('<div style="text-align: center;">The alpha parameter determines the rate of decay of past data.</div>'),
    # ui.HTML('<div style="text-align: center;">If alpha is closer to one, then the EMA value adjusts to new data slowly - so it\'s smoother.</div>'),
    # ui.HTML('<div style="text-align: center;">If alpha is closer to zero, then the EMA value adjusts to new data quickly - so it\'s more volatile.</div>'),

    ui.layout_columns(
        ui.div(
            ui.input_select("symboln", "Symbol",
                            choices=symbolv, selected="SPY"
                            ),
            style="width: 80%; padding-left: 100px; padding-right: 1px;"
        ),
        # Date range slider
        ui.input_slider(
            "datev",
            "Select Date Range:",
            min=startd,
            max=endd,
            value=(startd, endd),  # Initial range selection
            # style="margin-left: 20px;"  # Add a 20px left margin
            # style="background-color: lightblue;"
        ),
        # ui.input_slider("n_points", "Number of points", min=100, max=1000, value=500, step=100),
        ui.input_slider("alphap",
                        ui.popover(
                            ui.input_action_button(
                                "btn2", "Alpha parameter (click for help)"),
                            "The alpha parameter determines the rate of decay of past data.",
                            ui.HTML("<br>"),
                            "If alpha is closer to one, then the EMA price adjusts to new prices slowly - so it\'s smoother.",
                            ui.HTML("<br>"),
                            "If alpha is closer to zero, then the EMA price adjusts to new prices quickly - so it\'s more volatile.",
                            id="btn_popover2"
                        ),  # end popover
                        # "Alpha parameter",
                        min=0.01, max=0.99, value=0.95, step=0.01),
        # ui.input_slider("volp", "Volatility", min=0.01, max=0.5, value=0.1, step=0.01),
        ui.input_slider("bb_std", "Bollinger Bands Std Dev",
                        min=1.0, max=3.0, value=2.0, step=0.1),
        col_widths=[3, 3, 3, 2]
    ),
    ui.card(
        # ui.card_header(textv),
        ui.output_plot("plotobj"),
        height="600px"
    ),
    # title=textv
)


# Create the Shiny server
def server(input, output, session):

    # Load OHLC stock prices from CSV file
    @reactive.calc
    # @reactive.event(input.resimulate, ignore_none=False)
    def get_prices():
        # Simulate Brownian motion prices
        # n = input.n_points()
        # volp = input.volp()
        # Generate random steps
        # steps = np.random.normal(0, volp, n)
        # Cumulative sum to get Brownian motion
        # priceb = np.cumsum(steps)
        # Add a drift of 0.001 per step (optional)
        # drift = np.linspace(0, 0.001 * n, n)
        # priceb += drift

        # Load OHLC stock prices from CSV file
        symboln = input.symboln()
        filename = dirname + symboln + "_daily" + ".csv"
        ohlc = pd.read_csv(filename, parse_dates=["Index"])
        # Convert Date column from datetime64[ns] to date type
        ohlc.Index = ohlc.Index.dt.date
        # Set the time index as the data frame index
        ohlc.set_index("Index", inplace=True)
        # Log of OHLC prices
        ohlc.iloc[:, 0:4] = np.log(ohlc.iloc[:, 0:4])
        closep = ohlc[symboln + ".Close"]
        return closep

    # Calculate the EMA and the Bollinger Bands
    @reactive.calc
    def calculate_bbands():
        pricev = get_prices()
        # Calculate EMA
        alphap = input.alphap()
        emav = pricev.ewm(alpha=(1-alphap)).mean()
        stdv = np.sqrt(alphap)*pricev.ewm(alpha=(1-alphap)).std(bias=True)
        std_dev = input.bb_std()
        # Calculate upper and lower bands
        upper_band = emav + (stdv * std_dev)
        lower_band = emav - (stdv * std_dev)
        return emav, upper_band, lower_band

    # Plot using Matplotlib
    @render.plot
    def plotobj():
        pricev = get_prices()
        emav, upper_band, lower_band = calculate_bbands()
        # Subset the prices using the date window
        windoww = (pricev.index >= input.datev()[0]) & (
            pricev.index <= input.datev()[1])
        pricev = pricev[windoww]
        emav = emav[windoww]
        upper_band = upper_band[windoww]
        lower_band = lower_band[windoww]
        # Plot
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(pricev.index, pricev, label=input.symboln(),
                color='blue', alpha=0.7)
        ax.plot(pricev.index, emav,
                label=f'EMA (alpha={input.alphap()})', color='red', linewidth=2)
        ax.plot(pricev.index, upper_band,
                label=f'Upper Bollinger ({input.bb_std()} σ)', color='green', linestyle='--')
        ax.plot(pricev.index, lower_band,
                label=f'Lower Bollinger ({input.bb_std()} σ)', color='green', linestyle='--')
        # Fill between the bands
        # ax.fill_between(pricev.index, upper_band, lower_band, alpha=0.1, color='green')
        ax.set_title(input.symboln() + ' with EMA and Bollinger Bands')
        ax.set_xlabel('Time')
        ax.set_ylabel('Value')
        ax.legend()
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        return fig


app = App(app_ui, server)
