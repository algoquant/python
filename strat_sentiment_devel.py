# -*- coding: utf-8 -*-
"""
Script for simulating a strategy using Covid sentiment data.

"""

# Import packages for matrices and data frames
import numpy as np
import pandas as pd


## Load data from Excel file
se_ries = pd.read_excel(r'C:/Develop/predictive/data/Impact of Covid News on Equities.xlsx', 
                        sheet_name='dailies')

# Get data frame info
se_ries.info()
# Get column types
type(se_ries)
se_ries.dtypes
# Get dimensions
se_ries.shape


# Get column names and coerce them to pandas series
cols = se_ries.columns.to_series()
# Remove leading and trailing spaces
cols = cols.apply(lambda col: col.strip())
cols[8] = 'sentiment'
# Rename columns
se_ries.columns = cols


# Select only some columns by name
# se_ries = se_ries[['date', 'amzn', 'spy', 'bac', 'qqq', 'vxx', 'sentiment_n', 'sentiment_p']]
se_ries = se_ries[['date', 'amzn', 'spy', 'bac', 'qqq', 'vxx', 'sentiment']]

# Remove rows containing NA values in spy column
se_ries.dropna(subset=['spy'], inplace=True)



# Calculate the total daily sentiment - same as 'sentiment daily'
# se_ries.loc[:, 'sentiment'] = se_ries['sentiment_n'] + se_ries['sentiment_p']
# sum(se_ries.sentiment - se_ries['sentiment daily'])
# Calculate the rolling average of sentiment
lagg = 5
# se_ries.loc[:, 'sent_roll'] = se_ries.sentiment.rolling(window=lagg).mean()
# se_ries.loc[0:lagg, 'sent_roll'] = 0
se_ries.loc[:, 'sent_roll'] = se_ries.sentiment.ewm(span=lagg, adjust=False).mean()
se_ries.loc[0, 'sent_roll'] = 0


# Calculate the daily dollar returns
sym_bols = ['amzn', 'spy', 'bac', 'qqq', 'vxx']
# Create symbols for the returns
symbols_rets = [(lambda x: (x + '_rets'))(x) for x in sym_bols]
# Calculate the returns and add columns
se_ries[symbols_rets] = se_ries[sym_bols].diff()
# Set NA values to zero
# se_ries.loc[0, symbols_rets] = 0

# Calculate column means
se_ries.mean()

# Create symbols for the moving averages of returns
# symbols_ma = [(lambda x: (x + '_ma'))(x) for x in sym_bols]
# Calculate the rolling averages of returns
# se_ries[symbols_ma] = se_ries[sym_bols].rolling(window=5).mean()



## Simulate a Crossover Strategy for the Moving Averages of Covid Sentiment

# Convert the date column to datetime type
in_dex = pd.to_datetime(se_ries.date)

# Select symbol
sym_bols = ['amzn', 'spy', 'bac', 'qqq', 'vxx']
sym_bol = sym_bols[1]

# Calculate asset log returns
return_s = np.log(se_ries[sym_bol]).diff()
return_s[0] = 0

# Calculate the fast and slow moving averages of sentiment
lagg1 = 5
se_ries.loc[:, 'sent_fast'] = se_ries.sentiment.ewm(span=lagg1, adjust=False).mean()
se_ries.loc[0, 'sent_fast'] = 0
lagg2 = 21
se_ries.loc[:, 'sent_slow'] = se_ries.sentiment.ewm(span=lagg2, adjust=False).mean()
se_ries.loc[0, 'sent_slow'] = 0


# Calculate the sentiment indicator equal to the difference 
# of the fast moving average minus the slow moving average.
indica_tor = se_ries.sent_fast - se_ries.sent_slow
# Indica_tor is equal to the sign of the indica_tor
indica_tor = indica_tor.apply(np.sign)
# Lag the positions by 1 period
position_s = indica_tor.shift(1)
position_s[0] = 0

# Calculate cumulative strategy returns
strategy_returns = position_s * return_s
strategy_returns = strategy_returns.cumsum()
asset_cum_returns = return_s.cumsum()

import matplotlib.pyplot as plt

# Create plot objects for plotting in two panels
fig_ure, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18), 
                                   gridspec_kw={'height_ratios': [3, 1]})

# Plot strategy cumulative returns
ax1.set_title(sym_bol + ' Strategy Cumulative Log Returns', size=16)
ax1.plot(in_dex, asset_cum_returns, label=sym_bol, linewidth=2, color='blue')
ax1.plot(in_dex, strategy_returns, label='Strategy', linewidth=2, color='red')
ax1.set_ylabel('Returns', size=12)

# Add legend
leg_end = ax1.legend(loc='best', prop=dict(size=14))
for line in leg_end.get_lines():
    line.set_linewidth(10)

# Plot strategy positions
ax2.set_title('Strategy Risk Positions', size=14)
ax2.plot(in_dex, position_s, label='Trading Positions')
ax2.set_ylabel('Positions', size=12)

# Set tight plot layout
fig_ure.tight_layout()
# Render the plot
plt.show()



## Simulate a Sentiment Strategy using the moving average of change in sentiment

# Convert the date column to datetime type
in_dex = pd.to_datetime(se_ries.date)

# Select symbol
sym_bols = ['amzn', 'spy', 'bac', 'qqq', 'vxx']
sym_bol = sym_bols[3]

# Calculate asset log returns
return_s = np.log(se_ries[sym_bol]).diff()
return_s[0] = 0

# Calculate the rolling average of change in sentiment
lagg = 41
# se_ries.loc[:, 'sent_roll'] = se_ries.sentiment.diff().rolling(window=lagg).mean()
se_ries.loc[:, 'sent_roll'] = se_ries.sentiment.diff().ewm(span=lagg, adjust=False).mean()
# se_ries.loc[0:lagg, 'sent_roll'] = 0
se_ries.loc[0, 'sent_roll'] = 0

# Calculate positions equal to the sign of the rolling change in sentiment
position_s = se_ries.sent_roll
position_s = position_s.apply(np.sign)
# Lag the positions by 1 period
position_s = position_s.shift(1)
position_s[0] = 0

# Calculate cumulative strategy returns
strategy_returns = position_s * return_s
strategy_returns = strategy_returns.cumsum()
asset_cum_returns = return_s.cumsum()

import matplotlib.pyplot as plt

# Create plot objects for plotting in two panels
fig_ure, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18), 
                                   gridspec_kw={'height_ratios': [3, 1]})

# Plot strategy cumulative returns
ax1.set_title(sym_bol + ' Strategy Cumulative Log Returns', size=16)
ax1.plot(in_dex, asset_cum_returns, label=sym_bol, linewidth=2, color='blue')
ax1.plot(in_dex, strategy_returns, label='Strategy', linewidth=2, color='red')
ax1.set_ylabel('Returns', size=12)

# Add legend
leg_end = ax1.legend(loc='best', prop=dict(size=14))
for line in leg_end.get_lines():
    line.set_linewidth(10)

# Plot strategy positions
ax2.set_title('Strategy Risk Positions', size=14)
ax2.plot(in_dex, position_s, label='Trading Positions')
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
ax1.plot(in_dex, se_ries.sentiment, label='sentiment', linewidth=2, color='black')
ax1.plot(in_dex, se_ries.sent_fast, label='fast_ma', linewidth=2, color='red')
ax1.plot(in_dex, se_ries.sent_slow, label='slow_ma', linewidth=2, color='blue')
ax1.set_ylabel('Sentiment', size=12)

# Add legend
leg_end = ax1.legend(loc='best', prop=dict(size=14))
for line in leg_end.get_lines():
    line.set_linewidth(10)

# Plot strategy positions
ax2.set_title('Sentiment Indicator', size=14)
ax2.plot(in_dex, indica_tor, label='Trading Positions')
ax2.set_ylabel('Indicator', size=12)

# Set tight plot layout
fig_ure.tight_layout()
# Render the plot
plt.show()



## Plot Prices and Sentiment with Two y-axis

import matplotlib.pyplot as plt

# Convert the date column to datetime type
in_dex = pd.to_datetime(se_ries.date)
# Set the time index of se_ries
# se_ries = se_ries.set_index(in_dex)
# Remove date column
# se_ries = se_ries.drop('date', axis=1)


# Set all fonts to bold
# plt.rcParams["font.weight"] = "bold"
# plt.rcParams["axes.labelweight"] = "bold"


## Plot SPY and Sentiment - first method

# Create plot window with subplots
fig_ure, (ax1, ax3) = plt.subplots(2, 1, figsize=(16, 18), 
                                   gridspec_kw={'height_ratios': [3, 1]})

# Create x-values
# x_val = np.arange(len(se_ries))

# Plot the first series
col_or = 'tab:red'
ax1.set_title(sym_bol + ' ETF and Moving Average Covid Sentiment Indicator', size=16)
ax1.set_xlabel('date', size=12)
ax1.set_ylabel(sym_bol, color=col_or, size=12)
series1 = ax1.plot(in_dex, se_ries.spy, label=sym_bol, linewidth=2, color=col_or)
# Change color of ticks
ax1.tick_params(axis='y', labelcolor=col_or)

# Plot the second series
# Create a second y-axis that shares the same x-axis
ax2 = ax1.twinx()
col_or = 'tab:blue'
ax2.set_ylabel('Sentiment', color=col_or, size=12)
series2 = ax2.plot(in_dex, indica_tor, label='Sentiment', linewidth=2, color=col_or)
ax2.tick_params(axis='y', labelcolor=col_or)
ax2.axhline(linewidth=2, color=col_or)

# Add legend with both lines
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
leg_end = ax2.legend(lines1 + lines2, labels1 + labels2, loc='best', prop=dict(size=14))
# Make legend lines wider
for line in leg_end.get_lines():
    line.set_linewidth(10)

# Plot strategy positions
ax3.set_title('Strategy Risk Positions', size=14)
ax3.plot(in_dex, position_s, label='Trading Positions')
ax3.set_ylabel('Positions', size=12)

# Set tight plot layout
fig_ure.tight_layout()
# Render the plot
plt.show()


## Alternative plot method - not as nice legend

# Create plot window
fig_ure = plt.figure(figsize=(12, 7))

# Plot the first series
col_or = 'tab:red'
ax1 = fig_ure.add_subplot(111)
ax1.set_ylabel('SPY', color=col_or, size=12)
ax1.plot(in_dex, se_ries.spy, label='SPY', color=col_or)
# Change color of ticks
ax1.tick_params(axis='y', labelcolor=col_or)

# Plot the second series
ax2 = ax1.twinx()
col_or = 'tab:blue'
ax2.set_ylabel('Sentiment', color=col_or, size=12)
ax2.plot(in_dex, se_ries.sent_roll, label='Sentiment', color=col_or)
# Change color of ticks
ax2.tick_params(axis='y', labelcolor=col_or)

# Add legend with both lines
leg_end = fig_ure.legend(loc="upper left")
# Make legend lines wider
for line in leg_end.get_lines():
    line.set_linewidth(10)

