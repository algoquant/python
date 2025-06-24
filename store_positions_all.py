# this script requires a database for each strategy in order to store the daily orders and positions
# API keys are stored in settings

import requests
import os
import sys
from datetime import datetime, timedelta
from datetime import date
import time
import pandas as pd
import numpy as np
import mysql.connector
import subprocess
import pathlib
import alpaca_trade_api as tradeapi


# print(pd.__version__)
# exit()


timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)

ux = timestamp
uxs = str(ux)


today = date.today()


yesterday = str(today - timedelta(days = 1))
myesterday = str(yesterday)
ydate = myesterday.replace("-","")


mtago = str(today - timedelta(days = 20))
mtago = str(mtago)
#mtago = mtago.replace("-","")

#mdate = "20201203"

mtoday = str(today)
mdate = mtoday.replace("-","")


starttime = time.time()



##connect to database

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', allow_local_infile=True)

# these are the template tables

table9 = "qqq.template_orders_eod"
table10 = "qqq.template_positions_eod"




# ----------------------------------------------------------
#acct: f1p
#dan@flaglerstreettrading.Combine

ticker = 'spy'


table11 = ticker+ ".ML_positions_eod_" +mdate
table12 = ticker+ ".ML_orders_eod_" +mdate

print("table 9",table9)
print("table 10",table10)
print("table 11",table11)
print("table 12",table12)


sql1 = "create table IF NOT EXISTS " +table11+ " like " +table10
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


sql1 = "create table IF NOT EXISTS " +table12+ " like " +table9
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


from settings import loginf1p, acct_namef1p, keyaf1p, keybf1p

login = loginf1p
acct_name = acct_namef1p
key1 = keyaf1p
key2 = keybf1p
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


portfolio = api.list_positions()
#print(portfolio)


# Get the position information from Alpaca.
for Position in portfolio:
	
	price = Position.current_price
	symbol = Position.symbol
	qty = Position.qty
	side = Position.side

	#print(symbol,price,qty,side)
	qtys = str(qty)
	ticker = str(symbol)
	sides = str(side)
	prices = str(price)
	
	sql1 = "replace into " +table11+  " (symbol, price_filled, qty, side) values ('" +ticker+ "', '" +prices+ "', " +qtys+ ", '" +sides+ "')"
	#print(sql1)
	cursor = con.cursor()
	cursor.execute(sql1)
	con.commit()
	cursor.close()


# Get the order information from Alpaca.


try:

	closed_orders = api.list_orders(
		status='closed',
		limit=500
	)	
	
	#print(closed_orders)
	
	for o in closed_orders:

		symbol = str(o.symbol)
		side = str(o.side)
		qty = str(o.qty)
		filled_qty = str(o.filled_qty)
		s_date = str(o.submitted_at)
		c_date = str(o.created_at)
		f_date = str(o.filled_at)
		order_type = str(o.order_type)
		ext_hrs =  str(o.extended_hours)
		tif = str(o.time_in_force)
		other_type = str(o.type)
		status = str(o.status)
		f_price = str(o.filled_avg_price)
		l_price = str(o.filled_avg_price)
		tradeid = o.client_order_id
		alpacaid = str(o.id)

		if (f_price == 'None'):
			f_price = '0'
		if (l_price == 'None'):
			l_price = '0'
			

		sql = "replace into " +table12+ " (symbol, qty,filled_qty,side,date_submitted,date_created,date_filled,order_type,ext_hrs,tif,type,status,price_limit,price_filled,tradeid,order_status) values ('" +symbol+ "','" +qty+ "','" +filled_qty+ "','" +side+ "','" +s_date+ "','" +c_date+ "','" +f_date+ "','" +order_type+  "','" +ext_hrs+  "','" +tif+  "','" +other_type+  "','" +status+  "','" +l_price+  "','" +f_price+  "', '" +tradeid+ "','closed')"  
		#print(sql)
		cursor = con.cursor()
		cursor.execute(sql)
		con.commit()
		cursor.close()
		
except OSError as e:
	pass


# ----------------------------------------------------------
#acct: f2p
#pta1@predictivetradingsystems.com

ticker = 'qqq'


table11 = ticker+ ".ML_positions_eod_" +mdate
table12 = ticker+ ".ML_orders_eod_" +mdate

print("table 9",table9)
print("table 10",table10)
print("table 11",table11)
print("table 12",table12)


sql1 = "create table IF NOT EXISTS " +table11+ " like " +table10
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


sql1 = "create table IF NOT EXISTS " +table12+ " like " +table9
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


from settings import login2fp, acct_name2fp, keya2fp, keyb2fp

login = login2fp
acct_name = acct_name2fp
key1 = keya2fp
key2 = keyb2fp
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


portfolio = api.list_positions()
#print(portfolio)


# Get the position information from Alpaca.
for Position in portfolio:
	
	price = Position.current_price
	symbol = Position.symbol
	qty = Position.qty
	side = Position.side

	#print(symbol,price,qty,side)
	qtys = str(qty)
	ticker = str(symbol)
	sides = str(side)
	prices = str(price)
	
	sql1 = "replace into " +table11+  " (symbol, price_filled, qty, side) values ('" +ticker+ "', '" +prices+ "', " +qtys+ ", '" +sides+ "')"
	#print(sql1)
	cursor = con.cursor()
	cursor.execute(sql1)
	con.commit()
	cursor.close()


# Get the order information from Alpaca.


try:

	closed_orders = api.list_orders(
		status='closed',
		limit=500
	)	
	
	#print(closed_orders)
	
	for o in closed_orders:

		symbol = str(o.symbol)
		side = str(o.side)
		qty = str(o.qty)
		filled_qty = str(o.filled_qty)
		s_date = str(o.submitted_at)
		c_date = str(o.created_at)
		f_date = str(o.filled_at)
		order_type = str(o.order_type)
		ext_hrs =  str(o.extended_hours)
		tif = str(o.time_in_force)
		other_type = str(o.type)
		status = str(o.status)
		f_price = str(o.filled_avg_price)
		l_price = str(o.filled_avg_price)
		tradeid = o.client_order_id
		alpacaid = str(o.id)

		if (f_price == 'None'):
			f_price = '0'
		if (l_price == 'None'):
			l_price = '0'
			

		sql = "replace into " +table12+ " (symbol, qty,filled_qty,side,date_submitted,date_created,date_filled,order_type,ext_hrs,tif,type,status,price_limit,price_filled,tradeid,order_status) values ('" +symbol+ "','" +qty+ "','" +filled_qty+ "','" +side+ "','" +s_date+ "','" +c_date+ "','" +f_date+ "','" +order_type+  "','" +ext_hrs+  "','" +tif+  "','" +other_type+  "','" +status+  "','" +l_price+  "','" +f_price+  "', '" +tradeid+ "','closed')"  
		#print(sql)
		cursor = con.cursor()
		cursor.execute(sql)
		con.commit()
		cursor.close()
		
except OSError as e:
	pass


# ----------------------------------------------------------
#acct: 1p
#pta1@predictivetradingsystems.com


ticker = 'aapl'


table11 = ticker+ ".ML_positions_eod_" +mdate
table12 = ticker+ ".ML_orders_eod_" +mdate

print("table 9",table9)
print("table 10",table10)
print("table 11",table11)
print("table 12",table12)


sql1 = "create table IF NOT EXISTS " +table11+ " like " +table10
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


sql1 = "create table IF NOT EXISTS " +table12+ " like " +table9
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


from settings import login1p, acct_name1p, keya1p, keyb1p

login = login1p
acct_name = acct_name1p
key1 = keya1p
key2 = keyb1p
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


portfolio = api.list_positions()
#print(portfolio)


# Get the position information from Alpaca.
for Position in portfolio:
	
	price = Position.current_price
	symbol = Position.symbol
	qty = Position.qty
	side = Position.side

	#print(symbol,price,qty,side)
	qtys = str(qty)
	ticker = str(symbol)
	sides = str(side)
	prices = str(price)
	
	sql1 = "replace into " +table11+  " (symbol, price_filled, qty, side) values ('" +ticker+ "', '" +prices+ "', " +qtys+ ", '" +sides+ "')"
	#print(sql1)
	cursor = con.cursor()
	cursor.execute(sql1)
	con.commit()
	cursor.close()


# Get the order information from Alpaca.


try:

	closed_orders = api.list_orders(
		status='closed',
		limit=500
	)	
	
	#print(closed_orders)
	
	for o in closed_orders:

		symbol = str(o.symbol)
		side = str(o.side)
		qty = str(o.qty)
		filled_qty = str(o.filled_qty)
		s_date = str(o.submitted_at)
		c_date = str(o.created_at)
		f_date = str(o.filled_at)
		order_type = str(o.order_type)
		ext_hrs =  str(o.extended_hours)
		tif = str(o.time_in_force)
		other_type = str(o.type)
		status = str(o.status)
		f_price = str(o.filled_avg_price)
		l_price = str(o.filled_avg_price)
		tradeid = o.client_order_id
		alpacaid = str(o.id)

		if (f_price == 'None'):
			f_price = '0'
		if (l_price == 'None'):
			l_price = '0'
			

		sql = "replace into " +table12+ " (symbol, qty,filled_qty,side,date_submitted,date_created,date_filled,order_type,ext_hrs,tif,type,status,price_limit,price_filled,tradeid,order_status) values ('" +symbol+ "','" +qty+ "','" +filled_qty+ "','" +side+ "','" +s_date+ "','" +c_date+ "','" +f_date+ "','" +order_type+  "','" +ext_hrs+  "','" +tif+  "','" +other_type+  "','" +status+  "','" +l_price+  "','" +f_price+  "', '" +tradeid+ "','closed')"  
		#print(sql)
		cursor = con.cursor()
		cursor.execute(sql)
		con.commit()
		cursor.close()
		
except OSError as e:
	pass








# ----------------------------------------------------------
#acct: 2p
#pta2@predictivetradingsystems.com


ticker = 'vxx'


table11 = ticker+ ".ML_positions_eod_" +mdate
table12 = ticker+ ".ML_orders_eod_" +mdate

print("table 9",table9)
print("table 10",table10)
print("table 11",table11)
print("table 12",table12)


sql1 = "create table IF NOT EXISTS " +table11+ " like " +table10
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


sql1 = "create table IF NOT EXISTS " +table12+ " like " +table9
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


from settings import login2p, acct_name2p, keya2p, keyb2p

login = login2p
acct_name = acct_name2p
key1 = keya2p
key2 = keyb2p
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


portfolio = api.list_positions()
#print(portfolio)


# Get the position information from Alpaca.
for Position in portfolio:
	
	price = Position.current_price
	symbol = Position.symbol
	qty = Position.qty
	side = Position.side

	#print(symbol,price,qty,side)
	qtys = str(qty)
	ticker = str(symbol)
	sides = str(side)
	prices = str(price)
	
	sql1 = "replace into " +table11+  " (symbol, price_filled, qty, side) values ('" +ticker+ "', '" +prices+ "', " +qtys+ ", '" +sides+ "')"
	#print(sql1)
	cursor = con.cursor()
	cursor.execute(sql1)
	con.commit()
	cursor.close()


# Get the order information from Alpaca.


try:

	closed_orders = api.list_orders(
		status='closed',
		limit=500
	)	
	
	#print(closed_orders)
	
	for o in closed_orders:

		symbol = str(o.symbol)
		side = str(o.side)
		qty = str(o.qty)
		filled_qty = str(o.filled_qty)
		s_date = str(o.submitted_at)
		c_date = str(o.created_at)
		f_date = str(o.filled_at)
		order_type = str(o.order_type)
		ext_hrs =  str(o.extended_hours)
		tif = str(o.time_in_force)
		other_type = str(o.type)
		status = str(o.status)
		f_price = str(o.filled_avg_price)
		l_price = str(o.filled_avg_price)
		tradeid = o.client_order_id
		alpacaid = str(o.id)

		if (f_price == 'None'):
			f_price = '0'
		if (l_price == 'None'):
			l_price = '0'
			

		sql = "replace into " +table12+ " (symbol, qty,filled_qty,side,date_submitted,date_created,date_filled,order_type,ext_hrs,tif,type,status,price_limit,price_filled,tradeid,order_status) values ('" +symbol+ "','" +qty+ "','" +filled_qty+ "','" +side+ "','" +s_date+ "','" +c_date+ "','" +f_date+ "','" +order_type+  "','" +ext_hrs+  "','" +tif+  "','" +other_type+  "','" +status+  "','" +l_price+  "','" +f_price+  "', '" +tradeid+ "','closed')"  
		#print(sql)
		cursor = con.cursor()
		cursor.execute(sql)
		con.commit()
		cursor.close()
		
except OSError as e:
	pass





# ----------------------------------------------------------
#acct: 5p
#pta5@predictivetradingsystems.com
# Buy Dividend stocks 

db = 'dividends'

table11 = db+ ".ML_positions_eod_" +mdate
table12 = db+ ".ML_orders_eod_" +mdate

print("table 9",table9)
print("table 10",table10)
print("table 11",table11)
print("table 12",table12)


sql1 = "create table IF NOT EXISTS " +table11+ " like " +table10
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


sql1 = "create table IF NOT EXISTS " +table12+ " like " +table9
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


from settings import login5p, acct_name5p, keya5p, keyb5p

login = login5p
acct_name = acct_name5p
key1 = keya5p
key2 = keyb5p
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


portfolio = api.list_positions()
#print(portfolio)


# Get the position information from Alpaca.
for Position in portfolio:
	
	price = Position.current_price
	symbol = Position.symbol
	qty = Position.qty
	side = Position.side

	#print(symbol,price,qty,side)
	qtys = str(qty)
	ticker = str(symbol)
	sides = str(side)
	prices = str(price)
	
	sql1 = "replace into " +table11+  " (symbol, price_filled, qty, side) values ('" +ticker+ "', '" +prices+ "', " +qtys+ ", '" +sides+ "')"
	#print(sql1)
	cursor = con.cursor()
	cursor.execute(sql1)
	con.commit()
	cursor.close()


# Get the order information from Alpaca.


try:

	closed_orders = api.list_orders(
		status='closed',
		limit=500
	)	
	
	#print(closed_orders)
	
	for o in closed_orders:

		symbol = str(o.symbol)
		side = str(o.side)
		qty = str(o.qty)
		filled_qty = str(o.filled_qty)
		s_date = str(o.submitted_at)
		c_date = str(o.created_at)
		f_date = str(o.filled_at)
		order_type = str(o.order_type)
		ext_hrs =  str(o.extended_hours)
		tif = str(o.time_in_force)
		other_type = str(o.type)
		status = str(o.status)
		f_price = str(o.filled_avg_price)
		l_price = str(o.filled_avg_price)
		tradeid = o.client_order_id
		alpacaid = str(o.id)

		if (f_price == 'None'):
			f_price = '0'
		if (l_price == 'None'):
			l_price = '0'
			

		sql = "replace into " +table12+ " (symbol, qty,filled_qty,side,date_submitted,date_created,date_filled,order_type,ext_hrs,tif,type,status,price_limit,price_filled,tradeid,order_status) values ('" +symbol+ "','" +qty+ "','" +filled_qty+ "','" +side+ "','" +s_date+ "','" +c_date+ "','" +f_date+ "','" +order_type+  "','" +ext_hrs+  "','" +tif+  "','" +other_type+  "','" +status+  "','" +l_price+  "','" +f_price+  "', '" +tradeid+ "','closed')"  
		#print(sql)
		cursor = con.cursor()
		cursor.execute(sql)
		con.commit()
		cursor.close()
		
except OSError as e:
	pass





# ----------------------------------------------------------
# acct: 4p
# pta4@predictivetradingsystems.com
# Short Top Performers 

db = 'topstocks'

table11 = db+ ".ML_positions_eod_" +mdate
table12 = db+ ".ML_orders_eod_" +mdate

table11 = ticker+ ".ML_positions_eod_" +mdate
table12 = ticker+ ".ML_orders_eod_" +mdate

print("table 9",table9)
print("table 10",table10)
print("table 11",table11)
print("table 12",table12)


sql1 = "create table IF NOT EXISTS " +table11+ " like " +table10
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


sql1 = "create table IF NOT EXISTS " +table12+ " like " +table9
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


from settings import login4p, acct_name4p, keya4p, keyb4p

login = login4p
acct_name = acct_name4p
key1 = keya4p
key2 = keyb4p
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


portfolio = api.list_positions()
#print(portfolio)


# Get the position information from Alpaca.
for Position in portfolio:
	
	price = Position.current_price
	symbol = Position.symbol
	qty = Position.qty
	side = Position.side

	#print(symbol,price,qty,side)
	qtys = str(qty)
	ticker = str(symbol)
	sides = str(side)
	prices = str(price)
	
	sql1 = "replace into " +table11+  " (symbol, price_filled, qty, side) values ('" +ticker+ "', '" +prices+ "', " +qtys+ ", '" +sides+ "')"
	#print(sql1)
	cursor = con.cursor()
	cursor.execute(sql1)
	con.commit()
	cursor.close()


# Get the order information from Alpaca.


try:

	closed_orders = api.list_orders(
		status='closed',
		limit=500
	)	
	
	#print(closed_orders)
	
	for o in closed_orders:

		symbol = str(o.symbol)
		side = str(o.side)
		qty = str(o.qty)
		filled_qty = str(o.filled_qty)
		s_date = str(o.submitted_at)
		c_date = str(o.created_at)
		f_date = str(o.filled_at)
		order_type = str(o.order_type)
		ext_hrs =  str(o.extended_hours)
		tif = str(o.time_in_force)
		other_type = str(o.type)
		status = str(o.status)
		f_price = str(o.filled_avg_price)
		l_price = str(o.filled_avg_price)
		tradeid = o.client_order_id
		alpacaid = str(o.id)

		if (f_price == 'None'):
			f_price = '0'
		if (l_price == 'None'):
			l_price = '0'
			

		sql = "replace into " +table12+ " (symbol, qty,filled_qty,side,date_submitted,date_created,date_filled,order_type,ext_hrs,tif,type,status,price_limit,price_filled,tradeid,order_status) values ('" +symbol+ "','" +qty+ "','" +filled_qty+ "','" +side+ "','" +s_date+ "','" +c_date+ "','" +f_date+ "','" +order_type+  "','" +ext_hrs+  "','" +tif+  "','" +other_type+  "','" +status+  "','" +l_price+  "','" +f_price+  "', '" +tradeid+ "','closed')"  
		#print(sql)
		cursor = con.cursor()
		cursor.execute(sql)
		con.commit()
		cursor.close()
		
except OSError as e:
	pass


# ----------------------------------------------------------
# acct: 13p
# pta13@predictivetradingsystems.com
# Short TSLA 

db = 'short_tsla'

table11 = db+ ".ML_positions_eod_" +mdate
table12 = db+ ".ML_orders_eod_" +mdate

table11 = ticker+ ".ML_positions_eod_" +mdate
table12 = ticker+ ".ML_orders_eod_" +mdate

print("table 9",table9)
print("table 10",table10)
print("table 11",table11)
print("table 12",table12)


sql1 = "create table IF NOT EXISTS " +table11+ " like " +table10
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


sql1 = "create table IF NOT EXISTS " +table12+ " like " +table9
print(sql1)
cursor = con.cursor()
cursor.execute(sql1)
con.commit()
cursor.close()


from settings import login13p, acct_name13p, keya13p, keyb13p

login = login13p
acct_name = acct_name13p
key1 = keya13p
key2 = keyb13p
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


portfolio = api.list_positions()
#print(portfolio)


# Get the position information from Alpaca.
for Position in portfolio:
	
	price = Position.current_price
	symbol = Position.symbol
	qty = Position.qty
	side = Position.side

	#print(symbol,price,qty,side)
	qtys = str(qty)
	ticker = str(symbol)
	sides = str(side)
	prices = str(price)
	
	sql1 = "replace into " +table11+  " (symbol, price_filled, qty, side) values ('" +ticker+ "', '" +prices+ "', " +qtys+ ", '" +sides+ "')"
	#print(sql1)
	cursor = con.cursor()
	cursor.execute(sql1)
	con.commit()
	cursor.close()


# Get the order information from Alpaca.


try:

	closed_orders = api.list_orders(
		status='closed',
		limit=500
	)	
	
	#print(closed_orders)
	
	for o in closed_orders:

		symbol = str(o.symbol)
		side = str(o.side)
		qty = str(o.qty)
		filled_qty = str(o.filled_qty)
		s_date = str(o.submitted_at)
		c_date = str(o.created_at)
		f_date = str(o.filled_at)
		order_type = str(o.order_type)
		ext_hrs =  str(o.extended_hours)
		tif = str(o.time_in_force)
		other_type = str(o.type)
		status = str(o.status)
		f_price = str(o.filled_avg_price)
		l_price = str(o.filled_avg_price)
		tradeid = o.client_order_id
		alpacaid = str(o.id)

		if (f_price == 'None'):
			f_price = '0'
		if (l_price == 'None'):
			l_price = '0'
			

		sql = "replace into " +table12+ " (symbol, qty,filled_qty,side,date_submitted,date_created,date_filled,order_type,ext_hrs,tif,type,status,price_limit,price_filled,tradeid,order_status) values ('" +symbol+ "','" +qty+ "','" +filled_qty+ "','" +side+ "','" +s_date+ "','" +c_date+ "','" +f_date+ "','" +order_type+  "','" +ext_hrs+  "','" +tif+  "','" +other_type+  "','" +status+  "','" +l_price+  "','" +f_price+  "', '" +tradeid+ "','closed')"  
		#print(sql)
		cursor = con.cursor()
		cursor.execute(sql)
		con.commit()
		cursor.close()
		
except OSError as e:
	pass








