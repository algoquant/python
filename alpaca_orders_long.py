#this gets orders from the long account

import datetime
import time as timecode
import mysql.connector
#from ib_insync import *
#from ib_insync.util import isNan
import sys, os
import asyncio
import telegram_send
import signal
import argparse
import alpaca_trade_api as tradeapi
import json

os.environ["APCA_API_BASE_URL"] = "https://api.alpaca.markets"
os.environ["APCA_API_KEY_ID"] = "AK5OZV124UWMDMV9J7IB"
os.environ["APCA_API_SECRET_KEY"] = "G6uzrT4LobJdSRUWEaT33PArhH5GhmAMVxwi7iwx"


global ticker
global tick_type
global future_ticker

#start timing loop for JUST logging
starttime = timecode.time()

ticker			= "qqq" #default

#new CLI parsing:
def as_date(string):
	#if "NOW" entered, set to current date.
	if string == None:
		return None
	if string == "NOW":
		string = datetime.datetime.now().date()
		string = string.strftime("%Y%m%d")

	try:
		#print(string)
#		string = string.to_datetime()	#date()	#
		string = string.strftime("%Y-%m-%d %H:%M:%S")
		value = datetime.datetime.strptime(string, '%Y-%m-%d %H:%M:%S')# %H:%M:%S')
	except:
		msg = "%s is not a date" % string
		raise argparse.ArgumentTypeError(msg)
	return value
	

def writeData(order):
	#print("\n order in writeData:",order)
	cursor = con.cursor()
	# Create a new record
	asset_id			= order.asset_id
	canceled_at			= order.canceled_at
	client_order_id 	= order.client_order_id
	created_at			= order.created_at #timestamp
	expired_at			= order.expired_at #timestamp
	extended_hours		= order.extended_hours
	failed_at			= order.failed_at #timestamp
	filled_at			= order.filled_at #timestamp
	filled_avg_price	= order.filled_avg_price
	filled_qty			= order.filled_qty
	id					= order.id
	legs				= order.legs
	limit_price			= order.limit_price
	order_type			= order.order_type
	qty					= order.qty
	replaced_at			= order.replaced_at #timestamp
	replaced_by			= order.replaced_by
	replaces			= order.replaces
	side				= order.side
	status				= order.status
	stop_price			= order.stop_price
	submitted_at		= order.submitted_at #timestamp
	symbol				= order.symbol
	time_in_force		= order.time_in_force
	type				= order.type
	updated_at			= order.updated_at #timestamp

	try:
		# Create a new record
		cursor = con.cursor()
		sql = "INSERT INTO `orders_long_"+ticker+"` (`asset_id`, `canceled_at`, `client_order_id`, `created_at`, `expired_at`, `extended_hours`, `failed_at`, `filled_at`, `filled_avg_price`, `filled_qty`, `id`, `legs`, `limit_price`, `order_type`, `qty`, `replaced_at`, `replaced_by`, `replaces`, `side`, `status`, `stop_price`, `submitted_at`, `symbol`, `time_in_force`, `type`, `updated_at`) VALUES (%s, %s, %s, %s, %s,%s, %s, %s, %s, %s,%s, %s, %s, %s, %s,%s, %s, %s, %s, %s,%s, %s, %s, %s, %s,%s)"
		
		data = (asset_id, as_date(canceled_at), client_order_id, as_date(created_at), as_date(expired_at), extended_hours, as_date(failed_at), as_date(filled_at), filled_avg_price, filled_qty, id, legs, limit_price, order_type, qty, as_date(replaced_at), replaced_by, replaces, side, status, stop_price, as_date(submitted_at), symbol, time_in_force, type, as_date(updated_at))
		print ("sql:", (sql, data))
		print(created_at)
		cursor.execute(sql, data)
		id = cursor.lastrowid
		#print (id)
		con.commit()
		cursor.close()
		#index += 1
	except mysql.connector.Error as e:
		print("skipped on errors:",e)
	finally:
		print ("inserted")

tDelta = datetime.timedelta(days=1)
parser = argparse.ArgumentParser(description='Parameters for alpaca order download script.')
parser.add_argument('--ticker',	 metavar="ticker", help='Ticker symbol', default='qqq', required=False)

args = parser.parse_args()


#connect to database, but create database if not found
try:
#	con = mysql.connector.connect(user='maxuser', password='waWWii21156!', host='35.231.41.51', database=ticker)
	con = mydb = mysql.connector.connect(user='root', password='2908855Ds', host='127.0.0.1', database=ticker)
except Exception as e:
	print("Timeout:",getattr(e, 'message', repr(e)))
	con = mysql.connector.connect(user='maxuser', password='waWWii21156!', host='35.231.41.51', database=ticker)
#	con = mydb = mysql.connector.connect(user='root', password='2908855Ds', host='127.0.0.1', database=ticker)
	mycursor = con.cursor()
	mycursor.execute("SHOW DATABASES")
	found = False
	for x in mycursor:
		print("testing ",x)
		if x == ticker:
			print("found ",x)
			found = True
			break
	if (found == False):
		mycursor = con.cursor()
		mycursor.execute("CREATE DATABASE "+ticker)
		con.close()
		try:
			con = mysql.connector.connect(user='maxuser', password='waWWii21156!', host='35.231.41.51', database=ticker)	
#			con = mydb = mysql.connector.connect(user='root', password='2908855Ds', host='127.0.0.1', database=ticker)
		except Exception as ee:
			print("Timeout:",getattr(ee, 'message', repr(ee)))
			
print ("Script running ticker:"+ticker)

#create table if it doesn't exist:
try:
	cursor = con.cursor()
	cursor.execute('''
		CREATE TABLE IF NOT EXISTS `orders_long_'''+ticker+'''` (
		`asset_id` char(40) DEFAULT NULL,
		`canceled_at` char(30) DEFAULT NULL,
		`client_order_id` char(40) DEFAULT NULL,
		`created_at` char(30) DEFAULT NULL,
		`expired_at` char(30) DEFAULT NULL,
		`extended_hours` char(6) DEFAULT NULL,
		`failed_at` char(30) DEFAULT NULL,
		`filled_at` char(30) DEFAULT NULL,
		`filled_avg_price` float DEFAULT NULL,
		`filled_qty` int(11) DEFAULT NULL,
		`id` char(40) DEFAULT NULL,
		`legs` char(6) DEFAULT NULL,
		`limit_price` float DEFAULT NULL,
		`order_type` char(10) DEFAULT NULL,
		`qty` int(11) DEFAULT NULL,
		`replaced_at` char(40) DEFAULT NULL,
		`replaced_by` char(40) DEFAULT NULL,
		`replaces` char(40) DEFAULT NULL,
		`side` char(5) DEFAULT NULL,
		`status` char(10) DEFAULT NULL,
		`stop_price` float DEFAULT NULL,
		`submitted_at` char(40) DEFAULT NULL,
		`symbol` char(10) DEFAULT NULL,
		`time_in_force` char(40) DEFAULT NULL,
		`type` char(10) DEFAULT NULL,
		`updated_at` char(40) DEFAULT NULL,
		`LAST_TIME` int(11) NOT NULL default 0,
		`ts` timestamp NOT NULL DEFAULT current_timestamp(),
		`prediction_ux` int(11) NOT NULL default 0,
		`transaction_id` int(11) NOT NULL default 0,
		`local_time` CHAR(30) DEFAULT NULL,
		`base_price` float DEFAULT NULL,
		`predicted_price` float DEFAULT NULL,
		`actual_price` float DEFAULT NULL,
		`var_base_price` float DEFAULT NULL,
		`trade_profit` float DEFAULT NULL,
		`sold_avg_price` float DEFAULT NULL,
		KEY `ts` (`ts`),
		KEY `LAST_TIME` (`LAST_TIME`)
		) ENGINE=InnoDB DEFAULT CHARSET=utf8;
	''')
	print("table created successfully")
	con.commit()
	cursor.close()
except: 
	print("table create failed")
finally:
	print("table maker done.")
try:

	cursor = con.cursor()
	cursor.execute('''
	CREATE TRIGGER `toDateTimeHistNew` BEFORE INSERT ON `'''+ticker+'''_hist_new` 
	FOR EACH ROW  
	set new.ts=from_unixtime(new.LAST_TIME);
	''')
	print("trigger created successfully")
	con.commit()
	cursor.close()

except: 
	print("trigger create failed")
finally:
	print("trigger maker done.")
	
# error handlers for historical data - start
# def onError(reqId, errorCode, errorString,contract):
#	  look at errorCode to see if warning or error
#	from io import StringIO
#	buf = StringIO()
#	buf.write('Mkt Index Data '+ticker+' script Error:')
#	buf.write("reqId:"+str(reqId))
#	buf.write("errorCode:"+str(errorCode))
#	buf.write("errorString:"+str(errorString))
#	sendtext = buf.getvalue()
#	print(sendtext)
#	if errorCode not in [2106]:
#		telegram_send.send(conf="/etc/telegram-send.conf",messages=[sendtext])
#		ib.disconnect()	   
#		end timing loop for JUST logging
#		endtime = timecode.time()
#		print("script time:",endtime - starttime, "seconds.")
#		exit()
#		
# ib.errorEvent += onError	  
# error handlers for historical data - done

def signint_handler(a, b):	# define the handler  
	#print("Signal Number:", a, " Frame: ", b)	
	print ('Program termination - CTRL+C clean.')
	ib.disconnect()	   
	#end timing loop for JUST logging
	endtime = timecode.time()
	print("script time:",endtime - starttime, "seconds.")
	exit()
  
signal.signal(signal.SIGINT, signint_handler)  # assign the handler to the signal SIGINT  
#error handlers for CTRL-C - done


print ("about to get order list")
api = tradeapi.REST()

# Get the last 10 of our closed orders
closed_orders = api.list_orders(
	status='closed',
	limit=500
)
print(closed_orders)
#jj = json.loads(output)
for o in closed_orders:
	writeData(o)
#	print(o)
con.close()
print ("break")
