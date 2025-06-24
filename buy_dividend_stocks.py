import os
import sys
from datetime import date, datetime, timedelta
import time
import pandas as pd
import numpy as np
import pathlib
import requests
import alpaca_trade_api as tradeapi
import inspect
timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("What is the current time: ", localtime, "Timestamp: ",timestamp)

today = date.today()
yesterday = today - timedelta(days = 1)
today = str(today)
mdate = today.replace("-","")
print(today)


ux = timestamp
uxs = str(ux)


# Dividend stocks

from settings import login5p, acct_name5p, keya5p, keyb5p

login = login5p
acct_name = acct_name5p
key1 = keya5p
key2 = keyb5p
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

		
# Get a list of target portfolio assets 

path1 = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
file = path1 + "/data/tickers_with_dividends.csv"  # target portfolio # negative beta

df = pd.read_csv(file)
df.columns =['ticker','exDate','pmtDate','rptDate','amount'] 
df = df[df["exDate"] == today]


index = df.index
number_of_rows = len(index) # find length of index
print(number_of_rows)
cnt = number_of_rows
print("Count: ",cnt)

print(df.head)
pos = 400000/ cnt
print("target positon:", pos)

#quit()



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
	except:
		pass

	qty = int(pos / price) 
	qtys = str(qty)
	print(tss, price, qtys)	


	# make the trade with Alpaca

	ux = int(time.time())
	uxs = str(ux)
	clientid = "BUY_" +tss+ "_" +uxs			
	clientid = str(clientid)
	
	print(clientid,qtys,p)

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
		pass


	

	
	x =+1




quit()

