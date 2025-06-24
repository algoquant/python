#run as follows:
# python3 historical_nosql_bs_new.py --dateStart=20200319 --dateEnd=20200324

#optional:
# python3 historical_nosql_bs_new.py --dateStart=20200319 --dateEnd=20200324 --ticker=QQQ

import requests
import os
from datetime import datetime, timedelta
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time# as timecode
import mysql.connector
import sys
import telegram_send
import signal
import argparse

global polygon_api_key
global ticker
global con
global map

import linecache

def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f.f_globals)
    print ('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))


def signint_handler(a, b):  # define the handler  
    #print("Signal Number:", a, " Frame: ", b)  
    print ('Program termination - CTRL+C clean.')
    #end timing loop for JUST logging
    endtime = timecode.time()
    print("script time:",endtime - starttime, "seconds.")
    exit()


def remap(map, s): 
	for item,val in map.items():
		if s == item:
			return val['name']
		#print(item,val['name'])#,val['type'])


def as_date(string):
	#if "NOW" entered, set to current date.
	if string == "NOW":
		string = datetime.now().date()
		string = string.strftime("%Y%m%d")
	try:
		#print(string)
		value = datetime.strptime(string, '%Y%m%d')# %H:%M:%S')
	except:
		msg = "%s is not a date" % string
		raise argparse.ArgumentTypeError(msg)
	return value

def get_one_minute_polygon(dt, start_unix_time, unix_increment, ticker, polygon_api_key):
#	d 	= dt
	dt = dt.strftime("%Y-%m-%d")
#	d = datetime.strptime(dt.strftime("%Y-%m-%d"), '%Y-%m-%d')
	t 	= ticker.upper()
	p 	= polygon_api_key
	st 	= start_unix_time
	et 	= int(start_unix_time) + unix_increment

	st	= int(st)*1000*1000*1000
	et	= int(et)*1000*1000*1000

	last_time = st 
	last_price = None
	last_size = None
	index = 0

	import requests


	getstring=f'https://api.polygon.io/v2/ticks/stocks/trades/{t}/{dt}?limit=50000&apiKey={p}&timestamp={last_time}&timestampLimit={et}'

	print(getstring)
	resp = requests.get(getstring)
	#print(resp)

	if resp.status_code != 200:
		# This means something went wrong.
		raise ApiError('GET /historical/ {}'.format(resp.status_code))

	r=resp.json()
# 	print(r)

	
	results			= r['results']
	success			= r['success']
	map				= r['map']
	ticker			= r['ticker']
	results_count	= r['results_count']
	db_latency		= r['db_latency']

	#print("success:",success)
	#print("map:",map)
	#print("ticker:",ticker)
	#print("db_latency:",db_latency)
	#print("results_count:",results_count)

# 	return results
	
	newresults = []
	for item in results:
# 		print("item:")
# 		print(item)
		index += 1
		aDict = {}
		for key,val in item.items():
			k = remap(map, key)
			if k == "sip_timestamp":
				last_time = val
				aDict["last_time"] = val

			if k == "size":
				last_size = val
				aDict["last_size"] = val
			if k == "price":
				last_price = val
				aDict["last_price"] = val
			if k == "id":
				last_id = val
# 				aDict["last_id"] = val
# 			if k == "sequence_number":
# 				last_sequence = val
# 				aDict["last_sequence"] = val
# 			if k == "exchange":
# 				last_exchange = val
# 				aDict["last_exchange"] = val
# 			if k == "conditions":
# #				last_condition = val
# 				last_condition = ' '.join([str(elem) for elem in val]) 
# 				aDict["last_condition"] = val
# 		print("aDict:")
# 		print(aDict)

		newresults.append(aDict)

# 		print_last_time = int(last_time/1000/1000/1000)
# 
# 		print("Std Time:", index, datetime.utcfromtimestamp(print_last_time).strftime('%Y-%m-%d %H:%M:%S'))
# 
# 		#print("Unixtime: ",last_time,"Size: ",size,"Price: ",price)
# 		print("Unixtime: ",last_time,)
# 		print("newresults:")
# 		print(newresults)
	return newresults
# 
# 
# 	
# 	return None	
	
#start timing loop for JUST logging
starttime = time.time()

#asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
signal.signal(signal.SIGINT, signint_handler)  # assign the handler to the signal SIGINT  
#error handlers for CTRL-C - done


parser = argparse.ArgumentParser(description='Parameters for historical ticker script.')
parser.add_argument('--ticker',  metavar="ticker", help='Ticker symbol', default='QQQ', required=False)
parser.add_argument('--dateEnd', metavar="dateE", type=as_date,  help='Ending Date', default=None, required=False)
parser.add_argument('--dateStart', metavar="dateS", type=as_date,  help='Starting Date', default=None, required=False)
parser.add_argument('--resume', metavar="resume", type=bool,  help='Resume Flag', default=True, required=False)

args = parser.parse_args()
ticker 		= args.ticker.lower()
dateStart	= args.dateStart
dateEnd		= args.dateEnd
resume		= args.resume

tDelta = timedelta(days=1)

#without end date, use one day data
if dateEnd is None and dateStart is not None:	
	dateEnd=dateStart+Delta	

if dateStart is not None:
	dateStart=dateStart.strftime("%Y-%m-%d")
if dateEnd is not None:
	dateEnd=dateEnd.strftime("%Y-%m-%d")

if dateEnd is None and dateStart is None:
	dateEnd=datetime.now()
	dateStart=dateEnd-tDelta	
	dateEnd=dateEnd.strftime("%Y%m%d %H:%M:%S")
	dateStart=dateStart.strftime("%Y%m%d %H:%M:%S")

	

print ("Script running ticker:"+ticker)
if ticker.find(',')!=-1:
	tickers = ticker.split(",")
	print("Script can only support a single ticker at this time!")
	exit()
else:
	tickers = None 

if dateStart is not None:
	print(" Starting date:"+dateStart)
if dateEnd is not None:
	print(" Ending date:"+dateEnd)
print(" Resuming:"+str(resume))



#print(tickers)
#exit()


os.environ['polygon_api_key'] = "jg0i3J_ZFD1_v4wBRQFEzp9NHDlYwHQff5_8_u"
polygon_api_key = os.environ.get("polygon_api_key", "my-api-key")

# dd=datetime(2020, 3, 25,4,0,0)			#starting on date at 4am			
# dd = dd.strftime("%Y-%m-%d %H:%M:%S") 	#start date as string

#calculate holidays
cal = get_calendar('USFederalHolidayCalendar')  # Create calendar instance
cal.rules.pop(7)                                # Remove Veteran's Day rule
cal.rules.pop(6)                                # Remove Columbus Day rule
tradingCal = HolidayCalendarFactory('TradingCalendar', cal, GoodFriday)
#print (tradingCal.rules)

#new instance of class
cal1 = tradingCal()
holiday_dates = cal1.holidays(datetime(2020, 1, 1), datetime(2020, 12, 31))


dstart = datetime.strptime(dateStart, '%Y-%m-%d')	#start market day at 4am
dend = datetime.strptime(dateEnd, '%Y-%m-%d')	#start market day at 4am

date_rng = pd.bdate_range(datetime(dstart.year,dstart.month,dstart.day), datetime(dend.year,dend.month,dend.day),  holidays=holiday_dates, freq='C', weekmask = None)
#print (date_rng)
#exit()

#iterate market business days:
index = 0
for d in date_rng:
	index += 1
	start = datetime.strptime(d.strftime("%Y-%m-%d 4:0:0"), '%Y-%m-%d %H:%M:%S')	#start market day at 4am
	
	unixtime_start = start.strftime('%s')										#convert to unixtime
	unixtime_end = int(unixtime_start) + 57600									#16 hours ahead to	market close as 8pm
	end = datetime.fromtimestamp(unixtime_end).strftime('%Y-%m-%d %H:%M:%S')	#end date as string
	
	ii = 0
	print("iterating range: from:", int(unixtime_start), "to:", int(unixtime_end)+60,  "num iters:",(int(unixtime_end)+60 - int(unixtime_start))/60)

# 	exit()
	for i in range(int(unixtime_start), int(unixtime_end)+60, 60):	#step in 60-second increments, and inclusive of unix_end
		ii += 1
		#print(unixtime_start, unixtime_end, index, ii, i)
		res = get_one_minute_polygon(d, i, 60, ticker, polygon_api_key)
		#exit()
# 		print(res)
# 		print("----")
		cols = False	#cols turned off
		jj=0

		for r in res:
			jj += 1
			print(r)
# 			if ("last_condition") not in r:
# 				r.update({"last_condition" : [0]})
# 				print("r updated")
# 				print(r)
# 			else:
# 				print("r good")

			#start - make sure the order is correct so CSV doesn't break!
# 			from collections import OrderedDict
# 			order_of_keys = ['last_time','last_sequence','last_id','last_exchange','last_size','last_condition','last_price']
# 			order_of_keys = ['last_time','last_size','last_price']
# 			list_of_tuples = [(key, r[key]) for key in order_of_keys]
# 			od = OrderedDict(list_of_tuples)				
# # 			r = json.loads(json.dumps(od))
# 			r=dict(od)
			#end - make sure the order is correct so CSV doesn't break!
# 			print(r)
# 			exit()
			
			try:
				df = pd.DataFrame.from_dict([r], orient="columns")
# 				df = pd.DataFrame(list(r.items()), columns=['last_time','last_sequence','last_id','last_exchange','last_size','last_condition','last_price'])

				outfile = "polygon_" +ticker+ "-" +dateEnd+ ".csv"
				#print(outfile)
	#			print(ii,jj)
	#			df.to_csv(outfile,  mode = 'a', index=False) # print column headers 
				df.to_csv(outfile,  mode = 'a', index=False, header=cols)
				cols = False
			except ValueError as e:				
				PrintException()
				print("ERROR:")
				print(e)

		

exit()

