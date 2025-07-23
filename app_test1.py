# Run this Shiny app in VS Code by clicking the "Run" button in the top right corner of the editor.
# 
# Or run this Shiny app from the terminal as follows:
# shiny run --reload --launch-browser /Users/jerzy/Develop/Python/app_test1.py

from shiny import App, render, ui
import matplotlib.pyplot as plt
import numpy as np

# Create the Shiny UI
app_ui = ui.page_fluid(
    ui.input_slider("n", "Number of points", min=10, max=100, value=50),
    ui.output_plot("plot1")
)

# Create the Shiny server
def server(input, output, session):
    @render.plot
    def plot1():
        x = np.random.rand(input.n())
        y = np.random.rand(input.n())
        fig, ax = plt.subplots()
        ax.scatter(x, y)
        return fig

# Create the Shiny app from the app_ui and the server
app = App(app_ui, server)
