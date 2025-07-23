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

# ---set trading variables ------------------------



symbol = 'ETH-USD'
size = 30
type = 'market'
tif = 'gtc'
target = 15
movingavgtime = 180 # time in minutes
currentux = timestamp

print("These are the trading variables")
print("Symbol: ",symbol," Trade size: ",size," Trade type: ",type," Time in force:",tif," Target Diff: ",target," Moving Avg Sample (mins): ",movingavgtime)

# create tables for storing results

#print(symbol)
table = symbol.replace("-","") + "_close"
#print(table)


try:
	sql = "create table if not exists " +table+ " (close float)"
#	print(sql)
	cursor= con.cursor()
	cursor.execute(sql)
	con.commit()
	cursor.close()

except:
	pass




# ----------------- get current price from Polygon

polygon_key = "SDpnrBpiRzONMJdl48r6dOo0_mjmCu6r" # angry_hoover

ticker = symbol.replace("-","/")

url = f'https://api.polygon.io/v1/last/crypto/{ticker}/?apiKey={polygon_key}'

getstring = url
#print(getstring)
resp = requests.get(getstring)

#print(resp)
if resp.status_code != 200:
	print("This means something went wrong")
	raise ApiError('GET /historical/ {}'.format(resp.status_code))
r=resp.json()

#print(r)
#print("Symbol: ",symbol)
last = r['last']

for item in last:
	p = (last["price"])

	price = str(p)




# ----------------- get average price from Polygon

polygon_key = "SDpnrBpiRzONMJdl48r6dOo0_mjmCu6r" # angry_hoover


ticker = symbol.replace("-","")
ticker = "X:" +ticker
#print("Ticker: ",ticker)


url = f'https://api.polygon.io/v2/aggs/ticker/{ticker}/range/1/minute/{d1}/{d2}?adjusted=true&sort=asc&limit={movingavgtime}&apiKey={polygon_key}'

getstring = url
#print(getstring)
resp = requests.get(getstring)

#print(resp)


if resp.status_code != 200:
	print("This means something went wrong")
	raise ApiError('GET /historical/ {}'.format(resp.status_code))


r=resp.json()

#		print(r)

for item in r["results"]:

	closed = str(item['c'])
	high = str(item['h'])
	low = str(item['l'])
	opened = str(item['o'])
	volume = str(item['v'])
	vwap = str(item['vw'])
	ux = (item['t'])

	ux = int(ux / 1000)
	uxs = str(ux)

#	print("Ticker: ",ticker, "Close: ",closed)

	try:
		sql1 ="replace into " +table+ " (close) values('"+closed+ "')"
#		print(sql1)
		cursor= con.cursor()
		cursor.execute(sql1)
		con.commit()
		cursor.close()
	except:
		pass


# print variables

sql2 = "select avg(close) from " +table
#print(sql2)

avgprice = 0

cursor = con.cursor()
cursor.execute(sql2)
result = cursor.fetchall()

for y in result:
	avgprice = (y[0])




# --------------Get Alpaca account information ----------------------

account = api.get_account()

#print(account)

starting_balance = account.equity
ending_balance = account.equity


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
			
# ------------ display variables ---------------------------------------


price = float(price)
avgprice = float(avgprice)
diff = (avgprice - price)
buyticker = ticker.replace("X:","")


print("Symbol: ",symbol, " Ticker:", ticker, " Buy Ticker:",buyticker)
print("Starting Balance: ", starting_balance)
print("Current Balance: ", ending_balance)
print("Current Price: ",price)
print("Average Price: ",avgprice)
print("Price Difference: ", diff)
print("Position Size: ", qty)
#print("Current Unixtime: ",currentux)
print("Current position", qty)
print("Position side:",side)
print("Buy qty: ",size)
print("Order type: ", type)
print("Time in force: ", tif)
print("Target: ",target)


# make a trade

if ((diff > target) & (qty == 0)):

	print("make a buy")
	print("The current price is below the avg price. Buy shares")

	clientid = buyticker+ "_BUY_" +uxs	
	print(clientid)


	
	try:
		api.submit_order(
		symbol= str(buyticker),
		qty= str(size),
		side="buy",
		type= str(type),
#		limit_price = price,
		time_in_force= str(tif),
		client_order_id= str(clientid)
		)
	except Exception as e:
		print(+str(e))
		pass

	
	buyorder = clientid+ "," +buyticker+ "," +size+ "," +side+ "," +type+ "," +tif+ "\n"
	print(buyorder)


elif (gain > 0.01):

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




quit;


