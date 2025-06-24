import requests
import os
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time
import datetime
from datetime import date
from datetime import datetime
from datetime import timedelta
import sys
import inspect

path1 = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
file = path1 + "/tickers.csv"  # target portfolio # negative beta

df = pd.read_csv(file)

tickerfile = "/Users/danielsavage/algos/tickers.csv" 
print(tickerfile)
tickers = pd.read_csv(tickerfile)

#print(tickers.head)


index = df.index
number_of_rows = len(index) # find length of index
print(number_of_rows)
cnt = number_of_rows
print("Count: ",cnt)


x = 0
for x in range(x,cnt):
	
	t = tickers.iloc[x, 0]
	print(t)

	x =+1

quit()
	