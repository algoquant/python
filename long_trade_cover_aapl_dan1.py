import os
import sys
import datetime
import time
import mysql.connector
import subprocess

# Dan's Acct 1

os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
os.environ["APCA_API_KEY_ID"] = "PK2E1EDFPQLE8W7A89TK"
os.environ["APCA_API_SECRET_KEY"] = "uZYBmwtAk7CbkxGW7LU2t76t7E0WEtM8I4AVhFW5"

# Dan's Acct 2


#os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
#os.environ["APCA_API_KEY_ID"] = "PKJXFW0QE0VWGSJEOV90"
#os.environ["APCA_API_SECRET_KEY"] = "0YaxxoFNAkuSkkRGaJdQG2Zu6HRF01bUoxTxCMag"


import alpaca_trade_api as tradeapi
api = tradeapi.REST()

#connect to database

con2 = mydb = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='aapl')
con1 = mydb = mysql.connector.connect(user='root', password='[your pw]', host='192.168.1.154', database='aapl')  #Mini 2

#tables

table = "aapl.long_trades_dan1"
table1 = "aapl.prices_aapl_daily"




from datetime import date, timedelta
today = date.today()
yesterday = today - timedelta(days = 1)

print("this is long_trade_cover aapl in dan1 acct.py")

timestamp = int(time.time())
localtime = time.ctime(timestamp)
#print("Local time:", localtime)


#print(timestamp)
#print(today)
today = str(today)
mtoday = today.replace("-","")
#print(mtoday)


start = time.time()
start = int(start)
st = str(start)

timestamp = start

# this script runs 290 seconds behind the long_trade_buy script closing out any open trades. 

  
ux = str(timestamp)
uxs = str(ux)
ux1 = timestamp - 290
ux1s = str(ux1)

uxtime = time.ctime(ux1)
localtime = time.ctime(timestamp)
print("Local time:", localtime, "Ux time: ", uxtime)


#print(ux)


# this query updates the arithmetic in the long_trades table

try:
	cursor2 = con2.cursor()
	qy2 = "update " + table + " set profit = ((avg_sold_price - filled_avg_price) * filled_qty), predicted_profit = ((predicted_change * filled_qty)) where status = 2"
	#print (qy2)
	cursor2.execute(qy2)
	con2.commit()

	qy3 = "update " + table + " set profit = 0 where profit is null"
	#print (qy3)
	cursor2.execute(qy3)
	con2.commit()

except mysql.connector.Error as e:	
	print("skipped on errors line 92:",e)

# this query identifies the oldest buy in the long_trades table that is  uncovered (status = 1) looking trades that have been reported "filled' from Alpaca.

qy1 = "select qty, symbol, tradeid from " +table+ " where tradeid like 'LONG%' and trade_status = 'filled' and status = 1 and unixtime < '" + ux1s + "' limit 1"
print(qy1)

qty = 0
sym = ''
tradeid = ''
qtys = ''


try:
	cursor2 = con2.cursor()
	cursor2.execute(qy1)
	result = cursor2.fetchall()
	for x in result:
		#print(x)
		qty = (x[0])
		sym = (x[1])
		tradeid = (x[2])
		print("Qty: ",qty,"Symbol: ",sym,"Tradeid: ",tradeid)
	cursor2.close()
except mysql.connector.Error as e:
	print("skipped on errors line 119:",e)


qtys = str(qty)




if qty > 0:

	print ("cover query: ",qy1)
	print("tradeid: ", tradeid)

	# trading variables
	side ='sell'
	type ='market'
	tif = 'day'
	clientid = "LONGCVR" + uxs
	print("clientid: ", clientid)

# this submits an order to Alpaca with a unique clientid "LONGCVR" + unixtime

	try:	
		api.submit_order(
				symbol=sym,
				qty=qtys,
				side=side,
				type=type,
				time_in_force=tif,
				client_order_id=clientid
		)

	except mysql.connector.Error as e:
		print("long cover trade failed:",e)

# this updates the long_trades table for the tradeid in line 86 above and changes the status to "2" in the long_trades table. The clientid in the table is updated to match the Alapca clientid just submitted.


	print("this confirms a cover of a long trade")	
	qy1 = "update " +table+  " set status = 2, clientid = '" + clientid + "' where tradeid = '" + tradeid + "'"
	print(qy1)


	try:
		sql = qy1
		cursor2 = con2.cursor()
		cursor2.execute(sql)
		con2.commit()
		cursor2.close()


	except mysql.connector.Error as e:
		print("skipped on errors lin 220:",e)



