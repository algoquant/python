
# Plot SPY and TLT with two y-axes using matplotlib and Plotly.
# Plotly plotfig.show() doesn't open the browser and instead returns to the console the figure object.

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Load SPY and TLT data from CSV files
spy = pd.read_csv("/Users/jerzy/Develop/data/etfdaily/SPY_daily.csv", parse_dates=True, date_format="%Y-%m-%d", index_col="Index")
# isinstance(spy.index, pd.DatetimeIndex)
# spy.index = pd.to_datetime(spy.index)
tlt = pd.read_csv("/Users/jerzy/Develop/data/etfdaily/TLT_daily.csv", parse_dates=True, date_format="%Y-%m-%d", index_col="Index")
# tlt.index = pd.to_datetime(tlt.index)

# Combine the Close prices into a single DataFrame
combined = pd.concat([spy["SPY.Close"], tlt["TLT.Close"]], axis=1)
# Rename the columns
combined.columns = ["SPY", "TLT"]
# Remove NA values (if any)
combined = combined.dropna()
# Calculate the log stock prices
combined[["SPY", "TLT"]] = np.log(combined[["SPY", "TLT"]])

# Plot SPY using matplotlib
plt.figure()
plt.plot(combined.index, combined["SPY"], label="SPY", color="blue")
plt.title("SPY Log Prices")
plt.xlabel("Time")
plt.ylabel("Log Price")
# plt.xticks(rotation=45)
plt.show()

# Plot SPY using Plotly
plotfig = go.Figure(go.Scatter(x=combined.index, y=combined["SPY"]))
plotfig = plotfig.update_layout(title="SPY", yaxis_title="Log Price", xaxis_rangeslider_visible=False, 
            title_font_size=12)
# Save the plot as an HTML file
plotfig.write_html("/Users/jerzy/Develop/Python/figure.html")
# Render the plot - but it doesn't open the browser and returns the figure object
plotfig.show()

### Plot SPY and TLT with two y-axes using matplotlib

fig, ax1 = plt.subplots(figsize=(10, 6))

color1 = "tab:blue"
color2 = "tab:red"

# Plot SPY on the left y-axis
ax1.set_xlabel("Date")
ax1.set_ylabel("SPY (log)", color=color1)
ax1.plot(combined.index, combined["SPY"], color=color1, label="SPY")
ax1.tick_params(axis="y", labelcolor=color1)

# Create a second y-axis for TLT
ax2 = ax1.twinx()
ax2.set_ylabel("TLT (log)", color=color2)
ax2.plot(combined.index, combined["TLT"], color=color2, label="TLT")
ax2.tick_params(axis="y", labelcolor=color2)

# Title and legend
plt.title("SPY and TLT Log Prices with Two Y-Axes")
fig.tight_layout()
fig.legend(loc="upper left", bbox_to_anchor=(0.1, 0.9))
plt.show()


### Plot SPY and TLT with two y-axes using Plotly

# Create figure with secondary y-axis
plotfig = make_subplots(specs=[[{"secondary_y": True}]])
# Add traces
plotfig.add_trace(
    go.Scatter(x=combined.index, y=combined["SPY"], name="SPY"),
    secondary_y=False,
)
plotfig.add_trace(
    go.Scatter(x=combined.index, y=combined["TLT"], name="TLT"),
    secondary_y=True,
)
# Add figure title
plotfig.update_layout(
title={
        "text": "SPY and TLT With Two Y-Axis",
        "font": {"size": 24},
        "font_weight": "bold"
    },
    # Legend text size is set to 20px
    legend=dict(x=0.01, y=0.99,  font=dict(size=20))
)
# Set line widths
plotfig.update_traces(line=dict(width=2))
plotfig.update_layout(legend=dict(itemsizing="constant", font=dict(family="sans-serif", size=18, color="black")))
# Set x-axis title
plotfig.update_xaxes(title_text="Year")
# Set y-axes titles
plotfig.update_yaxes(title_text="<b>SPY</b> yaxis", secondary_y=False)
plotfig.update_yaxes(title_text="<b>TLT</b> yaxis", secondary_y=True)

# Save the plot as an HTML file
plotfig.write_html("/Users/jerzy/Develop/Python/figure.html")
# Render the plot - but it doesn't open the browser and returns the figure object
# plotfig.show()


