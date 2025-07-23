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

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)

starttime = time.time()


today = date.today()
print(today)

yesterday = str(today - timedelta(days = 1))
myesterday = str(yesterday)
ydate = myesterday.replace("-","")

mtoday = str(today)
mdate = mtoday.replace("-","")
print(mdate)


ux = timestamp


path1 = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
file = path1 + "/tickers.csv"  # target portfolio # negative beta

df = pd.read_csv(file)

#df.columns =['ticker','exDate','pmtDate','rptDate','amount'] 

index = df.index
number_of_rows = len(index) # find length of index
print(number_of_rows)
cnt = number_of_rows
print("Count: ",cnt)

#print(df.head)

filename = path1+ "/data/one_day_bars_at_4pm_" +mdate+ ".csv"  	
print("create file:", filename)	
f = open(str(filename), "w")

#cnt = 10

x = 0
for x in range(x,cnt):


	xs = str(x)

	ticker = df.iloc[x, 0]
	t = ticker
	ts = str(t)
	ts = ts.upper()
#	ts = ts.lower()
#	print(ts, qty)
	tss = str(ts)
	print(tss)


	ux1 = ux
	ux2 = ux
	
	print(ux)
	
	dt1 = datetime.utcfromtimestamp(ux1).strftime('%Y-%m-%d')
	dt2 = datetime.utcfromtimestamp(ux2).strftime('%Y-%m-%d')
	dt1 = today
	dt2 = today
	
	getstring=f'https://api.polygon.io/v2/aggs/ticker/{tss}/range/1/day/{dt1}/{dt2}?sort=desc&apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u'
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

	except KeyError:
		pass
	except NameError:
		pass
	except: 
		PrintException()
		pass						
	#print("ticker:",ticker, queryCount,resultsCount,adjusted)

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

	except: 
		pass		

	out = t+ ", " +unixtime+ ", "  +volume+ "," +vwap+ "," +open_s+ "," +close_s+ "," +high+  "," +low+ "\n"
	f = open(filename, "a")
	print(out)
	f.write(out)

	

	x =+1

f.close()	
quit()


