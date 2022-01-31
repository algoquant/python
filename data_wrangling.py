# -*- coding: utf-8 -*-
"""
Script for Python data wrangling
https://towardsdatascience.com/a-checklist-for-data-wrangling-8f106c093fef
https://stackoverflow.com/questions/36814100/pandas-to-numeric-for-multiple-columns
https://stackoverflow.com/questions/44117326/how-can-i-remove-all-non-numeric-characters-from-all-the-values-in-a-particular

Note about 'axis' parameter in pandas:
https://stackoverflow.com/questions/22149584/what-does-axis-in-pandas-mean
    axis = 'index' (axis=0) means calculate by columns
    axis = 'columns' (axis=1) means calculate by rows

"""

## Import package for OS commands
import os

# Show current working directory
os.getcwd()
# List files in the directory
os.listdir()
# Change working directory
os.chdir("/Users/jerzy/Develop/python/scripts")
os.listdir()


## Load data from csv files

# Import packages for matrices and data frames
import numpy as np
import pandas as pd

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

# Select column by name
scores['HW1_score']
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
scores.at[1, 'HW1_score']= 9999
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
col_umn = pd.to_numeric(scores['test1_score'], errors='coerce')
# Replace NA values with mean column value
col_umn.fillna(col_umn.mean())
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




## Load OHLC data from csv file

# Load OHLC data from csv file and format the time index
se_ries = pd.read_csv('/Volumes/external/Develop/data/SP500_2020/GOOGL.csv', parse_dates=True, date_parser=pd.to_datetime, index_col='index')

# Get data frame info
se_ries.info()
# Get column types
type(se_ries)
se_ries.dtypes

# Get dimensions
se_ries.shape

# Print column names
se_ries.columns
# Rename columns
se_ries.columns = ['Open', 'High', 'Low', 'Close', 'Volume']
se_ries.head()
se_ries.tail()

# Extract time index
in_dex = se_ries.index

# Subset data frame
se_ries.iloc[0:5, :]

# Select Close prices
clos_e = se_ries['Close']
# Or
# clos_e = se_ries.iloc[:, 3]
type(clos_e)


