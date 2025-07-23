# this script stores the crypto orders each hour

import os
import sys
from datetime import datetime, timedelta
import time
import pandas as pd
import numpy as np
import mysql.connector
import subprocess
import pathlib

# print(pd.__version__)
# exit()
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 100)

from datetime import date, timedelta


#connect to database

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='algos', allow_local_infile=True)

# create  orders table

table = "orders"



try:
	sql = "create table if not exists " +table+ " (clientid varchar(100) NOT NULL,created varchar(100), price float, filled_qty float, side varchar(10), symbol varchar(10), status varchar(20),PRIMARY KEY (clientid) )"
	print(sql)

	cursor= con.cursor()
	cursor.execute(sql)
	con.commit()
	cursor.close()

except:
	pass



today = date.today()
yesterday = today - timedelta(days = 1)
today = str(today)
mdate = today.replace("-","")

# for testing set today to past date
today = '2020-11-20'



timestamp = int(time.time())
localtime = time.ctime(timestamp)
ux = timestamp

starttime = time.time()
ux = timestamp
uxs = str(ux)


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

	
import alpaca_trade_api as tradeapi

api = tradeapi.REST()

# --------------- get orders -----------------

#time.sleep(2)		

closed_orders = api.list_orders(
	status='all',
	limit= 100
)	
#print(closed_orders)

for o in closed_orders:
	clientid = o.client_order_id
	created_date = o.created_at
	price = o.filled_avg_price
	filled_qty = o.filled_qty
	side = o.side
	symbol = o.symbol
	status = o.status
	
	print("Clientid: ", clientid, " Date: ",created_date," Price: ",price, " Filled Qty: ",filled_qty, " Side: ", side, " Symbol: ",symbol, " Status: ",status)
	
	
	
	tradeid = str(clientid)

	created_date = str(created_date)
	newdate = created_date[0:19]
	print(newdate)


	if price == None:
		price = '0'
	if filled_qty == None:
		filled_qty = '0'

	price = str(price)
	filled_qty = str(filled_qty)
	clientid = str(clientid)
	cdate = str(created_date) 
	
	
	qy1 = "replace into " + table +  " (clientid, created, price , filled_qty, side , symbol, status) values ('" +clientid+ "','" + created_date+ "','" + price + "','" + filled_qty+ "','" + side + "','" + symbol+ "','" + status+ "')"
	print(qy1)
	cursor = con.cursor()
	cursor.execute(qy1)
	con.commit()
	cursor.close()
	


	


				
