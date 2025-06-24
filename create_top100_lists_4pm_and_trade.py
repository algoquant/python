# requires a one_day_bars_4pm.csv file (line 41)

import requests
import os
from datetime import datetime, timedelta
from datetime import date
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time# as timecode
import sys
import inspect
import alpaca_trade_api as tradeapi


pd.set_option('max_rows', 100)

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)
lt = localtime

print(lt[0:1])


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
dayfile = path1 + "/one_day_bars_4pm.csv"  # target portfolio # negative beta
day1 = pd.read_csv(dayfile)

# add column headers
day1.columns =['ticker','unixtime','volume','vwap','open_p','close_p','high','low'] 
day1['change'] = day1['close_p'] - day1['open_p']

# calculate change from open to close
day1['change'] = day1['close_p'] - day1['open_p']

# calculate pct change 
day1['pct_change'] = day1['change'] / day1['open_p']


# sort by biggest change in price 
day1 = day1.sort_values(by=['pct_change'], ascending=False)
print("\n This is a list of the top 100 stock from the previous trading day \n")
print(day1.head(10))


day2 = day1.sort_values(by=['pct_change'], ascending=True)
print("\n This is a list of the worst  100 stock from the previous trading day \n")
print(day2.head(10))

day1H = day1.head(10)
day2H = day2.head(10)

quit()

file1 = "top100_" +ydate+ ".csv"
file2 = "bottom100_" +ydate+ ".csv"

day1H.to_csv(file1, header=True, mode='w')
day2H.to_csv(file2, header=True, mode='w')


from settings import login4p, acct_name4p, keya4p, keyb4p

login = login4p
acct_name = acct_name4p
key1 = keya4p
key2 = keyb4p
endpoint = "https://paper-api.alpaca.markets"



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

qty = 100
qtys = str(qty)
		
		
# Get a list of target portfolio assets 

x = 0
for x in range(x,10): 

	xs = str(x)
	ticker = day1.iloc[x, 0]
	t = ticker
	ts = str(t)
	ts = ts.upper()
#	ts = ts.lower()
#	print(ts, qty)
	tss = str(ts)

	# to get current price of ticker
	
	polygonkey = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
	
	getstring = f"https://api.polygon.io/v1/last/stocks/{ts}?&apiKey={polygonkey}"
	#print(getstring)
	
	resp = requests.get(getstring)
	#print(resp)
	
	r=resp.json()
	#print(r)
	

	try: 

		last = r['last']
		
		for item in last:
	
			price = (last["price"])
			
			p = str(price)
			print("Ticker: ",ts,"Price: ",p, "Qty: ",qty)
		
			clientid = "BUY_" +tss+ "_" +uxs			
			clientid = str(clientid)
			
			print(ts,clientid,qty,price)
		
			try:
				api.submit_order(
				symbol=tss,
				qty=qtys,
				side='sell',
				type='limit',
				limit_price=p,
				time_in_force='day',
				client_order_id=clientid)
		        
			except Exception as e:
				print(+str(e))
				pass
			
	except Exception as e:
		pass

	
	x =+1

	print("top tickers:t",tss)
	
	x =+1
	
		

from settings import login3p, acct_name3p, keya3p, keyb3p

login = login3p
acct_name = acct_name3p
key1 = keya3p
key2 = keyb3p
endpoint = "https://paper-api.alpaca.markets"



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

qty = 100
qtys = str(qty)
		
# Get a list of target portfolio assets 

x = 0
for x in range(x,10): 

	xs = str(x)
	ticker = day2.iloc[x, 0]
	t = ticker
	ts = str(t)
	ts = ts.upper()
#	ts = ts.lower()
#	print(ts, qty)
	tss = str(ts)

	# to get current price of ticker
	
	polygonkey = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
	
	getstring = f"https://api.polygon.io/v1/last/stocks/{ts}?&apiKey={polygonkey}"
	#print(getstring)
	
	resp = requests.get(getstring)
	#print(resp)
	
	r=resp.json()
	#print(r)
	

	try: 

		last = r['last']
		
		for item in last:
	
			price = (last["price"])
			
			p = str(price)
			print("Ticker: ",ts,"Price: ",p, "Qty: ",qty)
		
			clientid = "BUY_" +tss+ "_" +uxs			
			clientid = str(clientid)
			
			print(ts,clientid,qty,price)
		
			try:
				api.submit_order(
				symbol=tss,
				qty=qtys,
				side='buy',
				type='limit',
				limit_price=p,
				time_in_force='day',
				client_order_id=clientid)
		        
			except Exception as e:
				print(+str(e))
				pass
			
	except Exception as e:
		pass

	
	x =+1

	print("top tickers:t",tss)
	
	x =+1
	
		


