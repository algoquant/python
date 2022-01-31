import os
import sys
import datetime
import time
import mysql.connector
con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts')

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("\nLocal time:", localtime)

uxs = str(timestamp)

sql = "CREATE TABLE IF NOT EXISTS `equities` (`name`varchar(255), `status` varchar(20), `shortable` char(5), `tradeable` char(5), `marginable` char(5), `easy_to_borrow` char(5), `exchange` varchar(10), `id` varchar(100), `symbol` varchar(10), PRIMARY KEY (`symbol`)) ENGINE=InnoDB DEFAULT CHARSET=latin1"

print(sql)
cursor = con.cursor()
cursor.execute(sql)
con.commit()
cursor.close()


# Dan'Account 1

os.environ["APCA_API_BASE_URL"] = "https://paper-api.alpaca.markets"
os.environ["APCA_API_KEY_ID"] = "PKE0N5CPGCYMPKDG9H6U"
os.environ["APCA_API_SECRET_KEY"] = "Fp9tzXDfvjxOFqWjxHGyGF4nCLW5kty3BBAQG3ZH"


import alpaca_trade_api as tradeapi

api = tradeapi.REST()

import alpaca_trade_api as tradeapi

api = tradeapi.REST()

# Get a list of all active assets.
active_assets = api.list_assets(status='active')
#print(active_assets)

for asset in active_assets:
	symbol = str(asset.symbol)
	name = str(asset.name)
	marginable = str(asset.marginable)
	easy_to_borrow = str(asset.easy_to_borrow)
	tradeable = str(asset.tradable)
	shortable = str(asset.shortable)
	id = str(asset.id)
	exchange = str(asset.exchange)
	status = str(asset.status)

	name = name.replace("'","")
	
	#print(symbol, marginable, easy_to_borrow, tradeable, shortable, id, exchange, status)
	
	
	sql = "replace into equities (symbol, name, marginable, easy_to_borrow, tradeable, shortable, id, exchange, status) values ('" +symbol+ "', '" +name+ "', '" +marginable+ "', '" +easy_to_borrow+"', '" +tradeable+"', '" +shortable+"', '" +id+"', '" +exchange+"', '" +status+ "')"
	print(sql)
	cursor = con.cursor()
	print ("sql:", (sql))
	cursor.execute(sql)
	con.commit()
	cursor.close()
	
	