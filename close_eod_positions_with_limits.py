import os
import sys
from datetime import date, datetime, timedelta
import time
import pandas as pd
import numpy as np
import pathlib
import requests
import alpaca_trade_api as tradeapi

# print(pd.__version__)
# exit()
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 100)


today = date.today()
yesterday = today - timedelta(days = 1)
today = str(today)
mdate = today.replace("-","")



timestamp = int(time.time())
localtime = time.ctime(timestamp)
ux = timestamp
uxs = str(ux)



# ----------------- get current price from Polygon

symbol = 'SPY'
ticker = symbol
polygon_key = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"



a = "https://api.polygon.io/v1/last/stocks/"
b = "/"
c = "?apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
url = a + symbol + b + c
url = str(url)
print(url)
getstring = url
print(getstring)
resp = requests.get(getstring)

#print(resp)
if resp.status_code != 200:
	print("This means something went wrong")
	raise ApiError('GET /historical/ {}'.format(resp.status_code))
r=resp.json()

#print(r)
print("Symbol: ",symbol)
last = r['last']

for item in last:
	p = (last["price"])

	price = str(p)

print("Price: ",price)


# ---------------------------------------------------------


print("ML prediction is positive. Make Long Trades")

from settings import loginf1p, acct_namef1p, keyaf1p, keybf1p

login = loginf1p
acct_name = acct_namef1p
key1 = keyaf1p
key2 = keybf1p
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

# ------------------------------------------------------------------

# close all open orders

api.cancel_all_orders()

# Get the last 100 of our closed orders
closed_orders = api.list_orders(
    status='open',
    limit=500,
    #/nested=True  # show nested multi-leg orders
)

#print(closed_orders)


portfolio = api.list_positions()


# Print the quantity of shares for each position.
for Position in portfolio:

	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side

	print("the current position is: ",symbol,price,"Qty: ",qty,"Side: ",side)
			
	if (qty < -0):

		clientid = "COVERSHORT" + uxs			
		print("too many shorts, so liquidate position")	
		print("fp1",clientid,symbol,qty,price)


		qty = (qty * -1)
		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='buy',
	#		type='market',
			type='limit',
			limit_price=price,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print(+str(e))
			#pass


	if (qty > 0):


		clientid = "COVERLONG" + uxs			
		print("too many longs, so liquidate position")	
		print("fp1",clientid,symbol,qty,price)

		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
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


# ---------------------------------------------------------













# close eod open positions for f2 PAPER

# ----------------- get current price from Polygon

symbol = 'QQQ'
ticker = symbol
polygon_key = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"



a = "https://api.polygon.io/v1/last/stocks/"
b = "/"
c = "?apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
url = a + symbol + b + c
url = str(url)
print(url)
getstring = url
print(getstring)
resp = requests.get(getstring)

#print(resp)
if resp.status_code != 200:
	print("This means something went wrong")
	raise ApiError('GET /historical/ {}'.format(resp.status_code))
r=resp.json()

#print(r)
print("Symbol: ",symbol)
last = r['last']

for item in last:
	p = (last["price"])

	price = str(p)

print("Price: ",price)


# ---------------------------------------------------------



print("ML prediction is positive. Make Long Trades")	

from settings import loginf2p, acct_namef2p, keyaf2p, keybf2p

login = loginf2p
acct_name = acct_namef2p
key1 = keyaf2p
key2 = keybf2p
endpoint = "https://paper-api.alpaca.markets"

print("\n",login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2


api = tradeapi.REST()

portfolio = api.list_positions()


# ------------------------------------------------------------------

# close all open orders

api.cancel_all_orders()

# Get the last 100 of our closed orders
closed_orders = api.list_orders(
    status='open',
    limit=500,
    #/nested=True  # show nested multi-leg orders
)

#print(closed_orders)

# Print the quantity of shares for each position.
for Position in portfolio:

	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side

	print("the current position is: ",symbol,price,"Qty: ",qty,"Side: ",side)
			
	if (qty < -0):

		clientid = "COVERSHORT" + uxs			
		print("too many shorts, so liquidate position")	
		print("fp2",clientid,symbol,qty,price)


		qty = (qty * -1)
		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='buy',
	#		type='market',
			type='limit',
			limit_price=price,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print(+str(e))
			#pass


	if (qty > 0):


		clientid = "COVERLONG" + uxs			
		print("too many longs, so liquidate position")	
		print("fp2",clientid,symbol,qty,price)

		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='sell',
			type='limit',
			limit_price=price,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			#print(+str(e))
			pass









# ----------------- get current price from Polygon

symbol = 'AAPL'
ticker = symbol
polygon_key = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"



a = "https://api.polygon.io/v1/last/stocks/"
b = "/"
c = "?apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
url = a + symbol + b + c
url = str(url)
print(url)
getstring = url
print(getstring)
resp = requests.get(getstring)

#print(resp)
if resp.status_code != 200:
	print("This means something went wrong")
	raise ApiError('GET /historical/ {}'.format(resp.status_code))
r=resp.json()

#print(r)
print("Symbol: ",symbol)
last = r['last']

for item in last:
	p = (last["price"])

	price = str(p)

print("Price: ",price)


# ---------------------------------------------------------



print("ML prediction is positive. Make Long Trades")	

from settings import login1p, acct_name1p, keya1p, keyb1p

login = login1p
acct_name = acct_name1p
key1 = keya1p
key2 = keyb1p
endpoint = "https://paper-api.alpaca.markets"

print("\n",login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2


api = tradeapi.REST()

# ------------------------------------------------------------------

# close all open orders

api.cancel_all_orders()

# Get the last 100 of our closed orders
closed_orders = api.list_orders(
    status='open',
    limit=500,
    #/nested=True  # show nested multi-leg orders
)

#print(closed_orders)

portfolio = api.list_positions()


# Print the quantity of shares for each position.
for Position in portfolio:

	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side

	print("the current position is: ",symbol,price,"Qty: ",qty,"Side: ",side)
			
	if (qty < -0):

		clientid = "COVERSHORT" + uxs			
		print("too many shorts, so liquidate position")	
		print("fp2",clientid,symbol,qty,price)


		qty = (qty * -1)
		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='buy',
	#		type='market',
			type='limit',
			limit_price=price,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print(+str(e))
			#pass


	if (qty > 0):


		clientid = "COVERLONG" + uxs			
		print("too many longs, so liquidate position")	
		print("fp2",clientid,symbol,qty,price)

		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='sell',
			type='limit',
			limit_price=price,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			#print(+str(e))
			pass











# ----------------- get current price from Polygon

symbol = 'VXX'
ticker = symbol
polygon_key = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"



a = "https://api.polygon.io/v1/last/stocks/"
b = "/"
c = "?apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
url = a + symbol + b + c
url = str(url)
print(url)
getstring = url
print(getstring)
resp = requests.get(getstring)

#print(resp)
if resp.status_code != 200:
	print("This means something went wrong")
	raise ApiError('GET /historical/ {}'.format(resp.status_code))
r=resp.json()

#print(r)
print("Symbol: ",symbol)
last = r['last']

for item in last:
	p = (last["price"])

	price = str(p)

print("Price: ",price)


# ---------------------------------------------------------



print("ML prediction is positive. Make Long Trades")	

from settings import login2p, acct_name2p, keya2p, keyb2p

login = login2p
acct_name = acct_name2p
key1 = keya2p
key2 = keyb2p
endpoint = "https://paper-api.alpaca.markets"

print("\n",login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2


api = tradeapi.REST()

# ------------------------------------------------------------------

# close all open orders

api.cancel_all_orders()

# Get the last 100 of our closed orders
closed_orders = api.list_orders(
    status='open',
    limit=500,
    #/nested=True  # show nested multi-leg orders
)

#print(closed_orders)

portfolio = api.list_positions()


# Print the quantity of shares for each position.
for Position in portfolio:

	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side

	print("the current position is: ",symbol,price,"Qty: ",qty,"Side: ",side)
			
	if (qty < -0):

		clientid = "COVERSHORT" + uxs			
		print("too many shorts, so liquidate position")	
		print("fp2",clientid,symbol,qty,price)


		qty = (qty * -1)
		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='buy',
	#		type='market',
			type='limit',
			limit_price=price,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print(+str(e))
			#pass


	if (qty > 0):


		clientid = "COVERLONG" + uxs			
		print("too many longs, so liquidate position")	
		print("fp2",clientid,symbol,qty,price)

		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='sell',
			type='limit',
			limit_price=price,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			#print(+str(e))
			pass

