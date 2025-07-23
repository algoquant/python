""" This is a Dash web app with CSS markup. """
""" It doesn't do anything but only writes some formatted text. """

# https://dash.plotly.com/external-resources
# Created folder /assets in the same directory as the Dash app: /Users/jerzy/Develop/Python/
# The .css files are in the folder /assets 
# This will affect all the Dash apps in the parent directory /Users/jerzy/Develop/Python/

# Run this Dash app as follows:
# In a terminal run:
# python3 /Users/jerzy/Develop/Python/dash_css.py
# Then in the browser open the url:
# http://127.0.0.1:8050/



from dash import Dash, html, dcc

app = Dash(__name__)

app.layout = html.Div([
    html.Div(
        className="app-header",
        children=[
            html.Div('Plotly Dash', className="app-header--title")
        ]
    ),
    html.Div(
        children=html.Div([
            html.H5('Overview'),
            html.Div('''
                This is an example of a simple Dash app with
                local, customized CSS.
            ''')
        ])
    )
])

if __name__ == '__main__':
    app.run_server(debug=True)
