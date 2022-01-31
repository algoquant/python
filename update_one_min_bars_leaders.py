
import requests
import os
from datetime import datetime, timedelta
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time# as timecode
import mysql.connector
import sys
import telegram_send
import signal
import argparse

global polygon_api_key

timestamp = int(time.time())
localtime = time.ctime(timestamp)
		
ux = timestamp

starttime = time.time()

#connect to database

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts', allow_local_infile=True)
table = "one_minute_bars"
table1 = "equities"
table2 = "leaders_volume_index_at_open"


# at open 9:30
startmin = 1612794600

# preopen at 9:00 
startmin = 1612794600 - 1800

# just after open at 9:35 
startmin = 1612794600 + 300

#  10:00 
startmin = 1612794600 + 1800

# at close
endmin = 1612818000
endmin10 = endmin + 10

# at 3:30
#endmin = 1612818000 - 1800
#endmin10 = endmin + 10

# csv file name
filename = "volume_index_at_900"
filename = "volume_index_at_935"
filename = "volume_index_at_1000"


startmin = str(startmin)
endmin = str(endmin)
endmin10 = str(endmin10)


sql = "drop table IF EXISTS " +table2
print(sql)
cursor = con.cursor()
cursor.execute(sql)
con.commit()
cursor.close()

sql = "create table IF NOT EXISTS " +table2+ "(id int auto_increment,symbol varchar(10),volume int(10), volume_index float,minopen float, minclose float, mingain float,dayopen float, dayclose float, daygain float, daypctgain float, PRIMARY KEY(id))"
print(sql)
cursor = con.cursor()
cursor.execute(sql)
con.commit()
cursor.close()


sql = "select symbol, volume, volume_index,open,close from " +table+ " where unixtime = " +startmin+ " order by volume_index desc"
print(sql)
cursor = con.cursor()
cursor.execute(sql)
result = cursor.fetchall()
for x in result:
	t = (x[0])
	v = (x[1])
	vi = (x[2])
	o = (x[3])
	c = (x[4])
	g = c - o
	
	symbol = str(t)
	volume = str(v)
	vol_index = str(vi)
	opened = str(o)
	closed = str(c)
	gain = str(g)

	sql1 = "replace into " +table2+ " (symbol, volume, volume_index, minopen, minclose, mingain) values ('" +symbol+ "', '" +volume+"', '" +vol_index+ "', '" +opened+ "', '" +closed+ "', '" +gain+ "')"
	print(sql1)
	cursor = con.cursor()
	cursor.execute(sql1)
	con.commit()
	cursor.close()

sql = "select distinct symbol, open,close from " +table+ " where unixtime between " +endmin+ " and " +endmin10
print(sql)
cursor = con.cursor()
cursor.execute(sql)
result = cursor.fetchall()
for x in result:
	t = (x[0])
	o = (x[1])
	c = (x[2])
	g = c - o
	
	if (o > 0):
		pctg = (g / o) * 100
	else:
		pctg = 0
	
	symbol = str(t)
	dayopened = str(o)
	dayclosed = str(c)
	daygain = str(g)
	daypctgain = str(pctg)

	sql1 = "update " +table2+ " set dayopen = " +dayopened+ ", dayclose = " +dayclosed+ ", daygain = " +daygain+ ", daypctgain = " +daypctgain+ " where symbol = '" +symbol+ "'"
	print(sql1)
	cursor = con.cursor()
	cursor.execute(sql1)
	con.commit()
	cursor.close()


# create a dataframe and output a .csv file

try:


	query = "Select * from " +table2
	df = pd.read_sql(query,mydb)


	mydb.close() #close the connection
except Exception as e:
	mydb.close()
	print(str(e))

print(df.head)

outfile = "/Users/danielsavage/algos/" +filename+ ".csv"
#print(outfile)
df.to_csv(outfile, index=False)


