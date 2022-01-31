# this script updates the large trainingset table prices_aapl with price data from the most recent day 

import os
import sys
import datetime
import time
import pandas as pd
import numpy as np
import mysql.connector

pd.set_option('display.max_rows', 500)

from datetime import date, timedelta

today = date.today()
yesterday = today - timedelta(days = 1)
today = str(today)
mdate = today.replace("-","")

timestamp = int(time.time())
localtime = time.ctime(timestamp)
	
ux = (timestamp) # runs at 6:00:00


#connect to database


con = mydb = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='aapl')


table = "prices_aapl_daily" # past 4 weeks


print("create a row in this table for every second between 5 am and 6 pm")

#testing
#ux = 1600345800  # 9-17-2020 08:30:00

x = ux
y = (x + (3600*14))

for x in range (x,y):

	xs = str(ux)

	sql = "replace into " +table+ "(unixtime) values ('" +xs+ "')"
	#print(sql)
	cursor = con.cursor()
	cursor.execute(sql)
	con.commit()
	cursor.close()

	localtime = time.ctime(ux)
	print(localtime)	
	ux = (ux + 1)
	x =+ 1

