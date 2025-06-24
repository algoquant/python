# run on crontab at 3:59 pm

import os
import sys
from datetime import date, datetime, timedelta
import time
import pandas as pd
import numpy as np
import pathlib
import requests
import alpaca_trade_api as tradeapi

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



# this uses Alapca account dan@flaglerstreettrading.com
from settings import login5p, acct_name5p, keya5p, keyb5p


login = login5p
acct_name = acct_name5p
key1 = keya5p
key2 = keyb5p
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

	ux =  int(time.time())
	uxs = str(ux)
	clientid = "COVER_" +symbol+ "_" + uxs			
	clientid = str(clientid)		
	print("sell dividends stocks")	
	print(clientid,symbol,qty,price)

	try:
		api.submit_order(
		symbol=symbol,
		qty=qtys,
		side='sell',
#		type='limit',
		type = 'market',
#		limit_price=price,
		time_in_force='day', # or 'ioc' 'immediate or cancel'
#		extended_hours=True,
		client_order_id=clientid)
        
	except Exception as e:
		#print(+str(e))
		pass
	
	time.sleep(1)


	