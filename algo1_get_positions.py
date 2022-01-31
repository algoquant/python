import datetime
import time
import mysql.connector
import sys, os
import alpaca_trade_api as tradeapi

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts')


timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)

#print(timestamp)
#print(today)
#today = str(today)
#mtoday = today.replace("-","")
#print(mtoday)

uxs = str(timestamp)


# Dan's Long Account 

os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
os.environ["APCA_API_KEY_ID"] = "PK8ESAYXZ04ETCBV2G7I"
os.environ["APCA_API_SECRET_KEY"] = "v7m3iGUQNVGUrtx7iQ8QDqNvXKYCS1XmsOkDOHeV"

api = tradeapi.REST()

portfolio = api.list_positions()
print(portfolio)

table1 = "algo1_trades"
#print(table1)


# Print the quantity of shares for each position.
for Position in portfolio:

	price = Position.current_price
	symbol = Position.symbol
	qty = Position.qty
	side = Position.side

#	print(price,symbol,qty,side)

	if (side == 'long'):

		clientid = symbol+ "_COVER" + uxs
		qty = int(qty)
		
		print("Sell ", side, "order :",symbol," qty: ",qty," at price: ",price, " with clientid: ",clientid)


		sym = str(symbol)
		p1 = str(price)
		quant = str(qty)
		sides = str(side)
		type = 'limit'

		api.submit_order(
		symbol=symbol,
		qty=qty,
		side='sell',
#		type='limit',
		type='market',
#		limit_price=price,
#		time_in_force='ioc',
		time_in_force='day',
		#extended_hours=True,
		client_order_id=clientid)


#		sql1 = "replace into " + table1 +  " (unixtime, date, trade_status, side, qty, symbol, order_price, clientid, order_type, tradeid) values ('" +uxs+ "', from_unixtime(" +uxs+ "), '1', 'sell', '" +quant+ "', '" +sym+ "', '" +p1+ "', '" +clientid+ "', '" +type+  "', '" +clientid+ "')"   
#		print(sql1)
#		cursor = con.cursor()
#		cursor.execute(sql1)
#		con.commit()
#		cursor.close()
#
	if (side == 'short'):

		clientid = symbol+ "_COVER" + uxs
		qty = int(qty)
		print("Cover ", side, "order :",symbol," qty: ",qty," at price: ",price, " with clientid: ",clientid)

		sym = str(symbol)
		p1 = str(price)
		qty = (qty * -1)
		
		quant = str(qty)
		type = 'limit'

		sql1 = "replace into " + table1 +  " (unixtime, date, trade_status, side, qty, symbol, order_price, clientid, order_type, tradeid) values ('" +uxs+ "', from_unixtime(" +uxs+ "), '1', 'buy', '" +quant+ "', '" +sym+ "', '" +p1+ "', '" +clientid+ "', '" +type+  "', '" +clientid+ "')"   
#		print(sql1)
#		cursor = con.cursor()
#		cursor.execute(sql1)
#		con.commit()
#		cursor.close()
#
		api.submit_order(
		symbol=symbol,
		qty=qty,
		side='buy',
#		type='limit',
		type='market',
#		limit_price=price,
#		time_in_force='ioc',
		time_in_force='day',
		#extended_hours=True,
		client_order_id=clientid)



# Get our position in AAPL.
#
##qqq_position = api.get_position('QQQ')
##print(qqq_position)
#
#portfolio = api.list_positions()
#
#
## Print the quantity of shares for each position.
#for position in portfolio:
#	price = position.current_price
#	symbol = position.symbol
#	qty = position.qty
#	side = position.side
#
#	print(price,symbol,qty,side)
#
#	time.sleep(3)
#
#
#	portfolio = api.list_positions()
#	#print(portfolio)
#
#
#	# Print the quantity of shares for each position.
#	for position in portfolio:
#		price1 = position.current_price
#		symbol = position.symbol
#		qty = position.qty
#		side = position.side
#
#		print(price1,symbol,qty,side)
#
#		price = float(price)
#		price1 = float(price1)	
#		change = price1 - price	
#		print("Change: ", change)
#		quantity = int(qty) 
#		buyqty = quantity * -1 
#		clientid = "SHORTCOVER" + ux 
#
#		if (change > 0 and quantity < 0):
#			print("Making a covering trade")
#			api.submit_order(
#			symbol=symbol,
#			qty=buyqty,
#			side= 'buy',
#			type= 'market',
#			time_in_force= 'day',
#			client_order_id=clientid)
#
#