# Copy of create_ticker_stats-2
# This script runs every minute 24x7

# import requests
# import os
import pandas as pd
# from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time
import datetime
from datetime import date, datetime, timedelta
# import mysql.connector
# import sys
# import inspect
# import alpaca_trade_api as tradeapi

# Get current time in seconds since epoch
starttime = time.time()
timestamp = int(starttime)
localtime = time.ctime(timestamp)
print("Local time:", localtime)
day = localtime[0:3]
hour = localtime[11:13]
minute =  localtime[14:16]
hour = int(hour)
minute = int(minute)
print("Local time:", localtime, day, hour, minute)

# Connect to database
# import mysql.connector as connection
# import pandas as pd
# print(df)
# quit()

to_day = date.today()
print(to_day)

if (day == 'Mon'):
	yesterday = str(to_day - timedelta(days = 3))
	myesterday = str(yesterday)
	ydate = myesterday.replace("-","")
else:
	yesterday = str(to_day - timedelta(days = 1))
	myesterday = str(yesterday)
	ydate = myesterday.replace("-","")

mtoday = str(to_day)
mdate = mtoday.replace("-", "")
print(mdate, ydate)

## Load data from csv file
filename = "/Volumes/external/Develop/data/polygon/" + mdate + "_polygon_aggr.csv"
print(filename)
dfx = pd.read_csv(filename)

# Add column names to data fram
dfx.columns = ['symbol', 'volume', 'avg_vol', 'open_price', 'open', 'high', 'low', 'localtime', 'close', 'average', 'volume', 'starttime', 'endtime']
# dfx.columns = ['symbol', 'open_price', 'open', 'high', 'low', 'localtime', 'close', 'average', 'volume', 'starttime', 'endtime']
# Set default: Display all the columns in output
# pd.set_option('display.max_columns', None)
# print(dfx)
# only use rows where close > 0

# Get unique symbol values in first column
dfx["symbol"].unique()

# ----------------------------------------------------------------

# Loop over tickers
x = 1
for x in range(1,7):

	if (x == 1):
		ticker = 'aapl'
	elif (x == 2):
		ticker = 'qqq'
	elif (x == 3):
		ticker = 'spxl'
	elif (x == 4):
		ticker = 'spy'
	elif (x == 5):
		ticker = 'tqqq'
	elif (x == 6):
		ticker = 'vxx'

# Select rows with the ticker
	options = [ticker]
	df = dfx[dfx['symbol'].isin(options)]
#	df = subset(dfx, symbol=='LTC-USD')
#	print(df)

# Add column with true price
	df['tp'] =  (df['high'] + df['low'] + df['close'])/3 
# Sort rows by starttime
	df = df.sort_values("starttime")

# Calculate simple rolling averages and EWMA
	avg = df.close.rolling(window=60, center=False).mean()
	xavg = df.close.ewm(com=60).mean()
	avgtp = df.tp.rolling(window=60, center=False).mean()
# Calculate standard deviation of open prices (not returns)
	std = df.open.std(axis=0, ddof=1, skipna=True)

	# Add column for the price change
	df['change1'] = df.close.diff(periods=1)
	df['pct1'] = (df['change1']/df['close'])*100 
	
	df1 = df

	df1['avg'] = avg
	df1['std'] = std
	df1['xavg'] = xavg
	df1['avgtp'] = avgtp
	
	
	bbul = (df1['avgtp'] + df1['std'])
	bbll = (df1['avgtp'] - df1['std'])
	
	
	df1['bbul'] = bbul
	df1['bbll'] = bbll
	
	ul = (df1['bbul'] - df1['avgtp'])
	ll = (df1['avgtp'] - df1['bbll'])
	
	
	df1['ul'] = ul 
	df1['ll'] = ll
	
	
	pctul = (df1['ul'] / df1['avgtp'] )
	pctll = (df1['ll'] / df1['avgtp'] )
	
	diff1 = df1['xavg'] - df1['avgtp']
	df1['diff1'] = diff1
	
	pct1 = df1['diff1'] / df1['avgtp']
	df1['pct1'] = pct1
	
	df1['pctul'] = pctul 
	df1['pctll'] = pctll
	
	df2 = df1[['starttime', 'close', 'change1', 'volume', 'pct1', 'diff1', 'xavg', 'avg', 'open', 'high', 'low']] 
	#print(df2)
	
	df3 = df2.tail(1)
	print(df3)

	df4 = df2.tail(3600)
	#print(df4)
	
	#print("if diff1 > 0, sell signal. If diff1 < 0, buy signal")
	
	outfile2 = ticker + "_last4hrs.csv"
	#print(outfile)	
	df4.to_csv(outfile2, encoding='utf-8', index=False, header=False)
	
	outfile = ticker + "_lastrow.csv"
	#print(outfile)	
	df3.to_csv(outfile, encoding='utf-8', index=False, header=False)
	
	outfile1 = ticker+ "_allstats.csv"
	df1.to_csv(outfile1, encoding='utf-8', index=False, header=True)
	
	
	x =+ 1

endtime = time.time()
lapsedtime = (endtime - starttime)
	
print("Time to load data: ",lapsedtime)
	
quit()


