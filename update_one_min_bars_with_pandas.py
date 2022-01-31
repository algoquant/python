import requests
import os
from datetime import datetime, timedelta
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time# as timecode
import sys
import telegram_send
import signal
import argparse
import mysql.connector as connection

global polygon_api_key

pd.set_option('max_rows', 100)

timestamp = int(time.time())
localtime = time.ctime(timestamp)
		
ux = timestamp

starttime = time.time()


# use these lines to load the full file aftre you download it

#filename = "/Volumes/Extreme/algos_ext/one_min_bars.csv"
#
#df = pd.read_csv(filename)
#print(df.head)
#
#df.columns =['symbol','unixtime','volume','vwap','open', 'close', 'high', 'low'] 
#df1 = df[df['symbol'].str.contains('AAPL')]
#
#
#print(df1.head)
#df1.to_csv('aapl_out.csv', index=False)
#
#


# use to load the AAPL bars 

filename = "/Users/danielsavage/algos/aapl_out.csv"
df = pd.read_csv(filename)

#print(df.head)

df = df.sort_values(by=['unixtime'], ascending=True)

#df1 = df["volume"].mean()
#print("Avg Volume: ",df1)

df2 = df[df['symbol'].str.contains('AAPL')]
df2 = df2["volume"].mean()

print("Avg Volume per minute: ",df2)

df3 = pd.concat([df.head(1)])
o = df3.iloc[0]['open']
print("Open: ", o)

df4 = pd.concat([df.tail(1)])
c = df4.iloc[0]['close']
print("Close: ", c)

change = c - o
print("Change: ",change)

pct_change = ((c / o) - 1) * 100
print("Pct Change: ",pct_change)

endtime = time.time()
lapsedtime = (endtime - starttime)

print("Time to load data: ",lapsedtime)



