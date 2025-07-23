import os
import sys
import datetime
import time
import mysql.connector


try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO


#connect to database


#con = mydb = mysql.connector.connect(user='root', password='[your pw]', host='192.168.1.154', database='aapl') # connects to Mini-2
#con = mydb = mysql.connector.connect(user='root', password='[your pw]', host='192.168.1.167', database='aapl') # connects to iMac
con = mydb = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='aapl')
con2 = mydb = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='aapl')


from datetime import date, timedelta
today = date.today()
yesterday = today - timedelta(days = 1)

#print(today)

timestamp = int(time.time())
localtime = time.ctime(timestamp)
#print("Local time:", localtime)


#print(timestamp)
#print(today)
today = str(today)
mtoday = today.replace("-","")
#print(mtoday)

table = "predictions_aapl_5min"
table1 = "prices_aapl_daily"
table2 = 'long_trades_dan1'

# Dan's Acct 1

os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
os.environ["APCA_API_KEY_ID"] = "PK2E1EDFPQLE8W7A89TK"
os.environ["APCA_API_SECRET_KEY"] = "uZYBmwtAk7CbkxGW7LU2t76t7E0WEtM8I4AVhFW5"

# Dan's Acct 2


os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
os.environ["APCA_API_KEY_ID"] = "PKJXFW0QE0VWGSJEOV90"
os.environ["APCA_API_SECRET_KEY"] = "0YaxxoFNAkuSkkRGaJdQG2Zu6HRF01bUoxTxCMag"

	
import alpaca_trade_api as tradeapi
			
api = tradeapi.REST()



sql1 = "select unixtime,prediction,lagtime,localtime from " +table+ " order by unixtime desc limit 1"

cursor1 = con.cursor()
print ("sql1:", (sql1))
cursor1.execute(sql1)
result = cursor1.fetchall()
for x in result:
	unixtime = (x[0])
	predict = (x[1])
	lag = (x[2])
	l = str((x[3]))

cursor1.close()
localtime = time.ctime(timestamp)
date = str(localtime)

ux1 = str(timestamp - 300)
uxs = str(timestamp)

sql2 = "select price from  " +table1+ " where unixtime between " +ux1+ " and " +uxs+ " and price > 0 order by unixtime desc limit 1"

print ("sql2:", (sql2))
cursor = con2.cursor()
cursor.execute(sql2)
result = cursor.fetchall()
for x in result:
	p = (x[0])
	p = (p / 4)
	print("Last Localtime: ", l, "Unixtime: ", unixtime, "Price: ",p,"Prediction:  ",predict,"\n")

cursor.close()


#predict = 1

if (predict > 0):
	

	sym ='AAPL'
	qty = '1'
	side = 'buy'
	type ='limit'
	tif = 'ioc'
			
		
	clientid = "LONGBUY" + uxs
	
		
	print("Variables: ",sym,qty,side,type,p,tif,clientid)
			
	
	 
	api.submit_order(
		symbol=sym,
		qty=qty,
		side=side,
		type=type,
		limit_price=p,
		time_in_force=tif,
		client_order_id=clientid)
		
		
		
	print("long trade created with clientid: ", clientid)
	
	# this records the transaction in the long_trades table with the tradeid equal to the Alpaca clientid for later order matching. Status is shown as "1" which means the trade is uncovered.  The "price" added to the long_trades table is called the "order_price" and is equal to the price of the equity when the prediction is made. This should be compared to the "filled_avg_price" which is the price when the Alapca buy trade is executed.
	
	clientid = str(clientid)
	date= str(date)
	price = str(p)
	sym = str(sym)
	qty = str(qty)
	side = str(side)
	y = str(predict)
	lag = str(lag)
	lag = '0'
	
	status = '1' # trade is open
	
	cursor2 = con2.cursor()
	sql3 = "insert into " +table2+ " (tradeid, unixtime, date, order_price, symbol, qty, side, status, order_type, predicted_change, trade_lag) values ('"
	qy3 = clientid  + "', '" + uxs + "', '" + date + "', '" + price + "', '" + sym + "', '" + qty + "', '" + side +  "', '" + status +  "', '" + type +   "', '" + y + "', '" + lag + "');"
	sql4 = sql3 + qy3 
	print ("sql4:", (sql4))
	cursor2.execute(sql4)#
	con2.commit()
	cursor2.close()








			
