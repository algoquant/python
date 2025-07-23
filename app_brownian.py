# This is a Shiny app for a plotly time series plot.

# Run this Shiny app in VS Code by clicking the 'Run' button in the top right corner of the editor.
# 
# Or in a terminal run:
# shiny run --reload --launch-browser /Users/jerzy/Develop/Python/app_brownian.py

import numpy as np
import pandas as pd
from shiny import App, ui
from shinywidgets import output_widget, render_widget
import plotly.graph_objects as go

# Create a time series of Brownian motion
randv = pd.Series(np.random.normal(size=100).cumsum())
randv.index = pd.date_range('2025-01-01', periods=len(randv), freq='D')

# Second method to create a time series of Brownian motion
# randv = pd.DataFrame({
#     'date': pd.date_range('2025-01-01', periods=100, freq='D'),
#     'value': np.random.normal(size=100).cumsum()
# })
# randv.set_index('date', inplace=True)


# Create the Shiny UI
app_ui = ui.page_fluid(
    ui.h2('Brownian Motion Time Series Plot'),
    output_widget('plott')
)

# Create the Shiny server
def server(input, output, session):
    @output
    @render_widget
    def plott():
        fig = go.Figure(data=go.Scatter(x=randv.index, y=randv))
        # fig.update_layout(title='Brownian Motion Time Series Plot')
        return fig

# Create the Shiny app from the app_ui and the server
app = App(app_ui, server)
