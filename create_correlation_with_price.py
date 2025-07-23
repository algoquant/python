# creates a .csv file that includes the ticker prices and sentiment for correlation analysis.
# this is supposed to loop through the top 20 in the ticker_mentions.csv but I couldn't figure out how to change the name of the dataframe so it's hard coded to run TSLA.
  

import datetime
import time
import mysql.connector
import sys, os
import inspect
import pandas as pd

# load mentions file

path1 = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

dayfile = path1 + "/ticker_mentions.csv"  
day1 = pd.read_csv(dayfile)

# add column headers
day1.columns =['ticker','mentions'] 

# sort by number of mentions 
day1 = day1.sort_values(by=['mentions'], ascending=False)
print("\n This is a list of the top 20 mentioned tickers on stocknewsapi \n")
#print(day1.head(20))



file1 = path1 + "/tickers_with_sentiment.csv"  

# loading the tab-delimited file 
df = pd.read_table(file1)
 
# add column headers
df.columns =['ticker','date','headline', 'sentiment'] 

df['short_date'] = df['date'].str.slice(0, 10) 


# this convert the sentiment text to an integer. score3 is the sentiment integer_types
# I'm sure there is a way to do this with one line of code. Lazy!

df['score1']= df['sentiment'].apply(lambda x: 1 if (x == 'Positive') else 0) 
df['score2']= df['sentiment'].apply(lambda x: -1 if (x == 'Negative') else 0) 
df['score3']= df['score1'] + df['score2']
#print(df.head)

# Get a list of target portfolio assets 

x = 0
for x in range(x,1): 

	xs = str(x)
	ticker = day1.iloc[x, 0]
	t = ticker
	ts = str(t)
	ts = ts.upper()
#	ts = ts.lower()
	tss = str(ts)
	print(ts)


	tsla1 = df.loc[df['ticker'] == 'TSLA'] 
	tsla2 = tsla1.sort_values(by=['short_date'], ascending=True)

	print(tsla2)

	x =+1



file2 = path1 + '/tickers_with_one_day_bars.csv'

# loading the CSV file 
df1 = pd.read_csv(file2)
# add column headers
df1.columns =['ticker','unixtime','volume','vway','open_s','close_s','high','low'] 

df1['date'] = pd.to_datetime(df1['unixtime'], unit='ms')
df1['dates'] = df1['date'].astype(str)

df1['short_date'] = df1['dates'].str.slice(0, 10) 
#print(df1.head)

# Get a list of target portfolio assets 

x = 0
for x in range(x,1): 

	xs = str(x)
	ticker = day1.iloc[x, 0]
	t = ticker
	ts = str(t)
	ts = ts.upper()
#	ts = ts.lower()
	tss = str(ts)
	print(ts)


	tsla3 = df1.loc[df1['ticker'] == tss] 
	tsla4 = tsla3.sort_values(by=['short_date'], ascending=True)

	print("tsla4:",tsla4.head)

	x =+1


# combine the two dataframes 
tsla = pd.merge(tsla2, tsla4, on="short_date")


tsla = tsla[['ticker_x','short_date','score3','close_s']]
tsla = tsla.sort_values(by=['short_date'], ascending=True)

print(tsla.head)
tsla.to_csv('tsla_out.csv', header=True, mode='w')

xavg10 = tsla.score3.ewm(com=10).mean()
xavg30 = tsla.score3.ewm(com=30).mean()
xavg60 = tsla.score3.ewm(com=60).mean()
xavg120 = tsla.score3.ewm(com=120).mean()
xavg300 = tsla.score3.ewm(com=300).mean()


std10 = tsla.score3.rolling(window=10).std()
std30 = tsla.score3.rolling(window=30).std()
std60 = tsla.score3.rolling(window=60).std()
std120 = tsla.score3.rolling(window=120).std()
std300 = tsla.score3.rolling(window=300).std()

tsla['xavg10'] = xavg10
tsla['xavg30'] = xavg30
tsla['xavg60'] = xavg60
tsla['xavg120'] = xavg120
tsla['xavg300'] = xavg300

tsla['std10'] = std10
tsla['std30'] = std30
tsla['std60'] = std60
tsla['std120'] = std120
tsla['std300'] = std300

	# add a column for the close_s change
tsla['change1'] = tsla.close_s.diff(periods=1)
tsla['change10'] = tsla.close_s.diff(periods=10)
tsla['change30'] = tsla.close_s.diff(periods=30)

tsla.to_csv('tsla_out.csv', header=True, mode='w')

print(tsla.head)


