Note: This script does not run. DO NOT USE!

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
from urllib import parse


def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f_err = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f_err.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f_err.f_globals)
    print ('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))

polygon = "UJcr9ctoMBXEBK1Mqu_KQAkUuBxLvEtE" #jolly_bhaskara
apiKey = "&apiKey="
key = apiKey + polygon
#connect to database

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='ticker_prices', allow_local_infile=True)
global polygon_api_key

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)

starttime = time.time()

ux1 = timestamp
#ux = (ux1 - 86400)


#con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', #host='127.0.0.1', database='ticker_prices', allow_local_infile=True)

filename = "polygon_tickers.csv"
f = open(str(filename), "w")

count = 0
oldcursor = None
cursor = None
getstring=f'https://api.polygon.io/v3/reference/tickers?market=stocks&active=true&sort=ticker&order=asc&limit=50000{key}'	
print(getstring)

while getstring is not None:
	resp = requests.get(getstring)
	print(resp)

	r=resp.json()
# 	print(r)

	try:	
		results		= r['results']
		url 		= r['next_url']
		getstring=f'{url}{key}'	
		

		ticker = str(item['ticker'])
		name = str(item['name'])
		market = str(item['market'])		
		locale = str(item['locale'])		
		primary_exchange = str(item['primary_exchange'])		
#			type = str(item['type'])		
		active = str(item['active'])		
		currency_name = str(item['currency_name'])		
#			cik = str(item['cik'])		
#			composite_figi = str(item['composite_figi'])		
#			share_class_figi = str(item['share_class_figi'])		

		name = name.replace("'","")

		out = ticker+ "\t" +name+ "\n"


	
		try:
			
		#	print(out)
			f.write(out)

			sql = "replace into polygon_tickers (ticker,name,market,locale,primary_exchange,active,currency_name) values ('" +ticker+ "','" +name+ "','" +market+ "','" +locale+ "','" +primary_exchange+ "','" +active+ "','" +currency_name+ "')"
	#			sql = "replace into polygon_tickers (ticker,name,market,locale,primary_exchange,type,active,currency_name,cik,composite_figi,share_class_figi) values ('" +ticker+ "','" +name+ "','" +market+ "','" +locale+ "','" +primary_exchange+ "','" +type+ "','" +active+ "','" +currency_name+ "','" +cik+ "','" +composite_figi+ "','" +share_class_figi+ "')"
			
			print(sql)
			cursor = con.cursor()
			cursor.execute(sql)
			con.commit()
			cursor.close()
	
		except: 
			PrintException()
			pass		

	except:
		PrintException()
		getstring = None
		pass						





#
#	for item in r["results"]:
#
#		print(count)
#		print(item)
#		count += 1
#		ticker = str(item['ticker'])
#		name = str(item['name'])
#
#		out = ticker+ "\t" +name+ "\n"
#
#		try:
#		
#		#	print(out)
#			f.write(out)
#		except: 
#			PrintException()
#			pass		
#
#

	
f.close()

exit()


