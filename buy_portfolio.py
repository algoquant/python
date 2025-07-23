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

ux = timestamp
uxs = str(ux)

# this creates a portfolio for negative beta, larger cap assets 

# negative_beta

from settings import login8p, acct_name8p, keya8p, keyb8p
#
#login = login8p
#acct_name = acct_name8p
#key1 = keya8p
#key2 = keyb8p
#endpoint = "https://paper-api.alpaca.markets"
#


# small cap

#from settings import login9p, acct_name9p, keya9p, keyb9p
#
#login = login9p
#acct_name = acct_name9p
#key1 = keya9p
#key2 = keyb9p
#endpoint = "https://paper-api.alpaca.markets"


# large cap high beta


#from settings import login7p, acct_name7p, keya7p, keyb7p
#
#login = login7p
#acct_name = acct_name7p
#key1 = keya7p
#key2 = keyb7p
#endpoint = "https://paper-api.alpaca.markets"
#
#

# Value stocks

from settings import login10p, acct_name10p, keya10p, keyb10p

login = login10p
acct_name = acct_name10p
key1 = keya10p
key2 = keyb10p
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
#file = path1 + "/negative_beta.csv"  # target portfolio # negative beta
#file = path1 + "/small_cap.csv"  # target portfolio # negative beta
#file = path1 + "/largecap_highbeta.csv"  # target portfolio # negative beta
file = path1 + "/value_shares.csv"  # target portfolio # negative beta

df = pd.read_csv(file)

index = df.index
number_of_rows = len(index) # find length of index
print(number_of_rows)
cnt = number_of_rows
print("Count: ",cnt)

print(df.head)

x = 0
for x in range(x,cnt):
	xs = str(x)
	
	ticker = df.iloc[x, 0]
	qty = df.iloc[x, 1]
	t = ticker
	ts = str(t)
	ts = ts.upper()
#	ts = ts.lower()
#	print(ts, qty)
	tss = str(ts)
	qtys = str(qty)
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
		

	except:
		pass


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
		limit_price=p,
		time_in_force='day',
		client_order_id=clientid)
        
	except Exception as e:
		print(+str(e))
		pass

	
	x =+1


quit()

