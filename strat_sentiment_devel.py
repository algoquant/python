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

# Get data frame info
tseries.info()
# Get column types
type(tseries)
tseries.dtypes
# Get dimensions
tseries.shape


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



# Calculate the total day sentiment - same as 'sentiment day'
# tseries.loc[:, 'sentiment'] = tseries['sentiment_n'] + tseries['sentiment_p']
# sum(tseries.sentiment - tseries['sentiment day'])
# Calculate the rolling average of sentiment
lagg = 5
# tseries.loc[:, 'sent_roll'] = tseries.sentiment.rolling(window=lagg).mean()
# tseries.loc[0:lagg, 'sent_roll'] = 0
tseries.loc[:, 'sent_roll'] = tseries.sentiment.ewm(span=lagg, adjust=False).mean()
tseries.loc[0, 'sent_roll'] = 0


# Calculate the daily dollar returns
symbolv = ['amzn', 'spy', 'bac', 'qqq', 'vxx']
# Create symbols for the returns
symbols_rets = [(lambda x: (x + '_rets'))(x) for x in symbolv]
# Calculate the returns and add columns
tseries[symbols_rets] = tseries[symbolv].diff()
# Set NA values to zero
# tseries.loc[0, symbols_rets] = 0

# Calculate column means
tseries.mean()

# Create symbols for the moving averages of returns
# symbols_ma = [(lambda x: (x + '_ma'))(x) for x in symbolv]
# Calculate the rolling averages of returns
# tseries[symbols_ma] = tseries[symbolv].rolling(window=5).mean()



## Simulate a Crossover Strategy for the Moving Averages of Covid Sentiment

# Convert the date column to datetime type
indeks = pd.to_datetime(tseries.date)

# Select symbol
symbolv = ['amzn', 'spy', 'bac', 'qqq', 'vxx']
symbol = symbolv[1]

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
retstrat = posit * retsp
retstrat = retstrat.cumsum()
retsum = retsp.cumsum()

import matplotlib.pyplot as plt

# Create plot objects for plotting in two panels
plotfig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18), 
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
plotfig.tight_layout()
# Render the plot
plt.show()



## Simulate a Sentiment Strategy using the moving average of change in sentiment

# Convert the date column to datetime type
indeks = pd.to_datetime(tseries.date)

# Select symbol
symbolv = ['amzn', 'spy', 'bac', 'qqq', 'vxx']
symbol = symbolv[3]

# Calculate asset log returns
retsp = np.log(tseries[symbol]).diff()
retsp[0] = 0

# Calculate the rolling average of change in sentiment
lagg = 41
# tseries.loc[:, 'sent_roll'] = tseries.sentiment.diff().rolling(window=lagg).mean()
tseries.loc[:, 'sent_roll'] = tseries.sentiment.diff().ewm(span=lagg, adjust=False).mean()
# tseries.loc[0:lagg, 'sent_roll'] = 0
tseries.loc[0, 'sent_roll'] = 0

# Calculate positions equal to the sign of the rolling change in sentiment
posit = tseries.sent_roll
posit = posit.apply(np.sign)
# Lag the positions by 1 period
posit = posit.shift(1)
posit[0] = 0

# Calculate cumulative strategy returns
retstrat = posit * retsp
retstrat = retstrat.cumsum()
retsum = retsp.cumsum()

import matplotlib.pyplot as plt

# Create plot objects for plotting in two panels
plotfig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18), 
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
plotfig.tight_layout()
# Render the plot
plt.show()



## Plot Sentiment and its Moving Averages

# Create plot objects for plotting in two panels
plotfig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18), 
                                   gridspec_kw={'height_ratios': [3, 1]})

# Plot strategy cumulative returns
ax1.set_title('Covid Sentiment and its Moving Averages', size=16)
ax1.plot(indeks, tseries.sentiment, label='sentiment', linewidth=2, color='black')
ax1.plot(indeks, tseries.sent_fast, label='fast_ma', linewidth=2, color='red')
ax1.plot(indeks, tseries.sent_slow, label='slow_ma', linewidth=2, color='blue')
ax1.set_ylabel('Sentiment', size=12)

# Add legend
legendo = ax1.legend(loc='best', prop=dict(size=14))
for line in legendo.get_lines():
    line.set_linewidth(10)

# Plot strategy positions
ax2.set_title('Sentiment Indicator', size=14)
ax2.plot(indeks, indic, label='Trading Positions')
ax2.set_ylabel('Indicator', size=12)

# Set tight plot layout
plotfig.tight_layout()
# Render the plot
plt.show()



## Plot Prices and Sentiment with Two y-axis

import matplotlib.pyplot as plt

# Convert the date column to datetime type
indeks = pd.to_datetime(tseries.date)
# Set the time index of tseries
# tseries = tseries.set_index(indeks)
# Remove date column
# tseries = tseries.drop('date', axis=1)


# Set all fonts to bold
# plt.rcParams["font.weight"] = "bold"
# plt.rcParams["axes.labelweight"] = "bold"


## Plot SPY and Sentiment - first method

# Create plot window with subplots
plotfig, (ax1, ax3) = plt.subplots(2, 1, figsize=(16, 18), 
                                   gridspec_kw={'height_ratios': [3, 1]})

# Create x-values
# xvar = np.arange(len(tseries))

# Plot the first series
color = 'tab:red'
ax1.set_title(symbol + ' ETF and Moving Average Covid Sentiment Indicator', size=16)
ax1.set_xlabel('date', size=12)
ax1.set_ylabel(symbol, color=color, size=12)
series1 = ax1.plot(indeks, tseries.spy, label=symbol, linewidth=2, color=color)
# Change color of ticks
ax1.tick_params(axis='y', labelcolor=color)

# Plot the second series
# Create a second y-axis that shares the same x-axis
ax2 = ax1.twinx()
color = 'tab:blue'
ax2.set_ylabel('Sentiment', color=color, size=12)
series2 = ax2.plot(indeks, indic, label='Sentiment', linewidth=2, color=color)
ax2.tick_params(axis='y', labelcolor=color)
ax2.axhline(linewidth=2, color=color)

# Add legend with both lines
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
legendo = ax2.legend(lines1 + lines2, labels1 + labels2, loc='best', prop=dict(size=14))
# Make legend lines wider
for line in legendo.get_lines():
    line.set_linewidth(10)

# Plot strategy positions
ax3.set_title('Strategy Risk Positions', size=14)
ax3.plot(indeks, posit, label='Trading Positions')
ax3.set_ylabel('Positions', size=12)

# Set tight plot layout
plotfig.tight_layout()
# Render the plot
plt.show()


## Alternative plot method - not as nice legend

# Create plot window
plotfig = plt.figure(figsize=(12, 7))

# Plot the first series
color = 'tab:red'
ax1 = plotfig.add_subplot(111)
ax1.set_ylabel('SPY', color=color, size=12)
ax1.plot(indeks, tseries.spy, label='SPY', color=color)
# Change color of ticks
ax1.tick_params(axis='y', labelcolor=color)

# Plot the second series
ax2 = ax1.twinx()
color = 'tab:blue'
ax2.set_ylabel('Sentiment', color=color, size=12)
ax2.plot(indeks, tseries.sent_roll, label='Sentiment', color=color)
# Change color of ticks
ax2.tick_params(axis='y', labelcolor=color)

# Add legend with both lines
legendo = plotfig.legend(loc="upper left")
# Make legend lines wider
for line in legendo.get_lines():
    line.set_linewidth(10)

