import os
import sys
import datetime
import time
import mysql.connector
import subprocess

# Dan's Acct 1

#os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
#os.environ["APCA_API_KEY_ID"] = "PK2E1EDFPQLE8W7A89TK"
#os.environ["APCA_API_SECRET_KEY"] = "uZYBmwtAk7CbkxGW7LU2t76t7E0WEtM8I4AVhFW5"

# Dan's Acct 2


os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
os.environ["APCA_API_KEY_ID"] = "PKJXFW0QE0VWGSJEOV90"
os.environ["APCA_API_SECRET_KEY"] = "0YaxxoFNAkuSkkRGaJdQG2Zu6HRF01bUoxTxCMag"


import alpaca_trade_api as tradeapi
api = tradeapi.REST()

#connect to database

con2 = mydb = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='aapl')
#con2 = mydb = mysql.connector.connect(user='root', password='[your pw]', host='192.168.1.154', database='aapl')  # Mini 2

#con2 = mydb = mysql.connector.connect(user='root', password='[your pw]', host='192.168.1.84', database='qqq')  # Mini4


from datetime import date, timedelta
today = date.today()
yesterday = today - timedelta(days = 1)

print("this is short_trade_cover_aqpl_dan2.py")

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

table = "aapl.short_trades_dan2"
table1 = "aapl.prices_aapl_daily"

cursor2 = con2.cursor()

# this query updates the arithmetic in the short_trades table

try:
	qy2 = "update " + table + " set profit = ((filled_avg_price - avg_sold_price) * filled_qty), predicted_profit = ((predicted_change * filled_qty)) where status = 2"
	print (qy2)
	cursor2.execute(qy2)
	con2.commit()

	qy3 = "update " + table + " set profit = 0 where profit is null"
	print (qy3)
	cursor2.execute(qy3)
	con2.commit()

except mysql.connector.Error as e:	
	print("skipped on errors line 92:",e)



# this query identifies the oldest buy in the long_trades table that is  uncovered (status = 1) looking trades that have been reported "filled' from Alpaca.

qy1 = "select qty, symbol, tradeid from " +table+ " where tradeid like 'SHORT%' and trade_status = 'filled' and status = 1 and unixtime < '" + ux1s + "' limit 1"
print(qy1)

qty = 0
sym = ''
tradeid = ''
qtys = ''


try:
	cursor2.execute(qy1)
	result = cursor2.fetchall()
	for x in result:
		#print(x)
		qty = (x[0])
		sym = (x[1])
		tradeid = (x[2])
		print("Qty: ",qty,"Symbol: ",sym,"Tradeid: ",tradeid)
except mysql.connector.Error as e:
	print("skipped on errors line 119:",e)


qtys = str(qty)



if qty > 0:

	print ("cover query: ",qy1)
	print("tradeid: ", tradeid)

	# trading variables
	side ='buy'
	type ='market'
	tif = 'day'
	clientid = "SHORTCVR" + uxs
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
		print("short cover trade failed:",e)

# this updates the short_trades_dan2 table for the tradeid in line 86 above and changes the status to "2" in the short_trades_long_dan2 table. The clientid in the table is updated to match the Alapca clientid just submitted.


	print("this confirms a cover of a short trade")	
	qy3 = "update " +table+  " set status = 2, clientid = '" + clientid + "' where tradeid = '" + tradeid + "'"
	print(qy1)


	try:
		sql3 = qy3
		cursor2.execute(sql3)
		con2.commit()

	except mysql.connector.Error as e:
		print("skipped on errors lin 220:",e)


cursor2.close()



