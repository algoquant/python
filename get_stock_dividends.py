import requests
import os
from datetime import date, timedelta
from datetime import datetime
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time as timecode
import sys
import inspect


today = '2020-10-03'
yesterday = '2020-10-02'
print("Today: ",today, "Yesterday: ",yesterday)
mdate = today.replace("-","")


# get the list of top mentioned tickers 

path1 = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
dayfile = path1 + "/tickers.csv"  
day1 = pd.read_csv(dayfile)

print(day1.head)

# add column headers
day1.columns =['ticker'] 

filename = path1+ "/data/tickers_with_dividends.csv"
f = open(str(filename), "w")

		
x = 0
for x in range(x,8974): 
#for x in range(x,100): 

	xs = str(x)
	ticker = day1.iloc[x, 0]
	t = ticker
	ts = str(t)
	ts = ts.upper()
#	ts = ts.lower()
	tss = str(ts)
#	tss = 'T'
	print(tss)

	url = "https://api.polygon.io/v2/reference/dividends/" +tss+ "?&apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
	#print(url)

	getstring = url
	#print(getstring)
	resp = requests.get(getstring)
	print(resp)

	if resp.status_code != 200:
		print("This means something went wrong")
		raise ApiError('GET /historical/ {}'.format(resp.status_code))

	r=resp.json()
	#print(r)

	results			= r['results']

	try:
		for item in results:
			#print(item)
	
		
	
			ticker	= item['ticker']
			exDate	= item['exDate']
			pmtDate	= item['paymentDate']
			rcdDate	= item['recordDate']
			amount	= item['amount']
		
			ticker = str(ticker)
			exDate = str(exDate)
			pmtDate = str(pmtDate)
			rcdDate = str(rcdDate)
			amount = str(amount)
	
			out = ticker+ "," +exDate+ "," +pmtDate+ "," +rcdDate+ "," +amount+ "\n"
	
			f = open(str(filename), "a")
			f.write(out)
	except:
		pass	
		

	x =+1
	
		
f.close()