# this script runs every second and overs orders once profit target is reached

import os
import sys
from datetime import date, datetime, timedelta
import time
import pandas as pd
import numpy as np
import mysql.connector
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

d1 = today
d2 = today
print(d1,d2)


timestamp = int(time.time())
localtime = time.ctime(timestamp)

#connect to database

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='algos', allow_local_infile=True)


# -------  alpaca keys ----------------------------

#pta7p	key1 = PKULWOIOXYLHBFOX3O05	key2 = G5HYWE3ZUpLAEYWVB4QcTZNISbne46E3YqG2GDrW	algo3 - live

print("this algo is running in pta7p")

key1 = 'PKULWOIOXYLHBFOX3O05'
key2 = 'G5HYWE3ZUpLAEYWVB4QcTZNISbne46E3YqG2GDrW'
endpoint = "https://paper-api.alpaca.markets"

#print(key1)
#print(key2)
#print(endpoint)

os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

api = tradeapi.REST()

	
	
x = 1

for x in range(1,10):

# ------------------- get Alpaca positions ---------------------------
	
	
	portfolio = api.list_positions()
	
	#print(portfolio)
	
	qty = 0
	side = ''
	
	
	# Print the quantity of shares for each position.
	
	for Position in portfolio:
	
		price = Position.current_price
		symbol = Position.symbol
		qty = Position.qty
		side = Position.side
		gain = float(Position.unrealized_plpc)
	
		print("the current position is: ",symbol," Price: ", price," Qty: ",qty," Side: ",side," Gain: ",gain)
	
	# ------------------- make trades ----------------------------------------


	if (gain > 0.01):
	
		print("cover position")
		print("The gain is greate than 1%. Sell shares")
	
		clientid = buyticker+ "_SELL_" +uxs	
		print(clientid)
	
	
		
		try:
			api.submit_order(
			symbol= str(buyticker),
			qty= str(qty),
			side="sell",
			type= str(type),
	#		limit_price = price,
			time_in_force= str(tif),
			client_order_id= str(clientid)
			)
		except Exception as e:
			print(+str(e))
			pass
	
		
		sellorder = clientid+ "," +buyticker+ "," +qty+ "," +side+ "," +type+ "," +tif+ "\n"
		print(sellorder)


	time.sleep(1)

	print(x)	
	x =+ 1
	
	
	