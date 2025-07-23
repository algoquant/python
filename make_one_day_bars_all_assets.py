import requests
import os
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time
import datetime
from datetime import date
from datetime import datetime, timedelta
import sys
import telegram_send
import signal
import argparse
import subprocess
import linecache
import inspect

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("What is the current time: ", localtime, "Timestamp: ",timestamp)


today = date.today()
print(today)
yesterday = str(today - timedelta(days = 1))
ydate = yesterday.replace("-","")

path = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))


starttime = time.time()

x = 1
xs = str(x)

file2 = path + "/tickers.csv"
tickers = pd.read_csv(file2)
#print(tickers.head)


x = 0
for x in range(x,10): 

	xs = str(x)
	ticker = tickers.iloc[x, 0]
	t = ticker
	ts = str(t)
	ts = ts.upper()

	print(ts)

	
	filename = path+ "/one_day_bars_" +ydate+ ".csv"  	
	print("create file:", filename)	
	
	try:	
		f = open(str(filename), "a")
	except: 
		PrintException()


	
	getstring=f'https://api.polygon.io/v2/aggs/ticker/{ts}/range/1/day/{yesterday}/{yesterday}?sort=desc&limit=10&apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u'
	print(getstring)

	resp = requests.get(getstring)
	#print(resp)

	r=resp.json()

#	print(r)

	try:	
		results			= r['results']
#		map				= r['map']
		ticker			= r['ticker']
		queryCount 		= r['queryCount']
		resultsCount	= r['resultsCount']
		adjusted		= r['adjusted'] 		

	except:
		pass

#	return results
	import csv 

	try:
		for item in results:
			#print(item)
			vwap = str(item['vw'])
			open_s = str(item['o'])
			close_s = str(item['c'])
			high = str(item['h'])
			low = str(item['l'])
			unixtime = str(item['t'])
			volume = str(item['v'])

			out = t+ ", " +unixtime+ ", "  +volume+ "," +vwap+ "," +open_s+ "," +close_s+ "," +high+  "," +low+ "\n"
			print(out)
			f.write(out)


	except:
		pass

f.close()
