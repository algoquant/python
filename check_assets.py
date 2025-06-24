# this script checks to top10 asset performers the previous day to determine if they are shortable 
 
import datetime
from datetime import datetime, timedelta
from datetime import date
import pandas as pd
import time
import sys, os
import alpaca_trade_api as tradeapi

timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("What is the current time: ", localtime, "Timestamp: ",timestamp)


from settings import login6p, acct_name6p, keya6p, keyb6p


login = login6p
acct_name = acct_name6p
key1 = keya6p
key2 = keyb6p
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




today = date.today()
#print(today)

yesterday = str(today - timedelta(days = 1))
myesterday = str(yesterday)
ydate = myesterday.replace("-","")

mtoday = str(today)
mdate = mtoday.replace("-","")
#print(mdate)

# turn offf error messages
pd.options.mode.chained_assignment = None


ux = int(time.time())
uxs = str(ux)


ticker			= "qqq" #default


api = tradeapi.REST()

# Get a list of top assets yesterday

path1 = "/Users/danielsavage/algos"
file1 = path1 + "/top100_" +ydate+ ".csv"
topassets = pd.read_csv(file1)

#print(topassets.head(10))
toptickers = topassets['ticker']
#print(toptickers.head)


x = 0
for x in range(x,11):

	xs = str(x)
	ticker = topassets.iloc[x, 1]
	t = ticker
	ts = str(t)
	ts = ts.upper()
#	ts = ts.lower()
#	print(ts)

	# Check if ticker tradable on the Alpaca platform.
	asset = api.get_asset(ts)

	#print(asset)

	short = 0
	
	if asset.tradable:
	    print('\nWe can trade ',ts)
	    long = str(1)
	
	if asset.shortable:
		short = '1'	
	
	if short == 0:
		print(ts," cannot be shorted today")
	else:
		print(ts, " can be shorted today")
	

	x =+1
	