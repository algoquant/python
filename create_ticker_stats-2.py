# This script runs every minute 24x7


import requests
import os
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time
import datetime
from datetime import date
from datetime import datetime
from datetime import timedelta
import mysql.connector
import sys
import inspect
import alpaca_trade_api as tradeapi

timestamp = int(time.time())
localtime = time.ctime(timestamp)
day = localtime[0:3]
hour = localtime[11:13]
min =  localtime[14:16]
hour = int(hour)
min = int(min)

print("Local time:", localtime, day, hour, min)
timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)

starttime = time.time()


#connect to database

import mysql.connector as connection
import pandas as pd

#print(df)
#quit()



today = date.today()
print(today)

if (day == 'Mon'):
	yesterday = str(today - timedelta(days = 3))
	myesterday = str(yesterday)
	ydate = myesterday.replace("-","")

else:
	yesterday = str(today - timedelta(days = 1))
	myesterday = str(yesterday)
	ydate = myesterday.replace("-","")


mtoday = str(today)
mdate = mtoday.replace("-","")
print(mdate, ydate)

# ----------------------------------------------------------------
	
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
		 		

	filename = mdate+ "_polygonaggr.csv"
	print(filename)

	dfx = pd.read_csv (filename)

	# column names
	dfx.columns = ['symbol','volume','avg_vol','open_price','open','high','low','localtime','close','average','volume','starttime','endtime']

	#print(dfx)
	# only use rows where close > 0



	options = [ticker]
	df = dfx[dfx['symbol'].isin(options)] 
#	df = subset(dfx, symbol=='LTC-USD')
#	print(df)

	
	df['tp'] =  (df['high'] +  df['low'] +  df['close']) /3 
	df = df.sort_values("starttime")

	#print(df)
	
	avg = df['close'].rolling(window=60,center=False).mean()
	xavg = df.close.ewm(com=60).mean()
	avgtp = df['tp'].rolling(window=60,center=False).mean()
	std = df.open.std(axis = 0, ddof=1, skipna = True)
			
	# add a column for the price change
	df['change1'] = df.close.diff(periods=1)
	df['pct1'] = (df['change1'] / df['close']) * 100 
	
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
	
	df2 = df1[['starttime','close','change1','volume','pct1', 'diff1','xavg','avg','open','high','low']] 
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


