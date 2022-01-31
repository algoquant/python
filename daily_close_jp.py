import requests
import os
from datetime import date, timedelta
from datetime import datetime
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time# as timecode
import mysql.connector
import sys
import telegram_send
import signal
import argparse

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)


today = date.today()
yesterday = str(today - timedelta(days = 1))
today = str(today)
mdate = today.replace("-","")

# for testing set today to past date
#today = '2020-11-20'

print("Today: ",today, "Yesterday: ",yesterday)


global polygon_api_key

#connect to database

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts', allow_local_infile=True)
db_connection = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts')

table = "equities"


import datetime

f = open("closings.csv", "w")

header = "date,ticker,status,open,high,low,close,volume,afterHours,preMarket\n"
f.write(header)

sql = "select count(*) from " +table+ " where tradeable = 'True'"
cursor1 = con.cursor()
print ("sql:", (sql))
cursor1.execute(sql)
result = cursor1.fetchall()
for x in result:
	cnt = (x[0])
	print("Count: ",cnt)


sql = "select symbol,name from " +table+ " where tradeable = 'True'"
cursor1 = con.cursor()
print ("sql:", (sql))

cursor1.execute(sql)
result = cursor1.fetchall()
for x in result:
	symbol = str(x[0])
	name = str(x[1])

	print("Symbol: ",symbol)
	
	a = "https://api.polygon.io/v1/open-close/"
	b = "/"
	c = "?apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
	url = a + symbol + b + yesterday + c
	url = str(url)
	print(url)

	getstring = url


	#print(getstring)
	resp = requests.get(getstring)
	print(resp)

	if resp.status_code != 200:
		# This means something went wrong.
		raise ApiError('GET /historical/ {}'.format(resp.status_code))

	r=resp.json()

	print(r)

	ticker			= r['symbol']
	date			= r['from']
	status			= r['status']
	open			= r['open']
	high			= r['high']
	low				= r['low']
	close			= r['close']
	volume			= r['volume']
	afterHours		= r['afterHours']
	preMarket		= r['preMarket']
	
	ticker = str(ticker)
	date = str(date)
	status = str(status)
	open = str(open)
	high = str(high)
	low = str(low)
	close = str(close)
	volume = str(volume)
	afterHours = str(afterHours)
	preMarket = str(preMarket)
		
	print("ticker:",ticker, date, status, close)
	
	out = date + ", " +ticker+ "," +status+ "," +open+ "," +high+ "," +low+  "," +close+ "," +volume+ "," +afterHours+  "," +preMarket+ "\n"
	print(out)
	
	f.write(out)


f.close()
cursor1.close()

table = "closings"


sql1 = "create table IF NOT EXISTS " +table+ " (date char(10),ticker char(10) ,status int(1),open float,high float,low float,close float,volume int(12),afterHours float,preMarket float, pct_change float)"
print(sql1)


cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


sql1 = "load data local infile '/Users/danielsavage/flagler/algos/algo1/closings.csv' into table " +table+ " fields terminated by ','"
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()

sql = "update closings as a, equities as b set a.shortable = b.shortable where a.symbol = b.symbol"
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()




quit()

