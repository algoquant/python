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
from settings import login4p, acct_name4p, keya4p, keyb4p

timestamp = int(time.time())

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


# close all open orders

api.cancel_all_orders()

# Get the last 500 of our closed orders
closed_orders = api.list_orders(
    status='open',
    limit=500,
    #/nested=True  # show nested multi-leg orders
)

#print(closed_orders)



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

	qtys = str(qty)
	symbol = str(symbol)	
	print("the current position is ",symbol,"Current price: ", price,"Qty: ",qty,"Side: ",side)

	# cover shares 100 a time

	z = qty / 100
	a = 1
	for a in range(a,z)
		
		# make the trade with Alpaca

			
		ux =  int(time.time())
		uxs = str(ux)
		clientid = "COVER_" +symbol+ "_" + uxs			
		clientid = str(clientid)		
		print("sell dividends stocks")	
		print(clientid,symbol,qty,price)
	
		try:
			api.submit_order(
			symbol=symbol,
			qty='100',
			side='buy',
	#		type='limit',
			type = 'market',
	#		limit_price=price,
			time_in_force='day', # or 'ioc' 'immediate or cancel'
	#		extended_hours=True,
			client_order_id=clientid)
	        
		except Exception as e:
			#print(+str(e))
			pass

	a =+ 1
			
	time.sleep(5)	
	x =+1


quit()
		


