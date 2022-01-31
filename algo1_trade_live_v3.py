import os
import sys
from datetime import datetime, timedelta
from datetime import date
import time
import pandas as pd
import numpy as np
import mysql.connector
import subprocess
import pathlib
import alpaca_trade_api as tradeapi


# print(pd.__version__)
# exit()



#connect to database

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts', allow_local_infile=True)
DBconnection = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts')




today = date.today()
yesterday = str(today - timedelta(days = 1))
today = str(today)
mdate = today.replace("-","")

# for testing set today to past date
#today = '2020-11-20'

table = "algo1_orders"
table1 = "algo1_trades"
table2 = "closings"

timestamp = int(time.time())
localtime = time.ctime(timestamp)
ux = timestamp

starttime = time.time()

PATH = "/Users/danielsavage/flagler/algos/algo1"
PATH = pathlib.Path().absolute()

sql1 = "update " +table2+ " set pct_change = ((close / open) - 1) where open > 0"
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


ux = timestamp
uxs = str(ux)

# Dan's Long Account 

os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
os.environ["APCA_API_KEY_ID"] = "PK8ESAYXZ04ETCBV2G7I"
os.environ["APCA_API_SECRET_KEY"] = "v7m3iGUQNVGUrtx7iQ8QDqNvXKYCS1XmsOkDOHeV"



# prepare to make long buys

sql1 = "SELECT trim(symbol), premarket from " +table2+ " where date = '" +yesterday+ "' order by pct_change desc limit 100"
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
result = cursor.fetchall()
for x in result:
	ticker = (x[0])
	price = (x[1])
	sym = str(ticker)
	p1 = str(price)

	print("Ticker: ",ticker)

	try:
	
		api = tradeapi.REST()

	
		clientid = "LONG_" + sym + uxs
		print("Client order id: ",clientid)
		
		qty = '100'
		side = 'buy'
		type ='limit'
		type ='market'
		tif = 'day'
		tif = 'ioc'
		date = today
				
		
	
		sql1 = "replace into " + table1 +  " (unixtime, date, trade_status, side, qty, symbol, order_price, clientid, order_type, tradeid) values ('" +uxs+ "', from_unixtime(" +uxs+ "), '1', '" +side+ "', '" +qty+ "', '" +sym+ "', '" +p1+ "', '" +clientid+ "', '" +type+  "', '" +clientid+ "')"   
		
	
		print(sql1)
		cursor = con.cursor()
		cursor.execute(sql1)
		con.commit()
		cursor.close()
	
	

		try:

			api = tradeapi.REST()


			api.submit_order(
			symbol=sym,
			qty=qty,
			side=side,
			type=type,
			#limit_price=price,
			time_in_force=tif,
			#extended_hours=True,
			client_order_id=clientid)

		except Exception as e:
 			print("Alpaca long trade failed:"+str(e))
 			pass

		except alpaca_trade_api.rest.APIError as e:	
			print("Alpaca api rest failed:"+e)
			pass

	except OSError as e:
		print("Alpaca long trade failed")
		pass



# prepare to make short buys


sql1 = "SELECT trim(symbol), premarket from " +table2+ " where date = '" +yesterday+ "' and shortable = 'True' order by pct_change limit 100"
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
result = cursor.fetchall()
for x in result:
	ticker = (x[0])
	price = (x[1])
	sym = str(ticker)
	p1 = str(price)

	print("Ticker: ",ticker)

	try:
	
		api = tradeapi.REST()

	
		clientid = "SHORT_" + sym + uxs
		print("Client order id: ",clientid)
		
		qty = '100'
		side = 'sell'
		type ='limit'
		type ='market'
		tif = 'day'
		tif = 'ioc'
		date = today
				
		
	
		sql1 = "replace into " + table1 +  " (unixtime, date, trade_status, side, qty, symbol, order_price, clientid, order_type, tradeid) values ('" +uxs+ "', from_unixtime(" +uxs+ "), '1', '" +side+ "', '" +qty+ "', '" +sym+ "', '" +p1+ "', '" +clientid+ "', '" +type+  "', '" +clientid+ "')"   
		
	
		print(sql1)
		cursor = con.cursor()
		cursor.execute(sql1)
		con.commit()
		cursor.close()
	
	

		try:

			api = tradeapi.REST()


			api.submit_order(
			symbol=sym,
			qty=qty,
			side=side,
			type=type,
			#limit_price=price,
			time_in_force=tif,
			#extended_hours=True,
			client_order_id=clientid)

		except Exception as e:
 			print("Alpaca short trade failed:"+str(e))
 			pass

		except alpaca_trade_api.rest.APIError as e:	
			print("Alpaca api rest failed:"+e)
			pass

	except OSError as e:
		print("Alpaca short trade failed")
		pass


