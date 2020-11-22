#!/usr/bin/env python
# coding: utf-8

"""
Script for plotting an interactive line plot.
"""

# Import packages 
import numpy as np
# import plotly as py
# plotly.express for time series
import plotly.express as px
from plotly.offline import plot


## Line plot with Plotly Express
# https://plotly.com/python/line-and-scatter/

# Create line object
x_val = np.linspace(0, 8*np.pi, 1000)
fig_ure = px.line(x=x_val, y=np.cos(x_val), labels={'x':'t', 'y':'cos(t)'})
fig_ure.update_layout(title='Sine Function', yaxis_title='Sine', xaxis_rangeslider_visible=False)
# Plot interactive plot in browser and save to html file
plot(fig_ure, filename='sine_wave.html', auto_open=True)

