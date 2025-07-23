# In terminal run:
# python3 /Users/jerzy/Develop/Python/dash_stocks.py
# Then open:
# http://127.0.0.1:8050/

# print("This is a Dash app which plots stock prices from plotly.express\nSelect a stock symbol from the dropdown menu.\n")

import dash
from dash import dcc
from dash import html
# import dash_core_components as dcc
# import dash_html_components as html
from dash.dependencies import Input, Output
import plotly.express as px

df = px.data.stocks()

app = dash.Dash(__name__)


app.layout = html.Div([
  html.H2(['This is a Dash app which plots stock prices from plotly.express.', html.Br(), 'Select a stock symbol from the menu below:']),
    dcc.Dropdown(
        id="ticker",
        options=[{"label": x, "value": x} 
                 for x in df.columns[1:]],
        value=df.columns[1],
        clearable=False,
    style={"width": "30%"}
    ),
    dcc.Graph(id="time-series-chart"),
])


@app.callback(
    Output("time-series-chart", "figure"), 
    [Input("ticker", "value")])
def display_time_series(ticker):
    fig = px.line(df, x='date', y=ticker, width=1700, height=900)
    return fig


if __name__ == "__main__":
    app.run_server(debug=True)
