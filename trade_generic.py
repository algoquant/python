# This file is a generic trading script for Alpaca
# It was cloned from C:\Develop\predictive\news-nlp\trade_on_daily_sentiment.py

# this use the stocknewsapi news

import requests
import os
import pandas as pd

import time
import datetime
from datetime import date
from datetime import datetime
from datetime import timedelta
import sys
import traceback
import inspect
import numpy as np

import alpaca_trade_api as tradeapi

ticker = 'SPY'
sym = ticker
polygon_key = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"


timestamp = int(time.time())
localtime = time.ctime(timestamp)
day = localtime[0:3]
print("Local time:", localtime)

today = date.today()
print(today)

ux = timestamp


if (day == 'Mon'):
	yesterday = str(today - timedelta(days = 3))
	myesterday = str(yesterday)
	ydate = myesterday.replace("-","")
	ux1 = ux - 86400*3
else:
	yesterday = str(today - timedelta(days = 1))
	myesterday = str(yesterday)
	ydate = myesterday.replace("-","")
	ux1 = ux - 86400


lt = time.ctime(ux1)
print(lt)

ux2 = ux1 * 1000
uxs2 = str(ux2)

mtoday = str(today)
mdate = mtoday.replace("-","")
print(mdate, ydate)



import mysql.connector as connection
try:
    mydb = connection.connect(host="localhost", database = 'news',user="root", passwd="waWWii21156!",use_pure=True)
    query = "Select ticker,unixtime,volume,vwap,open,close,high,low,date,avg_sentiment,short_date from one_hour_bars_spy where unixtime < " +uxs2+ ";"
    df = pd.read_sql(query,mydb)
    mydb.close() #close the connection
except Exception as e:
    mydb.close()
    print(str(e)) 
print(query)

df['hr'] = df['short_date'].str.slice(11,13)
print(df.head)



# limit data set to one hour bars where hour of the day is 6 pm
df = df[df['hr'] == '18']

#df = df.dropna()

print(df.head)

df = df.sort_values('unixtime') 
df['avg_sentiment'] = pd.to_numeric(df['avg_sentiment'],errors = 'coerce')
df['price_change'] = df.open.diff(periods=1)
df['pct_price_change'] = df['price_change'] / df['close']  
df['avg_volume'] = df.volume.mean()
df['volume_index'] = df['volume'] / df['avg_volume']  
df['open_close_spread'] = df['open'] / df['close']  
df['high_low_spread'] = df['high'] / df['low']  

avg10 = df.avg_sentiment.rolling(window=10).mean()
avg30 = df.avg_sentiment.rolling(window=30).mean()
avg60 = df.avg_sentiment.rolling(window=60).mean()
avg120 = df.avg_sentiment.rolling(window=120).mean()
xavg10 = df.avg_sentiment.ewm(com=10).mean()
xavg30 = df.avg_sentiment.ewm(com=30).mean()
xavg60 = df.avg_sentiment.ewm(com=60).mean()
xavg120 = df.avg_sentiment.ewm(com=120).mean()

df['sent_avg10'] = avg10
df['sent_avg30'] = avg30
df['sent_avg60'] = avg60
df['sent_avg120'] = avg120

df['sent_xavg10'] = xavg10
df['sent_xavg30'] = xavg30
df['sent_xavg60'] = xavg60
df['sent_xavg120'] = xavg120


#print(df.head)
#print(df.dtypes)

#print("these are the statistics")

max = df.max()
#print("max :",max)


mean = df.mean()
#print("mean :",mean)


min = df.min()
#print("min :", min)

corr_matrix = df.corr()
cormat = corr_matrix['price_change'].sort_values(ascending=False)
#print("correlation: ",cormat)


# -----------------------------------------------------------

# prepare prediction set

import mysql.connector as connection
try:
    mydb = connection.connect(host="localhost", database = 'news',user="root", passwd="waWWii21156!",use_pure=True)
    query1 = "Select ticker,unixtime,volume,vwap,open,close,high,low,date,avg_sentiment,short_date from one_hour_bars_spy where unixtime > " +uxs2+ ";"
    df1 = pd.read_sql(query1,mydb)
    mydb.close() #close the connection
except Exception as e:
    mydb.close()
    print(str(e)) 
print(query1)

df1 = df1.sort_values('unixtime') 
df1['avg_sentiment'] = pd.to_numeric(df1['avg_sentiment'],errors = 'coerce')
df1['price_change'] = df1.open.diff(periods=1)
df1['pct_price_change'] = df1['price_change'] / df1['close']  
df1['avg_volume'] = df1.volume.mean()
df1['volume_index'] = df1['volume'] / df1['avg_volume']  

avg10 = df1.avg_sentiment.rolling(window=10).mean()
avg30 = df1.avg_sentiment.rolling(window=30).mean()
avg60 = df1.avg_sentiment.rolling(window=60).mean()
avg120 = df1.avg_sentiment.rolling(window=60).mean()
xavg10 = df1.avg_sentiment.ewm(com=10).mean()
xavg30 = df1.avg_sentiment.ewm(com=30).mean()
xavg60 = df1.avg_sentiment.ewm(com=30).mean()
xavg120 = df1.avg_sentiment.ewm(com=30).mean()

df1['avg10'] = avg10
df1['avg30'] = avg30
df1['avg60'] = avg60
df1['avg120'] = avg60

df1['xavg10'] = xavg10
df1['xavg30'] = xavg30
df1['xavg60'] = xavg60
df1['avg120'] = avg60

#print(df1.head)
#print(df1.dtypes)

train_df = df[['price_change', 'volume_index','avg_sentiment','open_close_spread','unixtime','sent_xavg30']]
predict_df = df[['volume_index','avg_sentiment','open_close_spread','unixtime','sent_xavg30']]

# ---------------------------------------------------------------
train_df = train_df.dropna()

print(df.shape)
print(df1.shape)


X = train_df.drop("price_change", axis=1)  # drop labels for training set
print("X")
print(X)

y = train_df["price_change"].copy()
print("y")
print(y)


lastrow = predict_df.tail(1)
print("lastrow")
print(lastrow)

			
#from sklearn.linear_model import LinearRegression
#lr = LinearRegression()
#lr.fit(X, y)
#results = lr.predict(predict)
#
#print("Predicted price change (SPY) tomorrow:: ",results[0])
#price = str(results[0])	
#
#from sklearn.metrics import mean_squared_error
#spy_predict = lr.predict(X)
#lin_mse = mean_squared_error(y, spy_predict)
#lin_rmse = np.sqrt(lin_mse)
#print ("RSME :",lin_rmse)
#

				
from sklearn.ensemble import RandomForestRegressor
forest_reg = RandomForestRegressor(n_estimators=1000, max_depth=20, random_state=42, n_jobs=-1)
forest_reg.fit(X, y)
results = forest_reg.predict(lastrow)
print("RF Predicted price change (SPY) tomorrow:: ",results[0])

prediction = results[0]	
print("Prediction: ",prediction)
		
from sklearn.metrics import mean_squared_error
predict = forest_reg.predict(X)
rf_mse = mean_squared_error(y, predict)
rf_rmse = np.sqrt(rf_mse)
print ("RSME :",rf_mse)

#quit()

# ----------------------------------------------------------------

# get current price of SPY from Polygon

global map

def remap(map, s): 
	for item,val in map.items():
		if s == item:
			return val['name']

ux = timestamp
uxs = str(ux)
dt = today
t 	= ticker.upper()
p 	= polygon_key
start_unix_time = (ux - 3600)  # tick data from the last hour
st 	= start_unix_time
et = ux *1000*1000*1000
st	= int(st)*1000*1000*1000
limit = 1

last_time = st 
last_price = None
last_size = None
index = 0

start = int(st / (1000*1000*1000))
end = int(et / (1000*1000*1000))


getstring=f'https://api.polygon.io/v2/ticks/stocks/trades/{t}/{dt}?reverse=true&limit={limit}&apiKey={p}&timestamp={last_time}&timestampLimit={et}'
print(getstring)


resp = requests.get(getstring)
print(resp)

r=resp.json()
#print(r)


results			= r['results']

newresults = []
df = pd.DataFrame()

for item in results:
	#print(item)
	

	if ("c") not in item:
		item.update({"c" : [0]})
		print("item updated")
		#print(item)

#	start - make sure the order is correct so CSV doesn't break!

	from collections import OrderedDict
	order_of_keys = ['t','y','q','i','x','s','c','p','z']
	list_of_tuples = [(key, item[key]) for key in order_of_keys]
	od = OrderedDict(list_of_tuples)				
# 				r = json.loads(json.dumps(od))
	item=dict(od)
	
	df = df.append(item, ignore_index=True)


#print(df.head)
df1 = df[["p", "s", "t"]]
df1['dates'] = pd.to_datetime(df1['t'], unit='ns')
df1['est'] = (df1['dates'].dt.tz_localize('UTC').dt.tz_convert('US/Eastern').dt.strftime("%Y-%m-%d %H:%M:%S"))


print(df1)
price = str(df1['p'])

lastrow = df1.tail(1)
price = lastrow.iloc[0]['p']
prices = str(price)
print("Price: " ,prices)

# ---------------------------------------------------------------------------------


from settings import login3p, acct_name3p, keya3p, keyb3p

login = login3p
acct_name = acct_name3p
key1 = keya3p
key2 = keyb3p
endpoint = "https://paper-api.alpaca.markets"


print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

api = tradeapi.REST()

tss = 'SPY'


# close all open orders

api.cancel_all_orders()

# Get the last 500 of our closed orders
closed_orders = api.list_orders(
    status='open',
    limit=500,
    #/nested=True  # show nested multi-leg orders
)

#print(closed_orders)


# show current positions
		
portfolio = api.list_positions()
qty = 0

# Print the quantity of shares for each position.

for Position in portfolio:
	
	price = Position.current_price
	symbol = Position.symbol
	qty = int(Position.qty)
	side = Position.side
	gain = Position.unrealized_intraday_plpc

	qtys = str(qty)
	symbol = str(symbol)	
	print("the current position is ",symbol,"Current price: ", price,"Qty: ",qty,"Side: ",side)

print("checking current sentiment... the sentiment is ", prediction)

if (prediction > 0):
	print("the current sentiment is positive, Check current position...")
	ux = int(time.time())
	uxs = str(ux)
	clientid = "LONGBUY_SPY_" +uxs

	if (qty > 0):
		print("the current position is: ",qtys)
		print("do nothing.  hold position.")

	elif (qty < 0):
		
		print("the current position is: ",qtys)
		print("liquidate current position")

		qty = qty * -1 #reverse sign of qty

		try:
			api.submit_order(
			symbol=tss,
			qty=qty,
			side='buy',
			type='limit',
	#		type = 'market',
			limit_price=prices,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
		except Exception as e:
			pass	

		time.sleep(1)

		print("make a long order for 1000 shares")


		try:
			api.submit_order(
			symbol=tss,
			qty='1000',
			side='buy',
			type='limit',
	#		type = 'market',
			limit_price=prices,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
		except Exception as e:
			pass	

	else:

		print("make a long order for 1000 shares")


		try:
			api.submit_order(
			symbol=tss,
			qty='1000',
			side='buy',
			type='limit',
	#		type = 'market',
			limit_price=prices,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
		except Exception as e:
			pass	

else:
	print("the current sentiment is negative, Check current position...")
	ux = int(time.time())
	uxs = str(ux)
	clientid = "LONGBUY_SPY_" +uxs

	if (qty < 0):
		print("the current position is: ",qtys)
		# do nothing.  hold position.

	elif (qty > 0):
		
		print("the current position is: ",qtys)
		print("liquidate current position")


		try:
			api.submit_order(
			symbol=tss,
			qty=qty,
			side='sell',
			type='limit',
	#		type = 'market',
			limit_price=prices,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
		except Exception as e:
			pass	

		time.sleep(1)

		print("make a long order for 1000 shares")


		try:
			api.submit_order(
			symbol=tss,
			qty='1000',
			side='sell',
			type='limit',
	#		type = 'market',
			limit_price=prices,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
		except Exception as e:
			pass	

	else:

		print("make a shorr order for 1000 shares")


		try:
			api.submit_order(
			symbol=tss,
			qty='1000',
			side='sell',
			type='limit',
	#		type = 'market',
			limit_price=prices,
			time_in_force='day',
			extended_hours=True,
			client_order_id=clientid)
		except Exception as e:
			pass	
		
					
		
quit()

