##################
# This script reads OHLC panel data from the file polygon_aggr, 
# then calculates rolling averages and EWMA by symbol, 
# and writes the data to csv files.
# This script runs every minute 24x7

## Load packages

import pandas as pd
import time
import datetime
from datetime import date, datetime, timedelta

## Get time stamps

# Get current time in seconds since epoch
starttime = time.time()
to_day = date.today()
mtoday = str(to_day)
mdate = mtoday.replace("-", "")


##################
## Load the OHLC panel data from csv file into a data frame.

# filename = mdate + "_polygon_aggr.csv"
mdate = '20220126'
filename = "/Volumes/external/Develop/data/polygon/" + mdate + "_polygon_aggr.csv"
dfx = pd.read_csv(filename)
# Or use package datatable
# import datatable as dt
# dfx = dt.fread(filename)
# dfx = dfx.to_pandas()

# Add column names to data frame
dfx.columns = ['symbol', 'volume', 'avg_vol', 'open_price', 'open', 'high', 'low', 'localtime', 'close', 'average', 'volume', 'starttime', 'endtime']
# Set default: Display all the columns in output
# pd.set_option('display.max_columns', None)

# Drop duplicate columns
# dfx = dfx.loc[:, ~dfx.columns.duplicated()]


##################
## Set aggregation parameters.

win_dow = 60


##################
## Perform loop over the symbols.

# Get unique symbol values from the first column
symbols = dfx["symbol"].unique()

for symbol in symbols:
  
	print("Processing the symbol " + symbol)

	# options = [symbol]
	# Subset rows with symbol
	df = dfx[dfx['symbol'].isin([symbol])] 
#	df = subset(dfx, symbol=='LTC-USD')
#	print(df)

	# Sort rows by start time
	df = df.sort_values("starttime")

  # Add column with true price
	df['tp'] = (df['high'] + df['low'] + df['close'])/3 
	
	# Add column for the price change (dollar returns)
	df['change1'] = df.close.diff(periods=1)
	# Add column for the percentage returns
	df['pct1'] = (df['change1']/df['close'])*100 
	
  # Calculate simple rolling averages and EWMA
	avg = df['close'].rolling(win_dow).mean()
	xavg = df.close.ewm(com=win_dow).mean()
	avgtp = df['tp'].rolling(win_dow).mean()
  # Calculate rolling standard deviation of returns
	std = df.change1.rolling(win_dow).std()

	df['avg'] = avg
	df['std'] = std
	df['xavg'] = xavg
	df['avgtp'] = avgtp

	# Calculate bollinger bands
	df['bbul'] = (df['avgtp'] + df['std'])
	df['bbll'] = (df['avgtp'] - df['std'])
	
	# Aren't these just equal to df['std'] ?
	df['ul'] = (df['bbul'] - df['avgtp']) 
	df['ll'] = (df['avgtp'] - df['bbll'])
	
	df['diff1'] = df['xavg'] - df['avgtp']
	df['pct1'] = df['diff1']/df['avgtp']
	
	df['pctul'] = (df['ul']/df['avgtp'])
	df['pctll'] = (df['ll']/df['avgtp'])
	
	# Subset the columns
	df1 = df[['starttime', 'close', 'change1', 'volume', 'pct1', 'diff1', 'xavg', 'avg', 'open', 'high', 'low']] 
	# print(df)

	# Write to csv files
	outfile = symbol + "_allstats.csv"
	df.to_csv(outfile, encoding='utf-8', index=False, header=True)

	df4 = df1.tail(3600)
	# print(df4)
	outfile = symbol + "_last4hrs.csv"
	# print(outfile)	
	df4.to_csv(outfile, encoding='utf-8', index=False, header=False)
	
	df3 = df1.tail(1)
	# print(df3)
	outfile = symbol + "_lastrow.csv"
	# print(outfile)	
	df3.to_csv(outfile, encoding='utf-8', index=False, header=False)

## End Loop over symbols

# Calculate the elapsed time .

lapsedtime = (time.time() - starttime)
	
print("Time to load data: ", lapsedtime)

