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

polygon = "UJcr9ctoMBXEBK1Mqu_KQAkUuBxLvEtE" #jolly_bhaskara
#connect to database

#con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='pts', allow_local_infile=True)
global polygon_api_key

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)

starttime = time.time()

ux1 = timestamp
#ux = (ux1 - 86400)


#con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', #host='127.0.0.1', database='ticker_prices', allow_local_infile=True)

filename = "polygon_crypto_pairs.tsv"
f = open(str(filename), "w")


getstring=f'https://api.polygon.io/v3/reference/tickers?market=crypto&active=true&sort=ticker&order=asc&limit=1000&apiKey={polygon}'	
print(getstring)

resp = requests.get(getstring)
print(resp)

r=resp.json()
#print(r)

try:	
	results			= r['results']

except:
	PrintException()
	pass						

#	print(results)


for item in r["results"]:

#	print(item)

	ticker = str(item['ticker'])
	name = str(item['name'])
	t = ticker.replace('USD','-usd')
	t = t.replace('AUD','-aud')
	t = t.replace('EUR','-eur')
	t = t.replace('X:','')
	tl = t.lower()

	out = ticker+ "\t" +name+ "\t" +tl+ "\n"

	try:
		
		print(out)
		f.write(out)
	except: 
		PrintException()
		pass		



exit()


