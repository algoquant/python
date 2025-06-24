import datetime
import time
import mysql.connector
import sys, os
import inspect
import pandas as pd

ticker = 'VZ'

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='news')

#from datetime import date, timedelta
#today = date.today()
#yesterday = today - timedelta(days = 1)

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)

#print(timestamp)
#print(today)
#today = str(today)
#mtoday = today.replace("-","")
#print(mtoday)


path1 = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
dayfile = path1 + "/polygon_vz-2021-01-08.csv"  
df = pd.read_csv(dayfile)

# add column headers
df.columns =['unixtime','volume','price'] 

df['dates'] = pd.to_datetime(df['unixtime'], unit='ns')
df['est'] = (df['dates'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern').dt.strftime("%Y-%m-%d %H:%M:%S"))
df_sell = df.loc[(df.unixtime >  1610024667819480000) & (df.unixtime <  1610029796095100000)]

print(df_sell.head)
df_sell.to_csv('vz_price_drop.csv', mode = 'w') 


df_buy = df.loc[(df.unixtime >  1610132496172170000) & (df.unixtime <  (1610153973200316928))]
print(df_sell.head)
df_buy.to_csv('vz_price_recovery.csv', mode = 'w') 
