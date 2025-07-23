import requests
import os
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time
import datetime
from datetime import datetime
from datetime import timedelta
import mysql.connector
import sys
import telegram_send
import signal
import argparse
import subprocess


#connect to database

#con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts', allow_local_infile=True)
global polygon_api_key

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)



starttime = time.time()

x = 1
xs = str(x)

for x in range(1,8977):
for x in range(1,20):

	try:

		con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts', allow_local_infile=True)


		xs = str(x)
		sql = "select symbol from equities limit " +xs+ ",1"
		print(sql)
		cursor = con.cursor()
		cursor.execute(sql)
		result = cursor.fetchall()
		for x in result:
			t = (x[0])
			
			symbol = str(t)
			print("Symbol: ",symbol)
		
			path = "/Volumes/ExtremePro/ml_trading_ext/tickers/" +symbol+ "/"
			path = "/Users/danielsavage/algos/tickers/" +symbol+ "/"
		
			cmd = "mkdir " +path
			print(cmd)
			subprocess.Popen(cmd, shell=True)
		
			cmd = "mkdir " +path+ "one_min_bars/"
			print(cmd)
			subprocess.Popen(cmd, shell=True)
			
			cmd = "mkdir " +path+ "one_hour_bars"
			print(cmd)
			subprocess.Popen(cmd, shell=True)
		

			
	except TypeError:
		pass
	
	
	x =+1


