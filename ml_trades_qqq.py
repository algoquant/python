# f1p dan@flaglerstreettrading.com

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


# prediction variable
keyvar = "changed30"
symbol = 'QQQ'
ticker = symbol
polygon_key = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"


timestamp = int(time.time())
localtime = time.ctime(timestamp)

starttime = time.time()

path = "/Volumes/ext_drive/qqq_data/"
file = "qqq_trainingset.csv"
filename = path + file

df = pd.read_csv(filename)
print(df.head)

final = df[[keyvar,"change1","change10","change30","change60","xavgchange10","xavgchange30","xavgchange60","avgchange10","avgchange30","avgchange60","std10","std30","std60"]]


final = final.fillna(0)


#print("Head: Final",final.head)
#print("Size: Final ",final.size)
#print("Shape Final: ",final.shape)


#print("these are the statistics")

max = final.max()
#print("max :",max)


mean = final.mean()
#print("mean :",mean)


min = final.min()
#print("min :", min)

corr_matrix = final.corr()
cormat = corr_matrix[keyvar].sort_values(ascending=False)
#print("correlation: ",cormat)

#print("mod_final")
mod_final = final.drop(keyvar, axis=1)  # drop labels for training set
#print(mod_final)

#print("final_labels")
final_labels = final[keyvar].copy()
#print(final_labels)

endtime = time.time()
lapsedtime = (endtime - starttime)

print("Time to load data: ",lapsedtime)

#quit()

a = 1


#for a in range(1,10):
for a in range(1,2000):

#for a in range(1,23400):

	from settings import loginf2p, acct_namef2p, keyaf2p, keybf2p


	login = loginf2p
	acct_name = acct_namef2p
	key1 = keyaf2p
	key2 = keybf2p
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



	try:

		timestamp = int(time.time())
		localtime = time.ctime(timestamp)
		
		ux = timestamp
		
#		print(ux)
		print("\n\nCurrent Time: ",localtime)		

	
		starttime = time.time()
	
		#print("get the prediction set")
	
		uxs = str(ux)
		ux1 = (ux -1)
		ux1s = str(ux1)
	


		ticker = symbol
		sym = ticker
		polygon_key = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
		
		

		global map
		
		def remap(map, s): 
			for item,val in map.items():
				if s == item:
					return val['name']
		
		dt = today
		t 	= ticker.upper()
		p 	= polygon_key
		start_unix_time = (ux - 14400)  # tick data from the last hour
		st 	= start_unix_time
		et = ux *1000*1000*1000
		st	= int(st)*1000*1000*1000
		limit = 2000
		
		last_time = st 
		last_price = None
		last_size = None
		index = 0
		
		start = int(st / (1000*1000*1000))
		end = int(et / (1000*1000*1000))
		
		
		localtime1 = time.ctime(start)
		localtime2 = time.ctime(end)
		
		getstring=f'https://api.polygon.io/v2/ticks/stocks/trades/{t}/{dt}?reverse=true&limit={limit}&apiKey={p}&timestamp={last_time}&timestampLimit={et}'
		
		
		#print(getstring)
			
		resp = requests.get(getstring)
		#print(resp)
		
		if resp.status_code != 200:
			# This means something went wrong.
			raise ApiError('GET /historical/ {}'.format(resp.status_code))
		
		r=resp.json()
		
		#print(r)
		
		
		results			= r['results']
		success			= r['success']
		map				= r['map']
		ticker			= r['ticker']
		results_count	= r['results_count']
		db_latency		= r['db_latency']
		
		newresults = []
		df = pd.DataFrame()
		
		for item in results:
			#print(item)
		
			if ("c") not in item:
				item.update({"c" : [0]})
			
		
		#	start - make sure the order is correct so CSV doesn't break!
		
			from collections import OrderedDict
			order_of_keys = ['t','y','q','i','x','s','c','p','z']
			list_of_tuples = [(key, item[key]) for key in order_of_keys]
			od = OrderedDict(list_of_tuples)				
		# 				r = json.loads(json.dumps(od))
			item=dict(od)
			#end - make sure the order is correct so CSV doesn't break!
			
		#	df = pd.DataFrame.from_dict(item, orient="columns")
			df = df.append(item, ignore_index=True)

		
		
		df = df.sort_values('t') 
		#print(df.head)
		print(df.shape)

		df1 = df[["p", "s"]]
		
		#print("Prediction dataframe: ",df1.shape)
		
		# only use rows that have more than  399 shares traded
		df1 = df1[df1["s"] > 399]
		
		#print("Prediction set > 399: ",df1.shape)
		
		
		df1['price'] = df1['p']
		df1['volume_1sec'] = df1['s']
		
		# fill any null values with the previous Value
		df1['price_adj'] = df1['price'].fillna(method='ffill', inplace=True)
		df1['price_adj'] = df1['price'].replace(to_replace=0, method='ffill')
		
		
		# add a column for the price change
		df1['change1'] = df1.price_adj.diff(periods=1)
		df1['change10'] = df1.price_adj.diff(periods=10)
		df1['change30'] = df1.price_adj.diff(periods=30)
		
		#print(df1.head)
		
				
		
		#	print("filter price change errors  from dataset")
		df1 = df1.loc[(df1.change1 <  1) & (df1.change1 >  -1)]
		
		
		
		# fill any null values with 0s
		df1['change1'] = df1.change1.fillna(0)
		df1['change10'] = df1.change10.fillna(0)
		df1['change30'] = df1.change30.fillna(0)
		
		
		df1['change60'] = df1.price_adj.diff(periods=60)
		#		df1['change120'] = df1.price_adj.diff(periods=120)
		#		df1['change300'] = df1.price_adj.diff(periods=300)
		#		df1['change3600'] = df1.price_adj.diff(periods=3600)
		df1['changed1'] = df1.price_adj.diff(periods=-1)
		df1['changed10'] = df1.price_adj.diff(periods=-10)
		df1['changed30'] = df1.price_adj.diff(periods=-30)
		#		df1['changed60'] = df1.price_adj.diff(periods=-60)
		#		df1['changed120'] = df1.price_adj.diff(periods=-120)
		#		df1['changed300'] = df1.price_adj.diff(periods=-300)
		#		df1['changed3600'] = df1.price_adj.diff(periods=-3600)
		
		
		avg10 = df1.price_adj.rolling(window=10).mean()
		avg30 = df1.price_adj.rolling(window=30).mean()
		avg60 = df1.price_adj.rolling(window=60).mean()
		#		avg120 = df1.price_adj.rolling(window=120).mean()
		#		avg300 = df1.price_adj.rolling(window=300).mean()
		#		avg3600 = df1.price_adj.rolling(window=3600).mean()
		#		
		xavg10 = df1.price_adj.ewm(com=10).mean()
		xavg30 = df1.price_adj.ewm(com=30).mean()
		xavg60 = df1.price_adj.ewm(com=60).mean()
		#		xavg120 = df1.price_adj.ewm(com=120).mean()
		#		xavg300 = df1.price_adj.ewm(com=300).mean()
		#		xavg3600 = df1.price_adj.ewm(com=3600).mean()
		#		
		
		std10 = df1.price_adj.rolling(window=10).std()
		std30 = df1.price_adj.rolling(window=30).std()
		std60 = df1.price_adj.rolling(window=60).std()
		#		std120 = df1.price_adj.rolling(window=120).std()
		#		std300 = df1.price_adj.rolling(window=300).std()
		#		std3600 = df1.price_adj.rolling(window=3600).std()
		#		
		df1['avg10'] = avg10
		df1['avg30'] = avg30
		df1['avg60'] = avg60
		#		df1['avg120'] = avg120
		#		df1['avg300'] = avg300
		##		df1['avg3600'] = avg3600
		
		df1['xavg10'] = xavg10
		df1['xavg30'] = xavg30
		df1['xavg60'] = xavg60
		#		df1['xavg120'] = xavg120
		#		df1['xavg300'] = xavg300
		##		df1['xavg3600'] = xavg3600
		#		
		df1['std10'] = std10
		df1['std30'] = std30
		df1['std60'] = std60
		#		df1['std120'] = std120
		#		df1['std300'] = std300
		##		df1['std3600'] = std3600
		#		
		
		
		df1['xavgchange10'] = df1['price_adj'] - df1['xavg10'] 
		df1['xavgchange30'] = df1['price_adj'] - df1['xavg30'] 
		df1['xavgchange60'] = df1['price_adj'] - df1['xavg60'] 
		#		df1['xavgchange120'] = df1['price_adj'] - df1['xavg120'] 
		#		df1['xavgchange300'] = df1['price_adj'] - df1['xavg300'] 
		##		df1['xavgchange3600'] = df1['price_adj'] - df1['xavg3600'] 
		#		
		df1['avgchange10'] = df1['price_adj'] - df1['avg10'] 
		df1['avgchange30'] = df1['price_adj'] - df1['avg30'] 
		df1['avgchange60'] = df1['price_adj'] - df1['avg60'] 
		#		df1['avgchange120'] = df1['price_adj'] - df1['avg120'] 
		#		df1['avgchange300'] = df1['price_adj'] - df1['avg300'] 
		##		df1['avgchange3600'] = df1['price_adj'] - df1['avg3600'] 
		#		
		df1['volindex'] = df1['volume_1sec'] / 1000 
		
#		df1 = df1.fillna(0)
		
		lastrow = df1.tail(1)
		
		price = lastrow.iloc[0]['price_adj']
		prices = str(price)
		print("Price: " ,prices)
		
		predict = lastrow[["change1","change10","change30","change60","xavgchange10","xavgchange30","xavgchange60","avgchange10","avgchange30","avgchange60","std10","std30","std60"]]
		#predict = lastrow[["volindex","change1","change10","change30","change60","change120","change300","xavgchange10","xavgchange30","xavgchange60","xavgchange120","xavgchange300","avgchange10","avgchange30","avgchange60","avgchange120","avgchange300","std10","std30","std60","std120","std300"]]
		
		print(predict)

	
		print("run LR...")				
					
		from sklearn.linear_model import LinearRegression
		lr = LinearRegression()
		lr.fit(mod_final, final_labels)
		results = lr.predict(predict)

		print("Results: ",results[0])
		pr = str(results[0])	
	
		from sklearn.metrics import mean_squared_error
		qqq_predict = lr.predict(mod_final)
		lin_mse = mean_squared_error(final_labels, qqq_predict)
		lin_rmse = np.sqrt(lin_mse)
		print ("RSME :",lin_rmse)

		# -------------------------------------------------------------------
		

		sym = symbol
		qty = 0
		side = ''

		api = tradeapi.REST()
		
		portfolio = api.list_positions()


		# Print the quantity of shares for each position.
		for Position in portfolio:
	
			price = Position.current_price
			symbol = Position.symbol
			qty = int(Position.qty)
			side = Position.side
		
			print("the current position is ",symbol,price,"Qty: ",qty,"Side: ",side)

		# --------------------------------------------

		if (qty > 900):
			ux = int(time.time())		
			uxs = str(ux)

	
			print("too large a long position sell 100 shares")	
			clientid = "COVERLONG" + uxs			

			try:
				api.submit_order(
				symbol=sym,
				qty='100',
				side='sell',
				type='market',
				time_in_force='day',
				client_order_id=clientid)
			except Exception as e:
				pass

		elif (qty < -900):
			ux = int(time.time())		
			uxs = str(ux)

			print("too large a short position. Cover 100 shares")	
			clientid = "COVERSHORT" + uxs			

			qty = (qty * -1) # reverse sign 

			try:
				api.submit_order(
				symbol=sym,
				qty='100',
				side='buy',
				type='market',
				time_in_force='day',
				client_order_id=clientid)
			except Exception as e:
				pass
							
		if (results > 0):

			print("the prediction is positive")
			ux = time.time()
			uxs = str(ux)

			if (qty < 0):

				print("current position is negative so liquidate position")	
				clientid = "COVERLONG" + uxs			

				# because current qty is negative, reserve the sign
				qty = (qty * -1)

				try:
					api.submit_order(
					symbol=sym,
					qty=qty,
					side='buy',
					type='market',
					time_in_force='day',
					client_order_id=clientid)
				except Exception as e:
					pass


				time.sleep(1)
				print("prediction is positive and position sold. Now buy long")	
				clientid = "LONG" + uxs
				try:
					api.submit_order(
					symbol=sym,
					qty=100,
					side='buy',
			#		type='market',
					type='limit',
					limit_price=price,
					time_in_force='ioc',
			#		extended_hours=True,
					client_order_id=clientid)
				except Exception as e:
					pass


			elif (qty > 0):
	
				clientid = "LONG" + uxs			
				print("prediction is positive and current position is positive so buy long")	
				try:
					api.submit_order(
					symbol=sym,
					qty=100,
					side='buy',
					type='limit',
					limit_price=price,
					time_in_force='ioc',
					client_order_id=clientid)
				except Exception as e:
					pass

			else:

				print("current position zero and prediction is positive. buy long")	
				clientid = "LONG" + uxs			

				try:
					api.submit_order(
					symbol=sym,
					qty=100,
					side='buy',
					type='limit',
					limit_price=price,
					time_in_force='ioc',
					client_order_id=clientid)
				except Exception as e:
					pass
			

		# --------------------------------------------
							
		elif (results < 0):

			print("the prediction is negative")
			ux = time.time()
			uxs = str(ux)

			if (qty < 0):

				print("current position is negative so hold and sell more short")
	
				clientid = "SHORT" + uxs	
		
				try:
					api.submit_order(
					symbol=sym,
					qty=100,
					side='sell',
			#		type='market',
					type='limit',
					limit_price=price,
					time_in_force='ioc',
			#		extended_hours=True,
					client_order_id=clientid)
			        
				except Exception as e:
					print("see line 673:"+str(e))
					pass

			elif (qty > 0):

				print("current position is positive so liquidate position")	

				clientid = "COVERLONG" + uxs			
				try:
					api.submit_order(
					symbol=sym,
					qty=qty,
					side='sell',
					type='market',
					time_in_force='day',
					client_order_id=clientid)

				except Exception as e:
					pass
	
				time.sleep(1)
				print("long position sold. Now make short given prediction is negative")

				clientid = "SHORT" + uxs			

				try:
					api.submit_order(
					symbol=sym,
					qty=100,
					side='sell',
					type='limit',
					limit_price=price,
					time_in_force='ioc',
					client_order_id=clientid)
				except Exception as e:
					pass

			else:
				print("position = zero. Make short given prediction is negative")

				clientid = "SHORT" + uxs			

				try:
					api.submit_order(
					symbol=sym,
					qty=100,
					side='sell',
					type='limit',
					limit_price=price,
					time_in_force='ioc',
					client_order_id=clientid)
				except Exception as e:
					pass
				

	
	except:
		pass
	
	time.sleep(1)
		
	a =+ 1

exit()



	
	
