import os
import sys
from datetime import date, datetime, timedelta
import time
import pandas as pd
import numpy as np
import pathlib
import requests
import alpaca_trade_api as tradeapi

# this uses Alapca account dan@flaglerstreettrading.com
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
		
portfolio = api.list_positions()


# Print the quantity of shares for each position.

for Position in portfolio:
	
	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side
		
	print("the current position is ",symbol,"Current price: ", price,"Qty: ",qty,"Side: ",side)

	
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
	#		limit_price=price,
			time_in_force='day', # or 'ioc' immediate or cancel'
	#		extended_hours=True,
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
	#		type='limit',
			type = 'market',
	#		limit_price=price,
			time_in_force='day', # or 'ioc' 'immediate or cancel'
	#		extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			print(+str(e))
			#pass
	