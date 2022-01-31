# QQQ    pta2

import os
import sys
from datetime import date, datetime, timedelta
import time
import pandas as pd
import numpy as np
import pathlib
import requests
import alpaca_trade_api as tradeapi

today = date.today()
yesterday = today - timedelta(days = 1)
today = str(today)
mdate = today.replace("-","")

import mysql.connector as sql
from sqlalchemy import create_engine


starttime = time.time()


# Credentials to database connection
hostname="localhost"
dbname="fred"
uname="root"
pwd="waWWii21156!"

# Create SQLAlchemy engine to connect to MySQL Database
engine = create_engine("mysql+pymysql://{user}:{pw}@{host}/{db}"
				.format(host=hostname, db=dbname, user=uname, pw=pwd))

# Convert dataframe to sql table                                   
#df = pd.read_sql('SELECT spy,DFEDTARU,DLTIIT FROM features_daily', con=engine)
#df = pd.read_sql('SELECT * FROM features_daily', con=engine)
df = pd.read_sql('SELECT * FROM features_daily order by date limit 1000,3840', con=engine)

#print(df)

df = df.fillna(0)
df['spy_change'] = df.spy.diff(periods=1)
df['T10YIE_change'] = df.T10YIE.diff(periods=1)
df['T5YIE_change'] = df.T5YIE.diff(periods=1)
df['DGS30_change'] = df.DGS30.diff(periods=1)
df['DGS10_change'] = df.DGS10.diff(periods=1)
df['DGS5_change'] = df.DGS5.diff(periods=1)
df['DGS2_change'] = df.DGS2.diff(periods=1)
df['DTB1YR_change'] = df.DTB1YR.diff(periods=1)
df['DLTIIT_change'] = df.DLTIIT.diff(periods=1)
df['T5YFF_change'] = df.T5YFF.diff(periods=1)
df['DFII5_change'] = df.DFII5.diff(periods=1)
df['BAMLC0A2CAAEY_change'] = df.BAMLC0A2CAAEY.diff(periods=1)
df['BAMLC2A0C35YEY_change'] = df.BAMLC2A0C35YEY.diff(periods=1)
df['BAMLH0A0HYM2EY_change'] = df.BAMLH0A0HYM2EY.diff(periods=1)
df['DFII7_change'] = df.DFII7.diff(periods=1)
df['BAMLC0A0CMEY_change'] = df.BAMLC0A0CMEY.diff(periods=1)
df['BAMLHE00EHYIEY_change'] = df.BAMLHE00EHYIEY.diff(periods=1)

df = df.dropna()
# filter any 1 second changes < or > 10
df = df.loc[(df.spy_change <  10) & (df.spy_change >  -10)] 



keyvar = 'spy_change'
corr_matrix = df.corr()
cormat = corr_matrix[keyvar].sort_values(ascending=False)
print("correlation: ",cormat)

#quit()

login = "loginf2p"
acct_name = "f2p"
key1 = "PKNQB5BEOOXQBU7CXHBF"
key2 = "5rfqQUmLMeCl6xpYHnqYmpla0qcmo7pLzZoLr4Nx"
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


#print(df.head(30))

df1 = (df.tail(1))
#print(df1)

#final = df[["spy_change","T10YIE_change","DFEDTARU","IOER","DFEDTARL","DTB1YR","BAMLC1A0C13YEY","DGS10","DGS30","DFII5","BAMLC0A2CAAEY","BAMLC2A0C35YEY","BAMLH0A0HYM2EY","DFII7","BAMLC0A0CMEY","BAMLHE00EHYIEY","DLTIIT"]]
#final = df[["spy","DFEDTARU","DLTIIT"]]

final = df[["spy_change","T10YIE_change","T5YIE_change","DGS30_change","DGS10_change","DGS5_change","DGS2_change","DTB1YR_change","DLTIIT_change","T5YFF_change","DFII5_change","BAMLC0A2CAAEY_change","BAMLC2A0C35YEY_change","BAMLH0A0HYM2EY_change","DFII7_change","BAMLC0A0CMEY_change","BAMLHE00EHYIEY_change"]]

df.to_csv('bonds_to_spy.csv')

# delete rows with 0 in the spy column
#final = final[final.spy != 0]

#drop last row 
final = final.head(final.shape[0] -1)

#predict= df1[["DFEDTARU","IOER","DFEDTARL","DTB1YR","BAMLC1A0C13YEY","DGS10","DGS30","DFII5","BAMLC0A2CAAEY","BAMLC2A0C35YEY","BAMLH0A0HYM2EY","DFII7","BAMLC0A0CMEY","BAMLHE00EHYIEY","DLTIIT"]]
#predict = df1[["DFEDTARU","DLTIIT"]]
predict = df1[["T10YIE_change","T5YIE_change","DGS30_change","DGS10_change","DGS5_change","DGS2_change","DTB1YR_change","DLTIIT_change","T5YFF_change","DFII5_change","BAMLC0A2CAAEY_change","BAMLC2A0C35YEY_change","BAMLH0A0HYM2EY_change","DFII7_change","BAMLC0A0CMEY_change","BAMLHE00EHYIEY_change"]]





mod_final = final.drop(keyvar, axis=1)  # drop labels for training set
final_labels = final[keyvar].copy()

#print(final)
#print(predict)


#print("run LR...")				
#			
#from sklearn.linear_model import LinearRegression
#lr = LinearRegression()
#lr.fit(mod_final, final_labels)
#results = lr.predict(predict)
#
#print("Results: ",results[0])
#pr = str(results[0])	
#
#from sklearn.metrics import mean_squared_error
#qqq_predict = lr.predict(mod_final)
#lin_mse = mean_squared_error(final_labels, qqq_predict)
#lin_rmse = np.sqrt(lin_mse)
#print ("RSME :",lin_rmse)
#
#			
	
from sklearn.ensemble import RandomForestRegressor
forest_reg = RandomForestRegressor(n_estimators=1000, max_depth=20, random_state=42, n_jobs=-1)
forest_reg.fit(mod_final, final_labels)
results = forest_reg.predict(predict)
print("RF Predicted price change (SPY) tomorrow:: ",results[0])

prediction = results[0]	
print("Prediction: ",prediction)
		
from sklearn.metrics import mean_squared_error
predict = forest_reg.predict(mod_final)
rf_mse = mean_squared_error(final_labels, predict)
rf_rmse = np.sqrt(rf_mse)
print ("RSME :",rf_mse)

tss = 'SPY'


quit()

getstring = "https://api.polygon.io/v1/last/stocks/" +tss+ "?&apiKey=jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
#print(getstring)

resp = requests.get(getstring)
#print(resp)

r=resp.json()
#print(r)


last = r['last']
for item in last:
	price = (last["price"])

p = str(price)
#print(p)


#qty = int((10000 / price) )
#qtys = str(qty)

			
ux = time.time()
ux = round(ux)
uxs = str(ux)

clientid = "SHORT_" +tss+ "_" +uxs
clientid = str(clientid)


api = tradeapi.REST()

if (prediction > 0):

	try:
		print("Buy 100 shares of SPY at ",price)
		clientid = "LONG_" +tss+ "_" +uxs
		clientid = str(clientid)

		api.submit_order(
		symbol=tss,
		qty=100,
		side='buy',
		type='limit',
		limit_price=price,
		time_in_force='day',
		extended_hours=True,
		client_order_id=clientid)
	except Exception as e:
		#print(+str(e))
		pass	
else:

	try:
		clientid = "SHORT_" +tss+ "_" +uxs
		clientid = str(clientid)

		print("Sell 100 shares of SPY at ",price)

		api.submit_order(
		symbol=tss,
		qty=100,
		side='sell',
		type='limit',
		limit_price=price,
		time_in_force='day',
		extended_hours=True,
		client_order_id=clientid)
	except Exception as e:
		#print(+str(e))
		pass	




endtime = time.time()
lapsedtime = (endtime - starttime)
print("Time to load data: ",lapsedtime)

