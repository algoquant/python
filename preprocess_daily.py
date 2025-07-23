import os
import sys
from datetime import date, datetime, timedelta
import time
import pandas as pd
import numpy as np
import pathlib
import requests
import alpaca_trade_api as tradeapi

# print(pd.__version__)
# exit()
pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 100)


today = date.today()
yesterday = today - timedelta(days = 1)
today = str(today)
mdate = today.replace("-","")
yesterday = str(yesterday)
ydate = yesterday.replace("-","")


timestamp = int(time.time())
localtime = time.ctime(timestamp)

starttime = time.time()


ticker = 'qqq'

#path = "/Volumes/ExtremePro/ml_trading_ext/spy_data/"  # if spy
path = "/Volumes/ext_drive/qqq_data/" # if qqq
#path = "/Volumes/Extreme/aapl_data/" # if aapl
#path = "/Users/danielsavage/public/" # if vxx

filename = "polygon_" +ticker+ "-" +today+ ".csv"

file = path + filename
print(file)
#quit()

df = pd.read_csv(file)
df.columns =['LAST_TIME','size','price'] 
df = df.sort_values('LAST_TIME') 

df['dates'] = pd.to_datetime(df['LAST_TIME'], unit='ns')
df['est'] = (df['dates'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern').dt.strftime("%Y-%m-%d %H:%M:%S"))
df['hours'] = (df['dates'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern').dt.strftime("%H"))
df['mins'] = (df['dates'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern').dt.strftime("%M"))
df['secs'] = (df['dates'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern').dt.strftime("%S"))
df['day'] = (df['dates'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern').dt.strftime("%d"))

df["hours"] = df["hours"].astype(str).astype(int)


# only include rows between 9 AM and 6 pm
#df = df.loc[(df.hours ==  9) & (df.mins ==  0) & (df.secs ==  1)]


df['change1'] = df.price.diff(periods=1)

#df = df.loc[(df.change1 <  1) & (df.change1 >  -1)] # filter any 1 second changes < or > 1

#print(df.head)
#print(df.dtypes)


	# add a column for the price change
df['change1'] = df.price.diff(periods=1)
df['change10'] = df.price.diff(periods=10)
df['change30'] = df.price.diff(periods=30)


print("filter price change errors  from dataset")
#df = df.loc[(df.change1 <  10) & (df.change1 >  -10)]
#df = df.loc[(df.change30 <  10) & (df.change30 >  -10)]

# fill any null values with 0s
df['change1'] = df.change1.fillna(0)
df['change10'] = df.change10.fillna(0)
df['change30'] = df.change30.fillna(0)


df['change60'] = df.price.diff(periods=60)
df['change120'] = df.price.diff(periods=120)
df['change300'] = df.price.diff(periods=300)
df['change3600'] = df.price.diff(periods=3600)
df['changed1'] = df.price.diff(periods=-1)
df['changed10'] = df.price.diff(periods=-10)
df['changed30'] = df.price.diff(periods=-30)
df['changed60'] = df.price.diff(periods=-60)
df['changed120'] = df.price.diff(periods=-120)
df['changed300'] = df.price.diff(periods=-300)
df['changed3600'] = df.price.diff(periods=-3600)

#print("filter likely adj_price change errors from dataset")

df = df.loc[(df.change1 <  1) & (df.change1 > -1) & (df.change10 <  2) & (df.change10 >  -2)  & (df.change10 >  -2)  & (df.change30 <  2) & (df.change30 > -2) & (df.change60 < 2) & (df.change60 > -2) & (df.change120 < 2) & (df.change120 > -2) & (df.change300 <  3) & (df.change300 > -3) & (df.change3600 <  10) & (df.change3600 > -10) & (df.changed1 <  1) & (df.changed1 > -1) & (df.changed10 <  2) & (df.changed10 >  -2)  & (df.changed10 >  -2)  & (df.changed30 <  2) & (df.changed30 > -2) & (df.changed60 < 2) & (df.changed60 > -2) & (df.changed120 < 2) & (df.changed120 > -2) & (df.changed300 <  3) & (df.changed300 > -3) & (df.changed3600 <  10) & (df.changed3600 > -10)]



avg10 = df.price.rolling(window=10).mean()
avg30 = df.price.rolling(window=30).mean()
avg60 = df.price.rolling(window=60).mean()
avg120 = df.price.rolling(window=120).mean()
avg300 = df.price.rolling(window=300).mean()
avg3600 = df.price.rolling(window=3600).mean()

xavg10 = df.price.ewm(com=10).mean()
xavg30 = df.price.ewm(com=30).mean()
xavg60 = df.price.ewm(com=60).mean()
xavg120 = df.price.ewm(com=120).mean()
xavg300 = df.price.ewm(com=300).mean()
xavg3600 = df.price.ewm(com=3600).mean()


std10 = df.price.rolling(window=10).std()
std30 = df.price.rolling(window=30).std()
std60 = df.price.rolling(window=60).std()
std120 = df.price.rolling(window=120).std()
std300 = df.price.rolling(window=300).std()
std3600 = df.price.rolling(window=3600).std()

df['avg10'] = avg10
df['avg30'] = avg30
df['avg60'] = avg60
df['avg120'] = avg120
df['avg300'] = avg300
df['avg3600'] = avg3600

df['xavg10'] = xavg10
df['xavg30'] = xavg30
df['xavg60'] = xavg60
df['xavg120'] = xavg120
df['xavg300'] = xavg300
df['xavg3600'] = xavg3600

df['std10'] = std10
df['std30'] = std30
df['std60'] = std60
df['std120'] = std120
df['std300'] = std300
df['std3600'] = std3600



df['xavgchange10'] = df['price'] - df['xavg10'] 
df['xavgchange30'] = df['price'] - df['xavg30'] 
df['xavgchange60'] = df['price'] - df['xavg60'] 
df['xavgchange120'] = df['price'] - df['xavg120'] 
df['xavgchange300'] = df['price'] - df['xavg300'] 
df['xavgchange3600'] = df['price'] - df['xavg3600'] 

df['avgchange10'] = df['price'] - df['avg10'] 
df['avgchange30'] = df['price'] - df['avg30'] 
df['avgchange60'] = df['price'] - df['avg60'] 
df['avgchange120'] = df['price'] - df['avg120'] 
df['avgchange300'] = df['price'] - df['avg300'] 
df['avgchange3600'] = df['price'] - df['avg3600'] 

df['volume_avg'] = df['size'].mean()
df['volindex'] = df['size'] / 30 

# combine new file with old file 
oldfile = ticker+ "_trainingset.csv"
oldfilename = path + oldfile
print(oldfilename)
df1 = pd.read_csv(oldfilename)

dftemp = [df, df1]
df2 = pd.concat(dftemp)

df2 = df2.sort_values('LAST_TIME') 
#print(df2.head)
#quit()
outfile = ticker+ "_trainingset.csv"
print(outfile)

df2.to_csv(outfile, index=False, header=True)

endtime = time.time()
lapsedtime = (endtime - starttime)

print("Time to load data: ",lapsedtime)

quit()


