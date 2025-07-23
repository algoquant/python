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
print("Local time:", localtime, day)

# But the Worst Performers today

from settings import login4p, acct_name4p, keya4p, keyb4p

login = login4p
acct_name = acct_name4p
key1 = keya4p
key2 = keyb4p
endpoint = "https://paper-api.alpaca.markets"

# -------------------------------------------------------


print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

#quit()

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

api = tradeapi.REST()

starttime = time.time()


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


ux = timestamp
uxs = str(ux)

path1 = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
filename = path1+ "/data/one_day_bars_at_9pm_" +ydate+ ".csv"  	


df = pd.read_csv(filename)
df.columns =['ticker','unixtime','volume','vway','open_s','close_s', 'high', 'low'] 

df['change'] = df['close_s'] - df['open_s']  
df['pct_change'] = df['change'] / df['open_s'] * 100

df = df.sort_values(by='pct_change', ascending=False)
#print(df.head)


df_top = df.head(30)


#limit to tickers with share volume > 100,000
df_top = df_top[df_top["volume"] > 100000]
cnt = df_top.shape[0]
z = int(cnt)

print(df_top)
print("Count: ",z)

df_bottom = df.tail(10)
#print(df_bottom)

#quit()

x = 0
for x in range(x,z):


	xs = str(x)

	ticker = df_top.iloc[x, 0]
	t = ticker
	ts = str(t)
	ts = ts.upper()
#	ts = ts.lower()
#	print(ts, qty)
	tss = str(ts)
	print(tss)

	# Check if ticker tradable on the Alpaca platform.
	asset = api.get_asset(ts)
	short = 0
	
	if asset.tradable:
	    print('\nWe can trade ',ts)
	    long = str(1)
	
	if asset.shortable:
		short = '1'	
	
	if short == 0:
		print(ts," cannot be shorted today")

	else:
		print(ts, " can be shorted today")
	
		print("make the trade with Alpaca")

		ux = timestamp
		uxs = str(ux)
		
		getstring = "https://api.polygon.io/v1/last/stocks/" +tss+ "?&apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
		print(getstring)
		
		resp = requests.get(getstring)
		print(resp)
		
		r=resp.json()
		#print(r)
		
		ux = timestamp
		uxs = str(ux)
	
	
		try: 
			last = r['last']
			for item in last:
				price = (last["price"])
			p = str(price)
			qty = int((20000 / price) )
			qty = int(qty)
			qtys = str(qty)
			print("Ticker: ",ts,"Price: ",p, "Qty: ",qty)
		except:
			pass


		clientid = "SHORT_" +tss+ "_" +uxs
		clientid = str(clientid)
		print(clientid,qty,price)

		
		try:
			api.submit_order(
			symbol=tss,
			qty=qtys,
			side='sell',
			type='limit',
	#		type = 'market',
			limit_price=price,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
		except Exception as e:
			print(+str(e))
			#pass	




	
				
	time.sleep(1)	
	x =+1

exit()

