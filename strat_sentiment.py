# -*- coding: utf-8 -*-
"""
Script for simulating a strategy using Covid sentiment data.

"""

# Import packages for matrices and data frames
import numpy as np
import pandas as pd


## Load data from Excel file and format the time index
se_ries = pd.read_excel(r'C:/Develop/predictive/data/Impact of Covid News on Equities.xlsx', 
                        sheet_name='dailies')

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



## Simulate a Crossover Strategy for the Moving Averages of Covid Sentiment

# Convert the date column to datetime type
in_dex = pd.to_datetime(se_ries.date)

# Define symbols
sym_bols = ['amzn', 'spy', 'bac', 'qqq', 'vxx']
# Modify this to select symbol to trade: 
sym_bol = sym_bols[3]

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


# Calculate differences between the rolling averages
position_s = se_ries.sent_fast - se_ries.sent_slow
# Positions are equal to the sign of the differences
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
ax1.plot(in_dex, se_ries.sent_fast, label='sent_fast', linewidth=2, color='red')
ax1.plot(in_dex, se_ries.sent_slow, label='sent_slow', linewidth=2, color='blue')
ax1.set_ylabel('Sentiment', size=12)

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

