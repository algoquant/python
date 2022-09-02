##################
# This script reads in a loop OHLC data from the files: 
# /Volumes/external_drive/one_minute_bars/[ticker]_polygonaggr.csv
# It then calculates rolling averages and EWMA for each symbol, 
# and writes the data to csv files.
# This script runs every minute from 6 AM to 8 PM.

## Load packages

import pandas as pd
import time

# Get current time in seconds since epoch
starttime = time.time()


##################
## Set aggregation parameters.

look_back = 60


##################
## Perform loop over the symbols.

# Set symbols to process
symbols = ["spy", "svxy", "vxx", "qqq", "spxl", "aapl", "tqqq"]

for symbol in symbols:
	
	print("Processing the symbol " + symbol)

	# Load the OHLC data from csv file into a data frame.
	filename = "/Volumes/external_drive/one_minute_bars/" + symbol + "_polygonaggr.csv"
	df = pd.read_csv(filename)
	#print(df)
	
	# Add column names to data frame
	df.columns = ['symbol', 'volume', 'avg_vol', 'open_price', 'open', 'high', 'low', 'localtime', 'close', 'average', 'volume', 'starttime', 'endtime']

	# Sort rows by start time
	df = df.sort_values("starttime")

	# Add column with true price
	df['tp'] = (df['high'] + df['low'] + df['close'])/3 
	
	# Add column for the price change (dollar returns)
	df['change1'] = df.close.diff(periods=1)
	# Add column for the percentage returns
	df['pct1'] = (df['change1']/df['close'])*100 
	
	# Calculate simple rolling averages and EWMA
	avg = df['close'].rolling(look_back).mean()
	xavg = df.close.ewm(com=look_back).mean()
	avgtp = df['tp'].rolling(look_back).mean()
	# Calculate rolling standard deviation of returns
	std = df.change1.rolling(look_back).std()

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
	print(df)
	#exit()
	
	# Write to csv files
	outfile = "/Volumes/external_drive/one_minute_aggs/" + symbol + "_allstats.csv"
	df.to_csv(outfile, encoding='utf-8', index=False, header=True)

	df4 = df1.tail(240)
	# print(df4)
	outfile = "/Volumes/external_drive/one_minute_aggs/" + symbol + "_last4hrs.csv"
	print(outfile)	
	df4.to_csv(outfile, encoding='utf-8', index=False, header=False)
	
	df3 = df1.tail(1)
	# print(df3)
	outfile = "/Volumes/external_drive/one_minute_aggs/" + symbol + "_lastrow.csv"
	# print(outfile)	
	df3.to_csv(outfile, encoding='utf-8', index=False, header=False)

## End Loop over symbols

# Print the elapsed time for running script.

print("Time elapsed to process the data: ", time.time() - starttime)

