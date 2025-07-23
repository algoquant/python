""" This is a Dash App for Testing. """
""" Adapted from: """
""" https://dash.plotly.com/advanced-callbacks """

# Run this Dash app as follows:
# In a terminal run:
# python3 /Users/jerzy/Develop/Python/dash_clicks.py
# Then in the browser open the url:
# http://127.0.0.1:8051/

import dash
from dash.dependencies import Input, Output
from dash import html

print("Run startup code")



app = dash.Dash()
app.layout = html.Div(
    [
        html.Button(html.H1("execute callback", style={"color": "red"}), id="button_1"),
        html.Div(children="callback not executed", id="first_output_1"),
        html.Div(children="callback not executed", id="second_output_1"),
    ]
)


@app.callback(
    Output("first_output_1", "children"),
    Output("second_output_1", "children"),
    Input("button_1", "n_clicks")
)
def change_text(n_clicks):
    return ["n_clicks is " + str(n_clicks), "n_clicks is " + str(n_clicks)]

if __name__ == '__main__':
    app.run_server(debug=True, port=8051)
