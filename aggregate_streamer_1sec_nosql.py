# MSG: {"event_type": "T", "timestamp": 1579127507190, "ex_id": 11, "id": 16827, "symbol": "QQQ", "price": 220.37, "size": 30, "conditions": [14, 12, 37, 41]}
# MSG: {"event_type": "T", "timestamp": 1579127507191, "ex_id": 11, "id": 16828, "symbol": "QQQ", "price": 220.35, "size": 70, "conditions": [12, 37]}
# // Stocks TRADE:
# {
#     "ev": "T",              // Event Type
#     "sym": "MSFT",          // Symbol Ticker
#     "x": "4",               // Exchange ID
#     "i": 12345,             // Trade ID
#     "z": 3,                 // Tape ( 1=A 2=B 3=C)
#     "p": 114.125,           // Price
#     "s": 100,               // Trade Size
#     "c": [0, 12],           // Trade Conditions
#     "t": 1536036818784      // Trade Timestamp ( Unix MS )
# }

import os
import json
import datetime
import asyncio
import uvloop
import logging
from polygon_streamer import PolygonStreamer

import time 
import datetime
from datetime import datetime, timedelta
from datetime import date
import time as timecode
import mysql.connector
import sys
#import telegram_send
import signal
import argparse
import linecache
import pandas as pd
import inspect

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("What is the current time: ", localtime, "Timestamp: ",timestamp)


today = date.today()
#print(today)

yesterday = str(today - timedelta(days = 1))
myesterday = str(yesterday)
ydate = myesterday.replace("-","")

mtoday = str(today)
mdate = mtoday.replace("-","")
#print(mdate)

ux = timestamp
uxs = str(ux)

#mdate = '20210309'



global ticker
global f
# f={}
def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f_err = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f_err.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f_err.f_globals)
    print ('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))



def signint_handler(a, b):  # define the handler  
    #print("Signal Number:", a, " Frame: ", b)  
    print ('Program termination - CTRL+C clean.')
    #end timing loop for JUST logging
    endtime = timecode.time()
    print("script time:",endtime - starttime, "seconds.")
    exit()

def file_maker(ticker):
	global f
	f[ticker.lower()]=open(ticker.lower()+"_polygonaggr", "a")
	print("file open successfully")



ticker 			= "spy"	#default

#start timing loop for JUST logging
starttime = timecode.time()

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())


signal.signal(signal.SIGINT, signint_handler)  # assign the handler to the signal SIGINT  
#error handlers for CTRL-C - done

spy = "SPY,QQQ,VXX,SVXY,AAPL,VXI,TQQQ,SPXL"



parser = argparse.ArgumentParser(description='Parameters for historical ticker script.')
parser.add_argument('--ticker',  metavar="ticker", help='Ticker symbol', default=spy, required=False)

args 	= parser.parse_args()
ticker 	= args.ticker.lower()
print ("Script running ticker:"+ticker)
if ticker.find(',')!=-1:
	tickers = ticker.split(",")
else:
	tickers = None 


if tickers != None:
# 	for ticker in tickers:
# 		file_maker(ticker)
	tickers = ["A."+item.upper() for item in tickers]
	tickers = ','.join(tickers)
else:
# 	file_maker(ticker)
	tickers = "A."+ticker.upper()

print(tickers)
#exit()
#qqqfile = open('qqq_polygon.txt', 'a+')

	
class StocksStreamer(PolygonStreamer):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)

	def listToString(s):  
	
		# initialize an empty string 
		str1 = ""  
	
		# traverse in the string   
		for ele in s:  
			str1 += ele   
	
		# return string   
		return str1  
	
	async def callback(self, message_str):
		try:
			def mapper(message):
				print("MSG DATA: "+json.dumps(message) )
				if message["ev"] == "T":
					return {
						"event_type": message["ev"],
						"starttime": message["t"],	#datetime.datetime.fromtimestamp(message["t"] / 1000),
						"ex_id": message["x"],
						"id": message["i"],
						"symbol": message["sym"].lower(),
						"price": message["p"],
						"size": message["s"],
						"conditions": message["c"]
					}
				elif message["ev"] == "A":
					print("DATATYPE:")
					print(type(message))
					if not 'op' in message.keys():				
						message["op"] = 0
					return {
						"event_type": message["ev"],
						"starttime": message["s"],	#datetime.datetime.fromtimestamp(message["t"] / 1000),
						"endtime": message["e"],	#datetime.datetime.fromtimestamp(message["t"] / 1000),
						"symbol": message["sym"].lower(),
						"open_price": message["op"],
						"wvap": message["vw"],
						"open": message["o"],
						"high": message["h"],
						"low": message["l"],
						"close": message["c"],
						"average": message["a"],
						"vol": message["v"],
						"av_vol": message["av"],
					}
#  {"ev": "A", "sym": "AAPL", "v": 40146, "av": 75399750, "op": 118.61, "vw": 118.0347, "o": 118.13, "c": 117.9806, "h": 118.1498, "l": 117.98, "a": 118.9437, "z": 80, "s": 1605733740000, "e": 1605733800000}				
				else:
# 					print("return message:")
# 					return message
					return {
						"event_type": message["ev"],
						"status": message["status"],
						"message": message["message"],
					}
			#return 

			localtime = time.ctime(starttime / 1000)


			
			for message in json.loads(message_str):
				msg = mapper(message)
				print("DATA: "+json.dumps(msg))
				if msg["event_type"]:
					if msg["event_type"] == "A":
						print("A DATA: "+json.dumps(mapper(message) ) )
						try:

							out = str(msg["symbol"]) + ", " + str(msg["vol"]) + ", " + str(msg["av_vol"]) + ", " + str(msg["open_price"]) + ", "
#							out = str(msg["vol"]) + ", " + str(msg["av_vol"]) + ", " + str(msg["open_price"]) + ", "
							out += str(msg["open"]) + ", " + str(msg["high"]) + ", " + str(msg["low"]) + ", " +localtime+ ", "
							out += str(msg["close"]) + ", " + str(msg["average"]) + ", " + str(msg["vol"]) + ","
							out += str(int(msg["starttime"]/1000))+"," + str(int(msg["endtime"]/1000))+"\n"
							print(msg["symbol"])
							print(out)
							f=open(mdate.lower()+"_polygonaggr.csv", "a")
							f.write(out)

							f.close()
# 							f[msg["symbol"]].write(out)

							print ("inserted")

						except Exception as e:
							print("insert row failed:",getattr(e, 'message', repr(e)))
							PrintException()

					elif msg["event_type"] == "T":
						print("T DATA: "+json.dumps(mapper(message) ) )

						try:

							print ("sql:", (sql, data))
							out = str(msg["price"]) + ", " +str(msg["size"])+ "," +localtime+ ", "+str(int(msg["timestamp"]/1000))+"\n"

							f[msg["symbol"]].write(out)

# 							cursor.execute(sql, data)
# 							con.commit()
# 							cursor.close()
							print ("inserted")
						except Exception as e:
							print("insert row failed:",getattr(e, 'message', repr(e)))
							PrintException()
					else:
						print("MSG: "+json.dumps(mapper(message) ) )
				else:
					print("MSG NO EV: "+json.dumps(mapper(message) ) )
		
			#return print([mapper(message) for message in json.loads(message_str)])

		except Exception as e:
			logging.error("{}".format(e.args))
			logging.exception("Error:\n%s" % e)
			PrintException()

#qqqfile.close()

def main():  
	#"T.MSFT,T.AAPL,T.AMD,T.NVDA"
	os.environ['polygon_api_key'] = "fmE3T2pErY3E_OO5q7LcBLHqCAQI_b7X" # default
	polygon_api_key = os.environ.get("polygon_api_key", "my-api-key") 
	cluster = "/stocks"
	symbols_str = tickers	#"T."+ticker
	streamer = StocksStreamer(api_key=polygon_api_key, cluster=cluster, symbols_str=symbols_str)
	streamer.start()


if __name__ == '__main__':
	main()



