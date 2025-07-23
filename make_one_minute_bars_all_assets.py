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
import linecache

def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f_err = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f_err.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f_err.f_globals)
    print ('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))


#connect to database

#con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts', allow_local_infile=True)
global polygon_api_key

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)



starttime = time.time()

#x = 1
#xs = str(x)
#
#for x in range(1,8977):
##for x in range(1,20):
#
#	try:
#
#		con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts', allow_local_infile=True)
#
#
#		xs = str(x)
#		sql = "select symbol from equities limit " +xs+ ",1"
#		print(sql)
#		cursor = con.cursor()
#		cursor.execute(sql)
#		result = cursor.fetchall()
#		for x in result:
#			t = (x[0])
#			
#			symbol = str(t)
#			print("Symbol: ",symbol)
#		
#			path_str = "/Volumes/ExtremePro/ml_trading_ext/tickers/" +symbol+ "/"
#		#	path_str = "/Users/danielsavage/algos/tickers/" +symbol+ "/"
#		
#			cmd = "mkdir " +path_str
#			#print(cmd)
#			subprocess.Popen(cmd, shell=True)
#		
#			cmd = "mkdir " +path_str+ "one_min_bars/"
#			#print(cmd)
#			subprocess.Popen(cmd, shell=True)
#			
#			cmd = "mkdir " +path_str+ "one_hour_bars"
#			#print(cmd)
#			subprocess.Popen(cmd, shell=True)
#		
#
#			
#	except TypeError:
#		pass
#	
#	
#	x =+1
#
#

ux = 1577970000 # Thursday, January 2, 2020 8:00:00 AM GMT-05:00


z = 0
for z in range(0,14):

	print(z)
	zs = str(z)	

	x = 1
	xs = str(x)
	con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts', allow_local_infile=True)
	
	
	for x in range(1,8977):
	#for x in range(1,2):
	
		xs = str(x)
#		sql = "select symbol from equities where symbol = 'AA'"
		sql = "select symbol from equities limit " +xs+ ",1"
		print(sql)
		cursor = con.cursor()
		cursor.execute(sql)
		result = cursor.fetchall()
		for y in result:
			t = (y[0])
			
			symbol = str(t)
			print("Symbol: ",symbol)
		
	
	
			path_str = "/Volumes/ExtremePro/ml_trading_ext/tickers/" +symbol+ "/one_min_bars/"
		#	path_str = "/Users/danielsavage/algos/tickers/" +symbol+ "/"
		
	
	
		
				
			filename_str = path_str+ "one_minute_bars" +zs+ ".csv"  	
	
			print("create file:", filename_str)	
		
			try:	
				f = open(str(filename_str), "w")
			except: 
				PrintException()
	
		
			ux1 = ux 
			ux1s = str(ux1)
		
			ux2 = ux1 + (30 * 86400)
			ux2s = str(ux2)
		
			
			dt1 = datetime.utcfromtimestamp(ux1).strftime('%Y-%m-%d')
			dt2 = datetime.utcfromtimestamp(ux2).strftime('%Y-%m-%d')
			
		
			getstring=f'https://api.polygon.io/v2/aggs/ticker/{t}/range/1/minute/{dt1}/{dt2}?sort=asc&limit=30000&apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u'
			print(getstring)
		
			resp = requests.get(getstring)
			#print(resp)

		
			r=resp.json()
	
		#	print(r)
		
			try:	
				results			= r['results']
		#		map				= r['map']
				ticker			= r['ticker']
				queryCount 		= r['queryCount']
				resultsCount	= r['resultsCount']
				adjusted		= r['adjusted'] 		
		
			except KeyError:
				pass
			except NameError:
				pass
			except: 
				PrintException()
				pass						
			#print("ticker:",ticker, queryCount,resultsCount,adjusted)
		
		#	return results
			import csv 
		
			try:
				for item in results:
					#print(item)
					vwap = str(item['vw'])
					open_s = str(item['o'])
					close_s = str(item['c'])
					high = str(item['h'])
					low = str(item['l'])
					unixtime = str(item['t'])
					volume = str(item['v'])
	
					out = t+ ", " +unixtime+ ", "  +volume+ "," +vwap+ "," +open_s+ "," +close_s+ "," +high+  "," +low+ "\n"
			
					print(out)
					f.write(out)
			except KeyError:
				pass
			except NameError:
				pass
			except: 
				PrintException()
				pass		
		
			try:
				f.close()
			except: 
				PrintException()
				pass		
		
				
	con.close()



	ux = (ux + 2592000)
	

	
			
	z =+1		
		


quit()


