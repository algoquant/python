# This is a Shiny app for a plotly bar data.

# Run this Shiny app in VS Code by clicking the "Run" button in the top right corner of the editor.
# 
# Or in a terminal run:
# shiny run --reload --launch-browser /Users/jerzy/Develop/Python/app_plotbars.py


import numpy as np
import plotly.graph_objects as go
from shiny import App, ui
from shinywidgets import output_widget, render_widget

# Create the Shiny UI
app_ui = ui.page_fluid(
    ui.h2("Plotly Bar Chart"),
    output_widget("plotbars"),
)

# Create the Shiny server
def server(input, output, session):
    @output
    @render_widget
    def plotbars():
        fig = go.Figure(
            go.Bar(x=['A', 'B', 'C'], y=np.random.uniform(size=3)),
            # layout=go.Layout(title="Simple Bar Chart")
        )
        return fig

# Create the Shiny app from the UI and the server
app = App(app_ui, server)
