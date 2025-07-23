# Load minute bar prices from a CSV file.
import pandas as pd
filen = "/Users/jerzy/Develop/data/minutes/SPY/2024-02-29.csv"
# ohlc = pd.read_csv(filen, parse_dates=["Index"], index_col="Index")
ohlc = pd.read_csv(filen, parse_dates=["Index"])
ohlc.keys()
pricev = ohlc["SPY.Close"]
pricev
pricev.plot()


## Plot the minute prices using matplotlib

import matplotlib.pyplot as plt

plt.plot(pricev)
plt.plot(pricev.index, pricev)
plt.show()
# Plot the minute volumes using matplotlib
voluv = ohlc["SPY.Volume"]
plt.plot(voluv.index, voluv)
plt.show()

# Plot the minute prices using pyplot - doesn't show the time index
from matplotlib import pyplot
pyplot.plot(pricev.index, pricev)
pyplot.show()


## Plotly dynamic interactive time series plots using plotly.graph_objects

import plotly.graph_objects as go
from plotly.offline import plot

# Create plotly graph object from data frame
plotfig = go.Figure([go.Scatter(x=ohlc["Index"], y=pricev)])
# Add time stamps to x-axis
plotfig.update_xaxes(
#    dtick = "M1",
    tickformat = "%H:%M"
)
# Add title and y-axis label
plotfig.update_layout(title="SPY Minute Prices", yaxis_title="Price", xaxis_rangeslider_visible=False)
# Render interactive plot in browser
plotfig.show()
# Render interactive plot in browser and save to html file
plot(plotfig, filename="stock_prices.html", auto_open=True)


