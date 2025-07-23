# This script queries the Alapca accounts for the most recent orders and confirms that they were completed, update the long_trades table with a "client_id" field and trade_status = "filled"

# This script is mission critical. It provides the "filled" trade_status to long_trades (Alpaca long account) and long_trades1 (Alpaca short account). See comment on line 63.

# It is run every 15 seconds and requests the most recent 10 trades (lines 34 and 136) which should be plenty at thei stage since  we are only place 2 trades a minute.

import datetime
import time as timecode
import mysql.connector
import sys, os
import alpaca_trade_api as tradeapi

#connect to database, but create database if not found

#con = mydb = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='aapl')
con2 = mydb = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='aapl')

con = mydb = mysql.connector.connect(user='root', password='[your pw]', host='192.168.1.84', database='qqq')

# Dan's Acct 1

os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
os.environ["APCA_API_KEY_ID"] = "PK2E1EDFPQLE8W7A89TK"
os.environ["APCA_API_SECRET_KEY"] = "uZYBmwtAk7CbkxGW7LU2t76t7E0WEtM8I4AVhFW5"



table = "aapl.long_trades_dan1"


ticker			= "AAPL" #default

api = tradeapi.REST()

# Get the most recent 10 orders
closed_orders = api.list_orders(
	status='all',
	limit=20
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
	
	tradeid = str(clientid)

	created_date = str(created_date)
	newdate = created_date[0:19]
	#print(newdate)


	if price == None:
		price = '0'
	if filled_qty == None:
		filled_qty = '0'

	z = clientid[0:7]
	#print(z)

# z is 'LONGBUY" if the Alpaca unique clientid was created in the long_trade_buy_py script which means that it was a "buy" order placed in the "long" Alpaca account. The update query below updates the trade_status of the entry in the long_trades table to "filled" which is used by the "long_trade_cover.py" script to decided what to sell. It also update the "filled_avg_price" field so it can be compared to the "order_price" [the price of the when the prediction was made] and futher compared to the avg_sold_price which is updtaed when the trade is covered.  
 	
	if z  == 'LONGBUY':

		price = str(price)
		filled_qty = str(filled_qty)
		clientid = str(clientid)
		clientid = clientid.replace("LONGBUY","LONGCVR")
		cdate = str(created_date) 
		
		#print("this confirms a long buy")	
		qy1 = "update " + table +  " set side = '" + side + "', trade_status = '" + status + "', filled_avg_price = '" + price + "', created_at = substr('"  + cdate + "',1,19), filled_qty = '" + filled_qty + "' where tradeid = '" + tradeid + "'"
		print(qy1)

	
		try:
			cursor1 = con2.cursor()
			sql = qy1
			cursor1.execute(sql)
			con2.commit()


		except mysql.connector.Error as e:
			print("update to Acct 1 failed:",e)

# z is 'LONGCVR" if the Alpaca unique clientid was created in the long_trade_cover_py script which means that a "sell" order was placed in the "long" Alpaca account to cover the trades that are marked "status" = 1 and "trade_status" = 'filled'. The update query below updates fields  in the long_trades table recording the "avg_sold_price" which is critical to determining the trade "profit" matching the original tradeid by matching the clientid in the long_trades table with unique clientid from Alpaca. 


	elif z  == 'LONGCVR':

		price = str(price)
		filled_qty = str(filled_qty)
		tradeid = str(clientid)
		cdate = str(created_date) 
		#tradeid = tradeid.replace("LONGCVR","LONGBUY")
		
		#print("this confirms a long buy")	
		qy2 = "update " + table +  " set side = '" + side + "', clientid = '" + clientid + "', trade_status = '" + status + "', avg_sold_price = '" + price + "', created_at = substr('"  + cdate + "',1,19), filled_qty = '" + filled_qty + "' where clientid = '" + tradeid + "'"
		print(qy2)

	
		try:
			cursor1 = con2.cursor()
			sql = qy2
			cursor1.execute(sql)
			con2.commit()


		except mysql.connector.Error as e:
			print("update to Acct 1 failed:",e)


con2.close()

