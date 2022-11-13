# -*- coding: utf-8 -*-
"""
Script for simulating a strategy using Covid sentiment data.

"""

# Import packages for matrices and data frames
import numpy as np
import pandas as pd


## Load data from Excel file
tseries = pd.read_excel(r'/Users/jerzy/Develop/data/Impact of Covid News on Equities.xlsx', 
                        sheet_name='dailies')

# Get column names and coerce them to pandas series
cols = tseries.columns.to_series()
# Remove leading and trailing spaces
cols = cols.apply(lambda col: col.strip())
cols[8] = 'sentiment'
# Rename columns
tseries.columns = cols


# Select only some columns by name
# tseries = tseries[['date', 'amzn', 'spy', 'bac', 'qqq', 'vxx', 'sentiment_n', 'sentiment_p']]
tseries = tseries[['date', 'amzn', 'spy', 'bac', 'qqq', 'vxx', 'sentiment']]

# Remove rows containing NA values in spy column
tseries.dropna(subset=['spy'], inplace=True)



## Simulate a Crossover Strategy for the Moving Averages of Covid Sentiment

# Convert the date column to datetime type
indeks = pd.to_datetime(tseries.date)

# Define symbols
symbolv = ['amzn', 'spy', 'bac', 'qqq', 'vxx']
# Modify this to select symbol to trade: 
symbol = symbolv[3]

# Calculate asset log returns
retsp = np.log(tseries[symbol]).diff()
retsp[0] = 0

# Calculate the fast and slow moving averages of sentiment
lagg1 = 5
tseries.loc[:, 'sent_fast'] = tseries.sentiment.ewm(span=lagg1, adjust=False).mean()
tseries.loc[0, 'sent_fast'] = 0
lagg2 = 21
tseries.loc[:, 'sent_slow'] = tseries.sentiment.ewm(span=lagg2, adjust=False).mean()
tseries.loc[0, 'sent_slow'] = 0


# Calculate the sentiment indicator equal to the difference 
# of the fast moving average minus the slow moving average.
indic = tseries.sent_fast - tseries.sent_slow
# Indica_tor is equal to the sign of the indic
indic = indic.apply(np.sign)
# Lag the positions by 1 period
posit = indic.shift(1)
posit[0] = 0

# Calculate cumulative strategy returns
retstrat = posit*retsp
retstrat = retstrat.cumsum()
retsum = retsp.cumsum()

import matplotlib.pyplot as plt

# Create plot objects for plotting in two panels
fig_ure, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18), 
                                   gridspec_kw={'height_ratios': [3, 1]})

# Plot strategy cumulative returns
ax1.set_title(symbol + ' Strategy Cumulative Log Returns', size=16)
ax1.plot(indeks, retsum, label=symbol, linewidth=2, color='blue')
ax1.plot(indeks, retstrat, label='Strategy', linewidth=2, color='red')
ax1.set_ylabel('Returns', size=12)

# Add legend
legendo = ax1.legend(loc='best', prop=dict(size=14))
for line in legendo.get_lines():
    line.set_linewidth(10)

# Plot strategy positions
ax2.set_title('Strategy Risk Positions', size=14)
ax2.plot(indeks, posit, label='Trading Positions')
ax2.set_ylabel('Positions', size=12)

# Set tight plot layout
fig_ure.tight_layout()
# Render the plot
plt.show()



## Plot Sentiment and its Moving Averages

# Create plot objects for plotting in two panels
fig_ure, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18), 
                                   gridspec_kw={'height_ratios': [3, 1]})

# Plot strategy cumulative returns
ax1.set_title('Covid Sentiment and its Moving Averages', size=16)
ax1.plot(indeks, tseries.sentiment, label='sentiment', linewidth=2, color='black')
ax1.plot(indeks, tseries.sent_fast, label='sent_fast', linewidth=2, color='red')
ax1.plot(indeks, tseries.sent_slow, label='sent_slow', linewidth=2, color='blue')
ax1.set_ylabel('Sentiment', size=12)

# Add legend
legendo = ax1.legend(loc='best', prop=dict(size=14))
for line in legendo.get_lines():
    line.set_linewidth(10)

# Plot strategy positions
ax2.set_title('Strategy Risk Positions', size=14)
ax2.plot(indeks, posit, label='Trading Positions')
ax2.set_ylabel('Positions', size=12)

# Set tight plot layout
fig_ure.tight_layout()
# Render the plot
plt.show()

