# -*- coding: utf-8 -*-
"""
Script for data wrangling in Python.
Mostly pandas and numpy data frames and time series.

https://towardsdatascience.com/a-checklist-for-data-wrangling-8f106c093fef
https://stackoverflow.com/questions/36814100/pandas-to-numeric-for-multiple-columns
https://stackoverflow.com/questions/44117326/how-can-i-remove-all-non-numeric-characters-from-all-the-values-in-a-particular

Note about 'axis' parameter in pandas:
https://stackoverflow.com/questions/22149584/what-does-axis-in-pandas-mean
    axis = 'index' (axis=0) means calculate by columns
    axis = 'columns' (axis=1) means calculate by rows

"""

## Import packages for matrices and data frames
import numpy as np
import pandas as pd

# Ignore FutureWarning
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)


## Removing outliers using zscores
# https://stackoverflow.com/questions/69735372/futurewarning-automatic-reindexing-on-dataframe-vs-series-comparisons-is-deprec

numerical_cols=df.select_dtypes(['int64','float64'])
for col in numerical_cols:
    feature_value_less_than_3sigma = df[col].mean()-3*(df[col].std())
    feature_value_greater_than_3sigma = df[col].mean()+3*(df[col].std())
    df = df[~((df[col].lt(feature_value_less_than_3sigma)) | (df[col].gt(feature_value_greater_than_3sigma)))]
    df = df[~((df[col] < (feature_value_less_than_3sigma)) | (df[col] > (feature_value_greater_than_3sigma)))]
else:
    print('\nAfter: ', df.shape)


# Create an array (vector) of numbers
np.arange(11, 17, 0.5)

# Create a list of numbers
np.arange(11, 17, 0.5).tolist()

# https://pynative.com/python-range-function/
range(11, 17)

# Create a 15x4 data frame of random integers
df = pd.DataFrame(np.random.randint(0, 10, size=(15, 4)), columns=list('ABCD'))

# Perform an ifelse loop
np.where(df['A'] > df['B'], df['A'], df['B'])

# Select two rows in first column
df.iloc[2:4, 0]
# Or
df.iloc[2:4, 0:1]

# Set two rows in first column to nan
df.iloc[2:4, 0] = np.nan

# Perform an locf loop forward
df.fillna(method='ffill')
# Perform an locf loop backward
df.fillna(method='bfill')


## Allocate data frame, ifelse, and locf on the data
# Use numpy arrays instead of pandas?
# https://stackoverflow.com/questions/41190852/most-efficient-way-to-forward-fill-nan-values-in-numpy-array


# Allocate a data frame with two columns filled with nan values
df = pd.DataFrame(np.nan, index=range(11, 17), columns=['A', 'B'])
# Set one cell to zero
df.iloc[3, 1] = 0


## Load data frame from csv file

# Load student scores data from csv file
scores = pd.read_csv('/Users/jerzy/Develop/lecture_slides/data/student_scores.csv')

# Get data frame info
scores.info()
# Set default: Display all the columns in output
pd.set_option('display.max_columns', None)
scores

# Get column types
type(scores)
scores.dtypes

# Get dimensions
scores.shape
# Get number of rows
len(scores)

# Select element in third row and fifth column
scores.iloc[2, 4]

# Select whole rows by number range
scores.iloc[2:4, :]

# Print column names
scores.columns

# Select single column by name
scores['HW1_score']
scores.HW1_score
# Select multiple columns by name
scores[['HW1_score', 'HW2_score', 'HW3_score']]
# Select columns by number range
scores.iloc[:, 2:4]
# Select columns by numbers
scores.iloc[:, [1, 3, 4]]

# Select rows except one of them
scores.drop(5, axis=0)
# Select columns except one of them
scores.drop('HW1_score', axis=1)

# Get unique values in column
scores["finance_track"].unique()
# Get number of unique values in column
scores['finance_track'].nunique()
# Get number of rows for each unique value
scores["finance_track"].value_counts()

# Calculate column means
scores.mean()
# Doesn't work for columns with some non-numeric values
scores['HW1_score'].mean()

# Get number of NaN values in each column
scores.isna().sum()
scores.isnull().sum()

# Get percentage of NaN values in each column
100*scores.isnull().sum()/len(scores)

# Remove all rows containing NA values
scores.dropna()
# Remove all columns containing NA values
scores.dropna(axis=1)
# Remove columns with less than 5 NaN values
scores.dropna(axis=1, thresh=5)

# Replace all NA values with -9999
scores.fillna(-9999)
# Replace NA values in specific column
scores['HW1_score'].fillna(-9999)
# Replace specific cell value
scores.at[1, 'HW1_score'] = 9999
# Fill NA values with NaN
scores.fillna(np.NaN)
# Fill NA values with strings
scores.fillna('data missing')
# Fill missing values with mean column values
# Doesn't work if there are some non-numeric values in a column
scores.fillna(scores.mean())

# Coerce column to numeric and replace non-numeric with NA
# Works only for single column
# pd.to_numeric(scores[['test1_score', 'test2_score']], errors='coerce')
scorest = pd.to_numeric(scores['test1_score'], errors='coerce')
# Replace NA values with mean column value
scorest.fillna(scorest.mean())
# Replace NA values of specific columns with mean value
# Doesn't work because there are some non-numeric values in the column
scores['HW1_score'].fillna(scores['HW1_score'].mean())
# Get names of columns except the first two
cols = scores.columns[2:]
# Coerce selected columns to numeric and replace non-numeric with NA
scores[cols] = scores[cols].apply(pd.to_numeric, errors='coerce')
# Fill NA values with column means
scores = scores.fillna(scores.mean(axis=0))
# Replace NA values with row means
# https://stackoverflow.com/questions/33058590/pandas-dataframe-replacing-nan-with-row-average
scores = scores.T.fillna(scores.mean(axis=1)).T
# Or using lambda function
scores[cols] = scores[cols].apply(lambda row: row.fillna(row.mean()), axis=1)
# Interpolate single column
scores['HW1_score'].interpolate()
# Replace NA values with interpolation of columns
scores.interpolate()
# Replace NA values with interpolation of rows
scores[cols].interpolate(axis=1)

# Add new column calculated from existing columns
scores.loc[:, 'test1_sum'] = scores['test1_score'] + scores['test2_score']
# Rename the last column
cols = scores.columns.values
cols[-1, ] = "tests_sum"
scores.columns = cols

# Continue with replace()
# https://towardsdatascience.com/a-checklist-for-data-wrangling-8f106c093fef

# Add LOCF - pandas ffill()
# https://stackoverflow.com/questions/47024931/how-to-fill-missing-dates-in-pandas-dataframe
# https://stackoverflow.com/questions/27905295/how-to-replace-nans-by-preceding-values-in-pandas-dataframe

# Add code for writing to csv file


# To delete an object in Python, we use the ‘del’ keyword
del scores


## Load OHLC data from csv file

from utils import read_csv

# Load OHLC data from csv file - the time index is formatted inside read_csv()
ohlc = read_csv('/Users/jerzy/Develop/data/BTC_minute.csv')

# Load OHLC data from csv file and format the time index
# ohlc = pd.read_csv('/Users/jerzy/Develop/data/SPY_day.csv', parse_dates=True, date_parser=pd.to_datetime, index_col='Date')
# ohlc = pd.read_csv('/Volumes/external/Develop/data/SP500_2020/GOOGL.csv', parse_dates=True, date_parser=pd.to_datetime, index_col='index')

# Get data frame info
ohlc.info()
# Get column types
type(ohlc)
ohlc.dtypes

# Get dimensions
ohlc.shape

# Print column names
ohlc.columns
# Rename columns
ohlc.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
ohlc.head()
ohlc.tail()

# Pandas set default: Display all the columns in the output
# pd.set_option('display.max_columns', None)

# Extract time index
datev = ohlc.index

# Subset data frame
ohlc.iloc[0:5, :]

# Select Close prices
closep = ohlc['Close']
# Or
# closep = ohlc.iloc[:, 3]
type(closep)

# Difference the Seconds column
diffsec = ohlc.Seconds.diff()


### Plot OHLC

## Plotly dynamic interactive time series plots using plotly.graph_objects

import plotly.graph_objects as go

# Select time slice of data
ohlcsub = ohlc['2019':'2020']

# Create plotly line graph object from data frame
plotfig = go.Figure([go.Scatter(x=ohlc.index, y=ohlc.Close)])
plotdata = plotfig.update_layout(title=symbol, yaxis_title='Log Price', xaxis_rangeslider_visible=False, 
            title_font_size=12)
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename='stock_prices.html', auto_open=True)
plotfig.show()


## Plotly simple candlestick with moving average

plotfig = go.Figure(data=[go.Candlestick(x=ohlc.index,
                open=ohlc.Open, high=ohlc.High, low=ohlc.Low, close=ohlc.Close, 
                name=symbol+' Log OHLC Prices', showlegend=False)])
plotdata = plotfig.update_layout(title=symbol+' Log OHLC Prices', 
                                title_font_size=24, title_font_color="blue", 
                                yaxis_title='Prices', font_color="black", font_size=18,
                                xaxis_rangeslider_visible=False)
# Calculate moving average stock prices
closep = ohlc['Close']
lookback = 55
pricema = closep.ewm(span=lookback).mean()
# Add moving average
plotdata = plotfig.add_trace(go.Scatter(x=ohlc.index, y=pricema[ohlc.index], 
                            name="Moving Average", line=dict(color="blue")))
# Customize legend
plotdata = plotfig.update_layout(legend=dict(x=0.2, y=0.9, traceorder="normal",
                      font=dict(family="sans-serif", size=18, color="blue")))
# Plot interactive plot in browser and save to html file
# plot(plotfig, filename='stock_candlesticks.html', auto_open=True)
plotfig.show()



