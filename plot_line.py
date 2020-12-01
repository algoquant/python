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
x_val = np.linspace(0, 2*np.pi, 1000)
y_val = np.sin(x_val**2)
fig_ure = px.line(x=x_val, y=y_val, labels={'x':'t', 'y':'cos(t)'})
fig_ure.update_layout(title='Sine Function', yaxis_title='Sine', xaxis_rangeslider_visible=False)
# Plot interactive plot in browser and save to html file
plot(fig_ure, filename='sine_wave.html', auto_open=True)


## Matplotlib simple line plot

import matplotlib.pyplot as plt

# Create plot panel
fig_ure = plt.figure()
fig_ure.set_figwidth(10)
fig_ure.set_figheight(6)
# Plot in panel
plt.plot(x_val, y_val, label='Function', linewidth=2, color='blue')
plt.ylabel('y_val', size=14)
plt.xlabel('x_val', size=14)
plt.title('Sine of Squared Function', size=14)
leg_end = plt.legend(loc='upper left', prop=dict(size=12))
for line in leg_end.get_lines():
    line.set_linewidth(10)
plt.show()


## Matplotlib with two y-axis
# https://matplotlib.org/gallery/api/two_scales.html


# Create some numpy data
t = np.arange(0.01, 10.0, 0.01)
data1 = np.exp(t)
data2 = np.sin(2 * np.pi * t)

# Create plot window with subplots
fig, ax1 = plt.subplots()

color = 'tab:red'
ax1.set_xlabel('time (s)')
ax1.set_ylabel('exp', color=color)
ax1.plot(t, data1, color=color)
# Change color of ticks
ax1.tick_params(axis='y', labelcolor=color)

# Create a second y-axis that shares the same x-axis
ax2 = ax1.twinx()

color = 'tab:blue'
ax2.set_ylabel('sin', color=color)
ax2.plot(t, data2, color=color)
ax2.tick_params(axis='y', labelcolor=color)

# Set plot layout - otherwise the right y-label is slightly clipped
fig.tight_layout()
plt.show()


