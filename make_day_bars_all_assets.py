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

polygon = "SDpnrBpiRzONMJdl48r6dOo0_mjmCu6r" #angry_hoover
starttime = time.time()

ux = (timestamp - (86400 * 30))  
uxs = str(ux)

ux1 = timestamp

x = 1
xs = str(x)

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='ticker_prices', allow_local_infile=True)


sql = "select distinct symbol from all_assets"
#sql = "select distinct symbol from all_assets where symbol = 'AAPL'"
print(sql)
cursor = con.cursor()
cursor.execute(sql)
result = cursor.fetchall()

for y in result:
	t = (y[0])
	
	symbol = str(t)
	print("Symbol 30days: ",symbol)



	path_str = "/Volumes/ext_drive/get_ticker_data/30_day_bars/" +symbol

	ux1s = str(ux1)

	ux2 = ux 
	ux2s = str(ux2)

	
	dt1 = datetime.utcfromtimestamp(ux1).strftime('%Y-%m-%d')
	dt2 = datetime.utcfromtimestamp(ux2).strftime('%Y-%m-%d')
	
		
	filename_str = path_str+ "_30day_bars.csv"  	

	#print("create file:", filename_str)	

	try:	
		f = open(str(filename_str), "w")
	except: 
		PrintException()



	getstring=f'https://api.polygon.io/v2/aggs/ticker/{t}/range/1/day/{dt2}/{dt1}?sort=asc&limit=30000&apiKey={polygon}'
	#print(getstring)

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
	
			#print(out)
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

		
	filename = path_str+ "_30day_bars.csv"  	
	#print("open file:", filename)	

	try:

		df = pd.read_csv(filename)
		df.columns = ['ticker', 'unixtime', 'volume', 'vwap', 'open', 'close', 'high', 'low']
		#print(df.head)
		
		start = df.iloc[0,5]
		#print(start)
		
	
		df['change'] = (df['close'] / start )
		
		df.to_csv(filename, header=False, index=False)
	
	except: 
		PrintException()
		pass						



			
con.close()

# 90 DAY

ux = (timestamp - (86400 * 90))  
uxs = str(ux)

ux1 = timestamp

x = 1
xs = str(x)

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='ticker_prices', allow_local_infile=True)


sql = "select distinct symbol from all_assets"
#sql = "select distinct symbol from all_assets where symbol = 'AAPL'"
print(sql)
cursor = con.cursor()
cursor.execute(sql)
result = cursor.fetchall()

for y in result:
	t = (y[0])
	
	symbol = str(t)
	print("Symbol 90days: ",symbol)



	path_str = "/Volumes/ext_drive/get_ticker_data/90_day_bars/" +symbol

	ux1s = str(ux1)

	ux2 = ux 
	ux2s = str(ux2)

	
	dt1 = datetime.utcfromtimestamp(ux1).strftime('%Y-%m-%d')
	dt2 = datetime.utcfromtimestamp(ux2).strftime('%Y-%m-%d')
	
		
	filename_str = path_str+ "_day_bars.csv"  	

	#print("create file:", filename_str)	

	try:	
		f = open(str(filename_str), "w")
	except: 
		PrintException()



	getstring=f'https://api.polygon.io/v2/aggs/ticker/{t}/range/1/day/{dt2}/{dt1}?sort=asc&limit=30000&apiKey={polygon}'
	#print(getstring)

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
	
			#print(out)
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

	filename = path_str+ "_day_bars.csv"  	
	#print("open file:", filename)	

	try:

		df = pd.read_csv(filename)
		df.columns = ['ticker', 'unixtime', 'volume', 'vwap', 'open', 'close', 'high', 'low']
		#print(df.head)
		
		start = df.iloc[0,5]
		#print(start)
		
	
		df['change'] = (df['close'] / start )
		
		df.to_csv(filename, header=False, index=False)
	
	except: 
		PrintException()
		pass						




			
con.close()
		
# 180 Day

ux = (timestamp - (86400 * 180))  
uxs = str(ux)

ux1 = timestamp

x = 1
xs = str(x)

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='ticker_prices', allow_local_infile=True)


sql = "select distinct symbol from all_assets"
#sql = "select distinct symbol from all_assets where symbol = 'AAPL'"
print(sql)
cursor = con.cursor()
cursor.execute(sql)
result = cursor.fetchall()

for y in result:
	t = (y[0])
	
	symbol = str(t)
	print("Symbol: 180days",symbol)



	path_str = "/Volumes/ext_drive/get_ticker_data/180_day_bars/" +symbol

	ux1s = str(ux1)

	ux2 = ux 
	ux2s = str(ux2)

	
	dt1 = datetime.utcfromtimestamp(ux1).strftime('%Y-%m-%d')
	dt2 = datetime.utcfromtimestamp(ux2).strftime('%Y-%m-%d')
	
		
	filename_str = path_str+ "_day_bars.csv"  	

	#print("create file:", filename_str)	

	try:	
		f = open(str(filename_str), "w")
	except: 
		PrintException()



	getstring=f'https://api.polygon.io/v2/aggs/ticker/{t}/range/1/day/{dt2}/{dt1}?sort=asc&limit=30000&apiKey={polygon}'
	#print(getstring)

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
	
			#print(out)
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

	filename = path_str+ "_day_bars.csv"  	
	#print("open file:", filename)	

	try:

		df = pd.read_csv(filename)
		df.columns = ['ticker', 'unixtime', 'volume', 'vwap', 'open', 'close', 'high', 'low']
		#print(df.head)
		
		start = df.iloc[0,5]
		#print(start)
		
	
		df['change'] = (df['close'] / start )
		
		df.to_csv(filename, header=False, index=False)
	
	except: 
		PrintException()
		pass						



			
con.close()

# 5 Years

ux = (timestamp - (86400 * 1500))  
uxs = str(ux)

ux1 = timestamp

x = 1
xs = str(x)

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='ticker_prices', allow_local_infile=True)


sql = "select distinct symbol from all_assets"
#sql = "select distinct symbol from all_assets where symbol = 'AAPL'"
print(sql)
cursor = con.cursor()
cursor.execute(sql)
result = cursor.fetchall()

for y in result:
	t = (y[0])
	
	symbol = str(t)
	print("Symbol-5 Yrs: ",symbol)



	path_str = "/Volumes/ext_drive/get_ticker_data/5_year_bars/" +symbol

	ux1s = str(ux1)

	ux2 = ux 
	ux2s = str(ux2)

	
	dt1 = datetime.utcfromtimestamp(ux1).strftime('%Y-%m-%d')
	dt2 = datetime.utcfromtimestamp(ux2).strftime('%Y-%m-%d')
	
		
	filename_str = path_str+ "_day_bars.csv"  	

	#print("create file:", filename_str)	

	try:	
		f = open(str(filename_str), "w")
	except: 
		PrintException()



	getstring=f'https://api.polygon.io/v2/aggs/ticker/{t}/range/1/day/{dt2}/{dt1}?sort=asc&limit=50000&apiKey={polygon}'
	#print(getstring)

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
	
			#print(out)
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

	filename = path_str+ "_day_bars.csv"  	
	#print("open file:", filename)	

	try:

		df = pd.read_csv(filename)
		df.columns = ['ticker', 'unixtime', 'volume', 'vwap', 'open', 'close', 'high', 'low']
		#print(df.head)
		
		start = df.iloc[0,5]
		#print(start)
		
	
		df['change'] = (df['close'] / start )
		
		df.to_csv(filename, header=False, index=False)
	
	except: 
		PrintException()
		pass						



			
con.close()


quit()


