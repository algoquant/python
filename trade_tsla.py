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

from settings import login13p, acct_name13p, keya13p, keyb13p

login = login13p
acct_name = acct_name13p
key1 = keya13p
key2 = keyb13p
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

# close all open orders

api.cancel_all_orders()

# Get the last 500 of our closed orders
closed_orders = api.list_orders(
    status='open',
    limit=500,
    #/nested=True  # show nested multi-leg orders
)

#print(closed_orders)


ts = 'tsla'
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

# if short = '1', you can short tsla today

print("make the current price of TSLA")

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
	print("Ticker: ",ts,"Price: ",p)
except:
	pass



# close all open orders

api.cancel_all_orders()

# Get the last 500 of our closed orders
closed_orders = api.list_orders(
    status='open',
    limit=500,
    #/nested=True  # show nested multi-leg orders
)

#print(closed_orders)

		
portfolio = api.list_positions()
qty = 0

# Print the quantity of shares for each position.


for Position in portfolio:
	
	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side
	gain = Position.unrealized_intraday_plpc
	gain = float(gain)
	gain = int(gain * 10000) # 35 = 3.5%	
	gains = str(gain)

	gain = float(gain)
	qtys = str(qty)
	symbol = str(symbol)	
	print("the current position is ",symbol,"Current price: ", price,"Qty: ",qty,"Side: ",side, "Pct Gain: ",gain)



if (qty < 0):

	print("Qty < 0. Check to see if trades should be made")

	if (gain < -10):

		print("loss is 1% today. Close current position")		

		if (qty < 0):

			qty = qty * 1 # reverse sign

			ux = int(time.time())
			uxs = str(ux)

			# clientid must be unique 
			clientid = "COVERSHRT_" +tss+ "_" +uxs
			clientid = str(clientid)
			print(clientid,qty,price)
		
			
			try:
				api.submit_order(
				symbol=tss,
				qty='500',
				side='buy',
				type='limit',
		#		type = 'market',
				limit_price=price,
				time_in_force='day',
		#		extended_hours=True,
				client_order_id=clientid)
			except Exception as e:
				#print(+str(e))
				pass	
				
	if (gain > 30):

		print("gain is 3% today. Close current position")		

		if (qty < 0):

			qty = qty * 1 # reverse sign

			ux = int(time.time())
			uxs = str(ux)

			# clientid must be unique 
			clientid = "COVERSHRT_" +tss+ "_" +uxs
			clientid = str(clientid)
			print(clientid,qty,price)
		
			
			try:
				api.submit_order(
				symbol=tss,
				qty='500',
				side='buy',
				type='limit',
		#		type = 'market',
				limit_price=price,
				time_in_force='day',
		#		extended_hours=True,
				client_order_id=clientid)
			except Exception as e:
				#print(+str(e))
				pass	
				
elif (qty < 0):

	print("Qty < 0. Check to see if trades should be made")

	if (gain < -10):

		print("loss is 1% today. Close current position")		

		if (qty < 0):

			qty = qty * 1 # reverse sign

			ux = int(time.time())
			uxs = str(ux)

			# clientid must be unique 
			clientid = "COVERSHRT_" +tss+ "_" +uxs
			clientid = str(clientid)
			print(clientid,qty,price)
		
			
			try:
				api.submit_order(
				symbol=tss,
				qty='500',
				side='buy',
				type='limit',
		#		type = 'market',
				limit_price=price,
				time_in_force='day',
		#		extended_hours=True,
				client_order_id=clientid)
			except Exception as e:
				#print(+str(e))
				pass	
				
	if (gain > 30):

		print("gain is 3% today. Close current position")		

		if (qty < 0):

			qty = qty * 1 # reverse sign

			ux = int(time.time())
			uxs = str(ux)

			# clientid must be unique 
			clientid = "COVERSHRT_" +tss+ "_" +uxs
			clientid = str(clientid)
			print(clientid,qty,price)
		
			
			try:
				api.submit_order(
				symbol=tss,
				qty='500',
				side='buy',
				type='limit',
		#		type = 'market',
				limit_price=price,
				time_in_force='day',
		#		extended_hours=True,
				client_order_id=clientid)
			except Exception as e:
				#print(+str(e))
				pass	

else:

	print("TSLA position is now zero. Short 500 shares")
	ux = int(time.time())
	uxs = str(ux)

	# clientid must be unique 
	clientid = "SHORT_" +tss+ "_" +uxs
	clientid = str(clientid)
	print(clientid,price)

	try:
		api.submit_order(
		symbol=tss,
		qty='500',
		side='sell',
		type='limit',
#		type = 'market',
		limit_price=price,
		time_in_force='day',
#		extended_hours=True,
		client_order_id=clientid)
	except Exception as e:
		print(+str(e))
		pass	
	
		
quit()
