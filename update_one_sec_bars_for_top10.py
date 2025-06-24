import requests
import os
import datetime
from datetime import datetime, timedelta
from datetime import date
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time 
import sys
import telegram_send

import signal
import argparse
import subprocess
import inspect
global polygon_api_key

pd.set_option('max_rows', 200)

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("What is the current time: ", localtime, "Timestamp: ",timestamp)


today = date.today()
#print(today)

yesterday = str(today - timedelta(days = 1))
myesterday = str(yesterday)
ydate = myesterday.replace("-","")

mtoday = str(today)
mdate = mtoday.replace("-","")
#print(mdate)

# turn offf error messages
pd.options.mode.chained_assignment = None

ux = timestamp
uxs = str(ux)

#ydate = '20210309'

path1 = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

file2 = path1 + "/" +mdate+ "_top_aggr.csv"  # one second bars for the day 
all_assets = pd.read_csv(file2)

# add column headers
all_assets.columns =['ticker','volume','unixtime','vwap','open_p','close_p','high','low','volume','ux1','ux2','f1'] 

all_assets['dates'] = pd.to_datetime(all_assets['ux2'], unit='s')
all_assets['est'] = (all_assets['dates'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern').dt.strftime("%Y-%m-%d %H:%M:%S"))

print(all_assets.head)
#print(all_assets['ticker'])


file1 = path1 + "/top100_" +ydate+ ".csv"
topassets = pd.read_csv(file1)

print(topassets.head(10))
toptickers = topassets['ticker']
print(toptickers.head)


x = 1
for x in range(x,11):

	xs = str(x)
	ticker = topassets.iloc[x, 1]
	t = ticker
	ts = str(t)
	ts = ts.lower()
	print(ts)

#	ts = 'can'

	try:
		df1 = all_assets.loc[all_assets['ticker'] == ts]

	
		df1['change1'] = df1.close_p.diff(periods=1)
		df1['pct_change'] = df1['change1'] / df1['close_p']
		df1['HL_spread'] = df1['high'] - df1['low']
		df1['OC_spread'] = df1['open_p'] - df1['close_p']
		df1['pct_highlow'] = df1['HL_spread'] / df1['close_p']
		df1['pct_openclose'] = df1['OC_spread'] / df1['close_p']
	
		median10 = df1.pct_highlow.rolling(window=10).median()
		df1['median_hl'] = median10
		
		openclose = df1.pct_openclose.rolling(window=10).median()
		df1['openclose'] = openclose
		
		df1['change_day'] = df1['change1'].sum()     
		df1['pct_change_day'] = df1['change_day'] / df1['close_p']
	#	df1['max']  = df1.max('close_p')
	#	df1['min']  = df1.min('close_p')
		df1['close_2p'] = df1['close_p']

		print(df1.head)	


		file1 = path1+ "/outfile_" +ts+ ".csv"
		df1.to_csv(file1, header=True, mode='w')
	
	except:
		pass
	
	


	x =+1
	
