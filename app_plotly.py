""" This is a Shiny App for a plotly plot. """

import shiny
import plotly.graph_objects as go
import pandas as pd

# Sample data
dframe = pd.DataFrame({
    "date": pd.date_range('2023-01-01', periods=100, freq='D'),
    "value": range(100)
})

app_ui = shiny.ui.page_fluid(
    shiny.ui.output_plot("ts_plot")
)

def server(input, output, session):
    @output
    @shiny.render.plot
    def ts_plot():
        fig = go.Figure(data=go.Scatter(x=dframe["date"], y=dframe["value"]))
        fig.update_layout(title="Time Series Plot")
        return fig

app = shiny.App(app_ui, server)
