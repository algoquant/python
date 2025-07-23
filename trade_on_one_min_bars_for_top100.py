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

ux = timestamp
uxs = str(ux)



#topfile = "top100_" +ydate+ ".csv"
topfile = "top100_20210309.csv"

top100 = pd.read_csv(topfile)
#print(top100)


# iterate through alltop one ticker at a time

# turn offf error messages
pd.options.mode.chained_assignment = None

x = 5
for x in range(x,15):

	xs = str(x)
	ticker = top100.iloc[x, 1]
	t = ticker
	ts = str(t)
	ts = ts.lower()
	print(ts)


	file = "outfile_" +ts+ ".csv"

	print(file)
	df = pd.read_csv(file)
	print(df.head)

	x =+1


quit()

x = 1
for x in range(x,15):

	xs = str(x)

	
	ticker = top100.iloc[x, 1]
	t = ticker
	ts = str(t)
	ts = ts.lower()
#	ts = 'EYES'
	print(ts)

	df1 = alltop.loc[alltop['ticker'] == ts]
	#print(df1.head)	

	file1 = "outfile_" +ts+ ".csv"


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


	df1.to_csv(file1, header=True, mode='a')

	
	x =+1
	



	