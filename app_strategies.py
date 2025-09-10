# A Shiny app for the exponential moving average prices with Bollinger bands.

# Created using the Shiny Assistant prompt: "plot brownian motion combined with EMA"
# https://gallery.shinyapps.io/assistant/

# Run this Shiny app in VS Code by clicking the "Run" button in the top right corner of the editor.
#
# Or in a terminal run:
#   shiny run --reload --launch-browser app_bollinger.py
# Launch browser URL:
# http://127.0.0.1:8000/
# 
# Find what processes are using port 8000
#   lsof -ti:8000
# 
# Kill the process (replace PID with the number from above)
#   kill -9 $(lsof -ti:8000)

import os
import glob
from shiny import App, reactive, render, ui
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
# from matplotlib.figure import Figure
from datetime import date

# Setup

# Title text
textv = "Trading Strategy Performance Dashboard"

# Get the current working directory
os.getcwd()
# Change the current working directory
os.chdir("/Users/jerzy/Develop/Python")

# List state CSV files for strategy performance
state_dirname = "/Users/jerzy/Develop/data/trading/"
state_files = glob.glob(state_dirname + "state_*.csv")
# Extract just the filename without path for display
state_file_names = [os.path.basename(f) for f in state_files]
state_file_dict = {name: path for name, path in zip(state_file_names, state_files)}

# Date range for the date slider
startd = date(2025, 7, 1)  # Set reasonable default start date
endd = date(2025, 9, 6)    # Current date


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
            ui.input_select("strategy_file", "Strategy State File",
                            choices=state_file_names, 
                            selected=state_file_names[0] if state_file_names else None
                            ),
            style="width: 80%; padding-left: 10px; padding-right: 1px;"
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
        col_widths=[6, 6]
    ),
    ui.card(
        ui.card_header("Strategy Performance (Total PnL = pnlReal + pnlUnreal)"),
        ui.output_plot("strategy_plot"),
        height="600px"
    ),
    # title=textv
)


# Create the Shiny server
def server(input, output, session):

    # Load strategy state data from CSV file
    @reactive.calc
    def get_strategy_data():
        selected_file = input.strategy_file()
        if selected_file and selected_file in state_file_dict:
            file_path = state_file_dict[selected_file]
            try:
                strategy_data = pd.read_csv(file_path, parse_dates=["date_time"])
                # Calculate total PnL
                strategy_data['total_pnl'] = strategy_data['pnlReal'] + strategy_data['pnlUnreal']
                # Calculate cumulative PnL
                strategy_data['cumulative_pnl'] = strategy_data['total_pnl'].cumsum()
                return strategy_data
            except Exception as e:
                print(f"Error loading strategy data: {e}")
                return pd.DataFrame()
        return pd.DataFrame()

    # Plot strategy performance
    @render.plot
    def strategy_plot():
        strategy_data = get_strategy_data()
        
        if strategy_data.empty:
            # Create empty plot with message
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.text(0.5, 0.5, 'No strategy data available', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=16)
            ax.set_title('Strategy Performance')
            return fig
        
        # Filter by date range
        date_range = input.datev()
        if 'date_time' in strategy_data.columns:
            # Convert date_time to date for comparison
            strategy_data['date_only'] = strategy_data['date_time'].dt.date
            mask = (strategy_data['date_only'] >= date_range[0]) & (strategy_data['date_only'] <= date_range[1])
            filtered_data = strategy_data[mask]
        else:
            filtered_data = strategy_data
        
        if filtered_data.empty:
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.text(0.5, 0.5, 'No data in selected date range', 
                   ha='center', va='center', transform=ax.transAxes, fontsize=16)
            ax.set_title('Strategy Performance')
            return fig
        
        # Create the plot
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), height_ratios=[2, 1])
        
        # Plot cumulative PnL
        ax1.plot(filtered_data['date_time'], filtered_data['cumulative_pnl'], 
                label='Cumulative PnL', color='blue', linewidth=2)
        ax1.set_title(f'Strategy Performance - {input.strategy_file()}')
        ax1.set_ylabel('Cumulative PnL ($)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Plot individual PnL components
        ax2.plot(filtered_data['date_time'], filtered_data['pnlReal'], 
                label='PnL Real', color='green', alpha=0.7)
        ax2.plot(filtered_data['date_time'], filtered_data['pnlUnreal'], 
                label='PnL Unrealized', color='red', alpha=0.7)
        ax2.plot(filtered_data['date_time'], filtered_data['total_pnl'], 
                label='Total PnL', color='purple', linewidth=2)
        ax2.set_xlabel('Date/Time')
        ax2.set_ylabel('PnL ($)')
        ax2.legend()
        ax2.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return fig


app = App(app_ui, server)
