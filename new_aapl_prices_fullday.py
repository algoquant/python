import os
import sys
import datetime
import time
import pandas as pd
import numpy as np
import mysql.connector
import subprocess
import linecache, warnings

# import the module
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError

print("\nstart")

pd.set_option('display.max_columns', 50)

from datetime import date, timedelta

today = date.today()
yesterday = today - timedelta(days = 1)
today = str(today)
mdate = today.replace("-","")

#connect to database

con1 = mydb = mysql.connector.connect(user='root', password='[your pw]', host='192.168.1.82', database='aapl')

con = mydb = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='aapl', allow_local_infile=True)

db_connection = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='aapl')

# create sqlalchemy engine
engine = create_engine("mysql+pymysql://{user}:{pw}@localhost/{db}"
				   .format(user="root",
						   pw="[your pw]",
						   db="aapl"))


table = "aapl.prices_aapl_daily"
table = "aapl.prices_aapl_daily_all"
table1 = "aapl_polygon"
#table1 = "aapl_polygon20200925"
table1 = "aapl_polygon20201001"

#sql = "create table IF NOT EXISTS xmas	 (unixtime BIGINT(20), volume_1sec float, change1sec float, change30sec float, change1min float, change2min float,change5min float,change1hr float, std_1min float, std_2min float, std_5min float, std_1hr float, xavgchange30sec float, xavgchange1min float, xavgchange2min float, xavgchange5min float, xavgchange1hr float)"
#sql1 = "create unique index ux on xmas(unixtime)"
#
#print (sql)
#cursor = con.cursor()
#cursor.execute(sql)
#con.commit()
#cursor.execute(sql1)
#con.commit()
#cursor.close()
#

PATH = "/Users/danielsavage/flagler/trainingsets/pandas/"

# testing
ux = 1601559000

a = 1

for a in range(1,23400):

	timestamp = int(time.time())
	localtime = time.ctime(timestamp)
	
	#ux = (timestamp - 3) # lag time for script
	
	lagtime = time.ctime(ux)
	
	print("Actual time:", localtime, timestamp, "Script time:", lagtime, ux)
	
	print("update the prices_aapl_daily table with current prices and volumes")
	
	zx1 = ux
	zx = str(zx1)
	zxs = str(zx1 - 360)
	
	sql = "select unixtime from " +table+ " where price is null and unixtime between " +zxs+ " and " +zx
	#print(sql)
	cursor = con.cursor()
	cursor.execute(sql)
	result = cursor.fetchall()
	
	
	for z in result:
		uz1 = (z[0])
		uzs1 = str(uz1)
	
		uz2 = (uz1 - (3600))
		uzs2 = str(uz2)
		
		sql1 = "select price from " +table+ " where unixtime between " +uzs2+ " and " +uzs1+ " and price > 0 order by unixtime desc limit 1"
		#print(sql1)
		cursor1 = con.cursor()
		cursor1.execute(sql1)
		result1 = cursor1.fetchall()
		cursor1.close()
	
		for y in result1:
			price = str((y[0]))
	
			sql2 = "update " +table+ " set price = " +price+ " where unixtime = " +uzs1
			#print(sql2)
			cursor.execute(sql2)
			con.commit()
	
	cursor.close()		
	
	sql1 = "select last_price from " + table1 + " where last_time between " +zxs+ " and " +zx+ " and last_price > 0 order by last_time desc limit 1"
	
	cursor1 = con1.cursor()
	#print ("sql1:", (sql1))
	cursor1.execute(sql1)
	result = cursor1.fetchall()
	for x in result:
		last_price = str((x[0])*4)
		#print(last_price)

	sql2 = "select sum(last_size) from " + table1 + " where last_size > 0 and last_time =  " +zx
	#print ("sql2:", (sql2))
	cursor1.execute(sql2)
	result = cursor1.fetchall()
	for y in result:
		volume = str((y[0]))
		
		if (volume == 'None'):
			volume = '0'
		#print(volume)	

	cursor1.close()

	sql3 = "update " + table + " set price = " +last_price+ ", volume_1sec = " + volume + " where unixtime = " +zx
	print (sql3)
	cursor = con.cursor()
	cursor.execute(sql3)
	con.commit()

	sql3 = "update " + table + " set volume_1sec = 0  where volume_1sec is null"
	print (sql3)
	cursor = con.cursor()
	cursor.execute(sql3)
	con.commit()
	cursor.close()


	ux = (ux + 1)
	a =+ 1
		
	
	
