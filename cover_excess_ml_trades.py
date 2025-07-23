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


polygon_key = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"


timestamp = int(time.time())
localtime = time.ctime(timestamp)
uxs = str(timestamp)

# ----------------------------------------------------------------------------

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

import alpaca_trade_api as tradeapi

api = tradeapi.REST()

symbol = 'SPY'
ticker = symbol

portfolio = api.list_positions()


# Print the quantity of shares for each position.
for Position in portfolio:

	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side

	print("the current position is: ",symbol,price,"Qty: ",qty,"Side: ",side)
	quit()
			
	if (qty < -1000):

		clientid = "COVERSHORT" + uxs			
		print("too many shorts, so liquidate position")	
		print(symbol,qty)


		qty = (qty * -1)
		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='buy',
			type='market',
	#		type='limit',
	#		limit_price=price,
			time_in_force='day',
	#		extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print("see line 588:"+str(e))
			pass


	if (qty > 1000):


		clientid = "COVERLONG" + uxs			
		print("too many longs, so liquidate position")	
		print(symbol,qty)

		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='sell',
			type='market',
	#		type='limit',
	#		limit_price=price,
			time_in_force='day',
	#		extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print("see line 588:"+str(e))
			pass


# ----------------------------------------------------------------------------

from settings import loginf2p, acct_namef2p, keyaf2p, keybf2p

login = loginf2p
acct_name = acct_namef2p
key1 = keyaf2p
key2 = keybf2p
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

import alpaca_trade_api as tradeapi

api = tradeapi.REST()

symbol = 'QQQ'
ticker = symbol

portfolio = api.list_positions()


# Print the quantity of shares for each position.
for Position in portfolio:

	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side

	print("the current position is: ",symbol,price,"Qty: ",qty,"Side: ",side)
			
	if (qty < -1000):

		clientid = "COVERSHORT" + uxs			
		print("too many shorts, so liquidate position")	
		print(symbol,qty)


		qty = (qty * -1)
		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='buy',
			type='market',
	#		type='limit',
	#		limit_price=price,
			time_in_force='day',
	#		extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print("see line 588:"+str(e))
			pass


	if (qty > 1000):


		clientid = "COVERLONG" + uxs			
		print("too many longs, so liquidate position")	
		print(symbol,qty)

		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='sell',
			type='market',
	#		type='limit',
	#		limit_price=price,
			time_in_force='day',
	#		extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print("see line 588:"+str(e))
			pass


# ----------------------------------------------------------------------------

from settings import login1p, acct_name1p, keya1p, keyb1p

login = login1p
acct_name = acct_name1p
key1 = keya1p
key2 = keyb1p
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

import alpaca_trade_api as tradeapi

api = tradeapi.REST()

symbol = 'AAPL'
ticker = symbol

portfolio = api.list_positions()


# Print the quantity of shares for each position.
for Position in portfolio:

	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side

	print("the current position is: ",symbol,price,"Qty: ",qty,"Side: ",side)
			
	if (qty < -3000):

		clientid = "COVERSHORT" + uxs			
		print("too many shorts, so liquidate position")	
		print(symbol,qty)


		qty = (qty * -1)
		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='buy',
			type='market',
	#		type='limit',
	#		limit_price=price,
			time_in_force='day',
	#		extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print("see line 588:"+str(e))
			pass


	if (qty > 3000):


		clientid = "COVERLONG" + uxs			
		print("too many longs, so liquidate position")	
		print(symbol,qty)

		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='sell',
			type='market',
	#		type='limit',
	#		limit_price=price,
			time_in_force='day',
	#		extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print("see line 588:"+str(e))
			pass


# ----------------------------------------------------------------------------

from settings import login2p, acct_name2p, keya2p, keyb2p

login = login2p
acct_name = acct_name2p
key1 = keya2p
key2 = keyb2p
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

import alpaca_trade_api as tradeapi

api = tradeapi.REST()

symbol = 'VXX'
ticker = symbol

portfolio = api.list_positions()


# Print the quantity of shares for each position.
for Position in portfolio:

	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side

	print("the current position is: ",symbol,price,"Qty: ",qty,"Side: ",side)
			
	if (qty < -10000):

		clientid = "COVERSHORT" + uxs			
		print("too many shorts, so liquidate position")	
		print(symbol,qty)


		qty = (qty * -1)
		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='buy',
			type='market',
	#		type='limit',
	#		limit_price=price,
			time_in_force='day',
	#		extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print("see line 588:"+str(e))
			pass


	if (qty > 10000):


		clientid = "COVERLONG" + uxs			
		print("too many longs, so liquidate position")	
		print(symbol,qty)

		try:
			api.submit_order(
			symbol=symbol,
			qty=qty,
			side='sell',
			type='market',
	#		type='limit',
	#		limit_price=price,
			time_in_force='day',
	#		extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print("see line 588:"+str(e))
			pass


