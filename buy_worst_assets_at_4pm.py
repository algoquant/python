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
print("Local time:", localtime)

# But the Worst Performers today

from settings import login3p, acct_name3p, keya3p, keyb3p

login = login3p
acct_name = acct_name3p
key1 = keya3p
key2 = keyb3p
endpoint = "https://paper-api.alpaca.markets"

# -------------------------------------------------------


print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

api = tradeapi.REST()

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
uxs = str(ux)

path1 = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
filename = path1+ "/one_day_bars_at_4pm_" +mdate+ ".csv"  	

df = pd.read_csv(filename)
df.columns =['ticker','unixtime','volume','vway','open_s','close_s', 'high', 'low'] 

df['change'] = df['close_s'] - df['open_s']  
df['pct_change'] = df['change'] / df['open_s'] * 100

df = df.sort_values(by='pct_change', ascending=False)
#print(df.head)

df_top = df.head(10)
print(df_top)

df_bottom = df.tail(10)
print(df_bottom)


x = 0
for x in range(x,10):


	xs = str(x)

	ticker = df_bottom.iloc[x, 0]
	t = ticker
	ts = str(t)
	ts = ts.upper()
#	ts = ts.lower()
#	print(ts, qty)
	tss = str(ts)
	print(tss)


	
	getstring = "https://api.polygon.io/v1/last/stocks/" +tss+ "?&apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
	print(getstring)
	
	resp = requests.get(getstring)
	print(resp)
	
	r=resp.json()
	#print(r)
	

	try: 

		last = r['last']
		
		for item in last:
	
			price = (last["price"])
			

		p = str(price)
	
		qty = int((40000 / price) )
		qtys = str(qty)
	
		print("Ticker: ",ts,"Price: ",p, "Qty: ",qty)

	except:
		pass
			

	portfolio = api.list_positions()
	#print(portfolio)
	
	# make the trade with Alpaca

	clientid = "BUY_" +tss+ "_" +uxs			
	clientid = str(clientid)
	
	print(ts,clientid,qty,price)

	try:
		api.submit_order(
		symbol=tss,
		qty=qtys,
		side='buy',
		type='limit',
#		type = 'market',
		limit_price=price,
		time_in_force='day',
		extended_hours=True,
		client_order_id=clientid)
	except:
		pass	
	
	x =+1

exit()

