# Shiny Express example
# https://shiny.posit.co/blog/posts/shiny-express/

# Run this Shiny app in VS Code by clicking the "Run" button in the top right corner of the editor.
#
# Or in a terminal run:
# shiny run --reload --launch-browser /Users/jerzy/Develop/Python/app_react1.py
# http://localhost:50905

import numpy as np
import pandas as pd
from shiny import reactive
from shiny.express import input, render, ui
from shinywidgets import render_plotly

ui.page_opts(title="Histogram", fillable=True)

# with ui.sidebar():
ui.input_numeric("nbins", "Number of bins", 10)

@reactive.calc
def df():
    return pd.Series(np.random.normal(size=1000))

with ui.card(full_screen=True):
    @render_plotly
    def histfun():
        import plotly.express as px
        histp = px.histogram(df(), nbins=input.nbins())
        histp.layout.update(showlegend=False)
        return histp

