#!/usr/bin/env python
# coding: utf-8

"""
Script for VWAP Moving Average Crossover Strategy
https://www.learndatasci.com/tutorials/python-finance-part-yahoo-finance-api-pandas-matplotlib/
https://www.learndatasci.com/tutorials/python-finance-part-2-intro-quantitative-trading-strategies/
https://www.learndatasci.com/tutorials/python-finance-part-3-moving-average-trading-strategy/
"""

# Import packages
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
# import mplfinance as mpf


## Load OHLC data from csv file and format the time index

se_ries = pd.read_csv('C:/Develop/data/SP500_2020/GOOGL.csv', parse_dates=True, date_parser=pd.to_datetime, index_col='index')
# Rename columns
se_ries.columns = ['Open', 'High', 'Low', 'Close', 'Volume']

# Calculate the fast and slow simple moving averages
# ma_fast = se_ries.Close.rolling(window=20).mean()
# Or
# ma_fastn = se_ries['Close'].rolling(window=20).mean()
# Compare them
# ma_fast.equals(ma_fastn)
# ma_slow = se_ries.Close.rolling(window=100).mean()
# Calculate EWMA
ma_fast = se_ries.Close.ewm(span=30, adjust=False).mean()
ma_slow = se_ries.Close.ewm(span=100, adjust=False).mean()

start_date = '2019-01-01'
end_date = '2020-04-17'

# Create plot objects
fig, ax = plt.subplots(figsize = (16, 9))

# Add plot objects
ax.plot(se_ries.loc[start_date:end_date, :].index, se_ries.loc[start_date:end_date, 'Close'], label = 'GOOG', linewidth = 2, color = 'red')
ax.plot(ma_slow.loc[start_date:end_date].index, ma_slow.loc[start_date:end_date], label = '100-days EWMA', linewidth = 2, color = 'green')
ax.plot(ma_fast.loc[start_date:end_date].index, ma_fast.loc[start_date:end_date], label = '30-days EWMA', linewidth = 2, color = 'blue')
ax.set_ylabel('Price in $', size = 14)

# Add legend
leg_end = ax.legend(loc='best', prop=dict(size=16))
# leg_end.get_frame().set_facecolor('grey')

for line in leg_end.get_lines():
    line.set_linewidth(10)

# Render the plot
plt.show()


## Simulate a Moving Average Crossover Strategy

# Calculate rolling VWAP
vwap = se_ries.Close
vol_ume = se_ries.Volume
vwap = vwap * vol_ume
vwap = vwap.rolling(window=150).sum()
vol_ume = vol_ume.rolling(window=150).sum()
vwap = vwap / vol_ume

# Calculate differences between the prices and the VWAP timeseries
position_s = se_ries.Close - vwap
# Positions are equal to the sign of the differences
position_s = position_s.apply(np.sign)
# Lag the positions by 1 period
position_s = position_s.shift(1)

# Calculate asset log returns
return_s = np.log(se_ries.Close).diff()

# Calculate cumulative strategy returns
strategy_returns = position_s * return_s
strategy_cum_returns = strategy_returns.cumsum()
asset_cum_returns = return_s.cumsum()

# Create plot objects for plotting in two panels
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 18))

# Plot strategy cumulative returns
ax1.plot(se_ries.index, asset_cum_returns, label = 'GOOG', linewidth = 2, color = 'b')
ax1.plot(se_ries.index, strategy_cum_returns, label = 'Strategy', linewidth = 2, color = 'r')
ax1.set_ylabel('Cumulative log returns', size = 14)

# Add legend
leg_end = ax1.legend(loc='best', prop=dict(size=16))
for line in leg_end.get_lines():
    line.set_linewidth(10)

# Plot strategy positions
ax2.plot(se_ries.index, position_s, label='Trading Positions')
ax2.set_ylabel('Trading Positions', size = 14)

# Render the plot
plt.show()
