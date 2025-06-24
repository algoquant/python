# -*- coding: utf-8 -*-
'''
Script for market data wrangling in Python.
Mostly pandas and numpy data frames and time series.

https://towardsdatascience.com/a-checklist-for-data-wrangling-8f106c093fef
https://stackoverflow.com/questions/36814100/pandas-to-numeric-for-multiple-columns
https://stackoverflow.com/questions/44117326/how-can-i-remove-all-non-numeric-characters-from-all-the-values-in-a-particular

Note about 'axis' parameter in pandas:
https://stackoverflow.com/questions/22149584/what-does-axis-in-pandas-mean
    axis = 'index' (axis=0) means calculate by columns
    axis = 'columns' (axis=1) means calculate by rows

'''

## Import packages for matrices and data frames
import numpy as np
import pandas as pd

# Ignore FutureWarning
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


## Load data frame from CSV file

# Load student scores data from CSV file
scoredf = pd.read_csv('/Users/jerzy/Develop/lecture_slides/data/student_scores.csv')

# Get data frame info
scoredf.info()
# Set default: Display all the columns in output
pd.set_option('display.max_columns', None)
scoredf

# Get column types
type(scoredf)
scoredf.dtypes

# Get dimensions
scoredf.shape
# Get number of rows
len(scoredf)

# Select element in third row and fifth column
scoredf.iloc[2, 4]

# Select whole rows by number range
scoredf.iloc[2:4, :]

# Print column names
scoredf.columns

# Select single column by name
scoredf['HW1_score']
scoredf.HW1_score
# Select multiple columns by name
scoredf[['HW1_score', 'HW2_score', 'HW3_score']]
# Select columns by number range
scoredf.iloc[:, 2:4]
# Select columns by numbers
scoredf.iloc[:, [1, 3, 4]]

# Select rows except one of them
scoredf.drop(5, axis=0)
# Select columns except one of them
scoredf.drop('HW1_score', axis=1)

# Get unique values in column
scoredf['finance_track'].unique()
# Get number of unique values in column
scoredf['finance_track'].nunique()
# Get number of rows for each unique value
scoredf['finance_track'].value_counts()

# Calculate column means
scoredf.mean()
# Doesn't work for columns with some non-numeric values
scoredf['HW1_score'].mean()

# Get number of NaN values in each column
scoredf.isna().sum()
scoredf.isnull().sum()

# Get percentage of NaN values in each column
100*scoredf.isnull().sum()/len(scoredf)

# Remove all rows containing NA values
scoredf.dropna()
# Remove all columns containing NA values
scoredf.dropna(axis=1)
# Remove columns with less than 5 NaN values
scoredf.dropna(axis=1, thresh=5)

# Replace all NA values with -9999
scoredf.fillna(-9999)
# Replace NA values in specific column
scoredf['HW1_score'].fillna(-9999)
# Replace specific cell value
scoredf.at[1, 'HW1_score'] = 9999
# Fill NA values with NaN
scoredf.fillna(np.NaN)
# Fill NA values with strings
scoredf.fillna('data missing')
# Fill missing values with mean column values
# Doesn't work if there are some non-numeric values in a column
scoredf.fillna(scoredf.mean())

# Coerce column to numeric and replace non-numeric with NA
# Works only for single column
# pd.to_numeric(scoredf[['test1_score', 'test2_score']], errors='coerce')
scorest = pd.to_numeric(scoredf['test1_score'], errors='coerce')
# Replace NA values with mean column value
scorest.fillna(scorest.mean())
# Replace NA values of specific columns with mean value
# Doesn't work because there are some non-numeric values in the column
scoredf['HW1_score'].fillna(scoredf['HW1_score'].mean())
# Get names of columns except the first two
cols = scoredf.columns[2:]
# Coerce selected columns to numeric and replace non-numeric with NA
scoredf[cols] = scoredf[cols].apply(pd.to_numeric, errors='coerce')
# Fill NA values with column means
scoredf = scoredf.fillna(scoredf.mean(axis=0))
# Replace NA values with row means
# https://stackoverflow.com/questions/33058590/pandas-dataframe-replacing-nan-with-row-average
scoredf = scoredf.T.fillna(scoredf.mean(axis=1)).T
# Or using lambda function
scoredf[cols] = scoredf[cols].apply(lambda row: row.fillna(row.mean()), axis=1)
# Interpolate single column
scoredf['HW1_score'].interpolate()
# Replace NA values with interpolation of columns
scoredf.interpolate()
# Replace NA values with interpolation of rows
scoredf[cols].interpolate(axis=1)

# Add new column calculated from existing columns
scoredf.loc[:, 'test1_sum'] = scoredf['test1_score'] + scoredf['test2_score']
# Rename the last column
cols = scoredf.columns.values
cols[-1, ] = 'tests_sum'
scoredf.columns = cols

# Continue with replace()
# https://towardsdatascience.com/a-checklist-for-data-wrangling-8f106c093fef

# Add LOCF - pandas ffill()
# https://stackoverflow.com/questions/47024931/how-to-fill-missing-dates-in-pandas-dataframe
# https://stackoverflow.com/questions/27905295/how-to-replace-nans-by-preceding-values-in-pandas-dataframe

# Write data frame to CSV file
scoredf.to_csv('output.csv')

# Delete the object
del scoredf


## Removing outliers using zscores
# https://stackoverflow.com/questions/69735372/futurewarning-automatic-reindexing-on-dataframe-vs-series-comparisons-is-deprec

# Need to define df first
numerical_cols = df.select_dtypes(['int64','float64'])
for col in numerical_cols:
    feature_value_less_than_3sigma = df[col].mean()-3*(df[col].std())
    feature_value_greater_than_3sigma = df[col].mean()+3*(df[col].std())
    df = df[~((df[col].lt(feature_value_less_than_3sigma)) | (df[col].gt(feature_value_greater_than_3sigma)))]
    df = df[~((df[col] < (feature_value_less_than_3sigma)) | (df[col] > (feature_value_greater_than_3sigma)))]
else:
    print('\nAfter: ', df.shape)


## Load single intraday prices from CSV file

# Import datetime for dates and times
# Don't import the whole module because it requires the double datetime syntax
# import datetime
from datetime import date, datetime, timedelta

# Convert a list of datetime objects to a list of time objects
def datetime_list_to_time_list(datetime_list):
    time_list = [dt.time() for dt in datetime_list]
    return time_list

# Load time series of intraday prices from CSV file
pricev = pd.read_csv('/Users/jerzy/Develop/data/raw/SPY_second_20250610.csv')

# Add a time index to the data frame
pricev['timestamp'] = pd.to_datetime(pricev['timestamp']/1000, unit='s')
pricev['timestamp'] = time_list = datetime_list_to_time_list(pricev['timestamp'])
# Set the time index as the data frame index
pricev.set_index('timestamp', inplace=True)
# Print the first 5 rows of the data frame
pricev.head()


# Plot single time series using matplotlib

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# Plot the time series with the x-axis with date and time
plt.figure()
plt.plot(pricev.index, pricev['SPY.price'])
plt.title('SPY Price Time Series')
plt.xlabel('Time')
plt.ylabel('Price')
plt.xticks(rotation=45)
plt.show()

# Plot the time series with the x-axis with hours and minutes
# But it doesn't format the x-axis with time only - in hours and minutes
# Examples from Copilot don't work either - time is formatted as numbers
fig, ax = plt.subplots()
ax.plot(pricev.index, pricev['SPY.price'])
ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
# Format the x-axis to display dates as 'Hour/Minute'
date_format = mdates.DateFormatter('%H/%M') # Example format
ax.xaxis.set_major_formatter(date_format)
# ax.xaxis.set_major_locator(mdates.AutoDateLocator()) # Example locator
# fig.autofmt_xdate() # Rotate labels
# plt.xticks(rotation=45)
plt.show()



## Load OHLC prices from CSV file

# Load OHLC data from CSV file - the time index is formatted inside read_csv()
symboln = 'SPY'
ohlc = pd.read_csv('/Users/jerzy/Develop/lecture_slides/data/SPY_daily.csv')
ohlc.set_index('Index', inplace=True)
# Rename columns
ohlc.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
# Log of Open, High, Low, Close prices
ohlc.iloc[:,0:4] = np.log(ohlc.iloc[:,0:4])
ohlc.head()
ohlc.tail()

# Load OHLC data from CSV file and format the time index
# ohlc = pd.read_csv('/Users/jerzy/Develop/data/raw/SPY_second_20250610.csv', parse_dates=True, date_parser=datetime.fromtimestamp, index_col='timestamp')
# ohlc = pd.read_csv('/Volumes/external/Develop/data/SP500_2020/GOOGL.csv', parse_dates=True, date_parser=pd.to_datetime, index_col='index')

# Add a time index to the data frame
ohlc['timestamp'] = pd.to_datetime(ohlc['timestamp']/1000, unit='s')
# Set the time index as the data frame index
ohlc.set_index('timestamp', inplace=True)
# Print the first 5 rows of the data frame
ohlc.head()

# Get data frame info
ohlc.info()
# Get column types
type(ohlc)
ohlc.dtypes

# Get dimensions
ohlc.shape

# Print column names
ohlc.columns

# Pandas set default: Display all the columns in the output
# pd.set_option('display.max_columns', None)

# Extract time index
datev = ohlc.index

# Subset data frame
ohlc.iloc[0:5, :]

# Difference the Seconds column
diffsec = ohlc.Seconds.diff()


### Plot OHLC

## Plotly dynamic interactive time series plots using plotly.graph_objects

import plotly.graph_objects as go

import plotly.io as pio
pio.renderers.default = 'chrome'

# Select Close prices
closep = ohlc.Close
# Or
# closep = ohlc.iloc[:, 3]
# Class of closep
type(closep)

# Select time slice of data
ohlcsub = ohlc['2024':'2026']


# Create plotly line graph object from data frame
plotfig = go.Figure(go.Scatter(x=ohlcsub.index, y=ohlcsub.Close,))
plotfig = plotfig.update_layout(title='SPY', yaxis_title='Log Price', xaxis_rangeslider_visible=False, 
            title_font_size=12)

plotfig.show()

# Plot interactive plot in browser and save to html file
# pip3 install -U kaleido # Install Kaleido for static image export
# pip3 install ipykernel
# pip3 install --upgrade nbformat
plotfig.write_image('spy_log_prices.png', width=800, height=600, scale=2)
plotfig.show(renderer='svg')


## Plotly simple candlestick with moving average

plotfig = go.Figure(go.Candlestick(x=ohlcsub.index,
                open=ohlcsub.Open, high=ohlcsub.High, low=ohlcsub.Low, close=ohlcsub.Close, 
                name=symboln + ' Log OHLC Prices', showlegend=False))
plotfig.update_layout(title=symboln + ' Log OHLC Prices', 
                                title_font_size=24, title_font_color='blue', 
                                yaxis_title='Prices', font_color='black', font_size=18,
                                xaxis_rangeslider_visible=False)
# Calculate moving average stock prices
# closep = ohlc['Close']
lookback = 55
pricema = closep.ewm(span=lookback).mean()
# Add moving average
plotfig = plotfig.add_trace(go.Scatter(x=ohlcsub.index, y=pricema[ohlcsub.index], 
                            name='Moving Average', line=dict(color='red')))
# Customize legend
plotfig = plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder='normal',
                      font=dict(family='sans-serif', size=18, color='red')))
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename='stock_candlesticks.html', auto_open=True)
plotfig.show()




