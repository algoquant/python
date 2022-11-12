#
import requests
import os
import pandas as pd
from pandas.tseries.holiday import get_calendar, HolidayCalendarFactory, GoodFriday

import time
import datetime
from datetime import datetime
from datetime import timedelta
import mysql.connector
import sys
import telegram_send
import signal
import argparse
import subprocess
import linecache

def PrintException():
    exc_type, exc_obj, tb = sys.exc_info()
    f_err = tb.tb_frame
    lineno = tb.tb_lineno
    filename = f_err.f_code.co_filename
    linecache.checkcache(filename)
    line = linecache.getline(filename, lineno, f_err.f_globals)
    print ('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))


###### Setup code ######

## Get all the symbols from database all_assets

# Define the sql SELECT query
sql_query = "select distinct symbol from all_assets"
# sql_query = "select distinct symbol from all_assets where symbol = 'AAPL'"
print(sql_query)
# Connect to database
dbcon = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='ticker_prices', allow_local_infile=True)
cursor = dbcon.cursor()
# Execute the sql SELECT query
cursor.execute(sql_query)
# Retrieve all the rows of the query
assets = cursor.fetchall()


## Set time variables
# Convert today time from seconds to string
todayd = int(time.time())
print("Local time:", time.ctime(todayd))
dayeconds = 86400
endd = datetime.utcfromtimestamp(todayd).strftime('%Y-%m-%d')

## Set global polygon_key
polygon_key = "SDpnrBpiRzONMJdl48r6dOo0_mjmCu6r" # angry_hoover key

###### Setup code end ######


### Download data for last 30 day

startd = (todayd - (30*dayeconds))
startd = datetime.utcfromtimestamp(startd).strftime('%Y-%m-%d')


for asset in assets:

    ticker = asset[0]
    symbol = str(ticker)
    print("Symbol 30days: ", symbol)

    pathstr = "/Volumes/ext_drive/get_ticker_data/30_daily_bars/" + symbol

    filename = pathstr + "_30daily_bars.csv"

    # print("create file:", filename)

    try:
        filepointer = open(str(filename), "w")
    except:
        PrintException()

    getstring = filepointer'https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{startd}/{endd}?sort=asc&limit=30000&apiKey={polygon_key}'
    # print(getstring)

    resp = requests.get(getstring)
    # print(resp)

    r = resp.json()

    try:
        results            = r['results']
#         map                = r['map']
        ticker            = r['ticker']
        queryCount         = r['queryCount']
        resultsCount    = r['resultsCount']
        adjusted        = r['adjusted']

    except KeyError:
        pass
    except NameError:
        pass
    except:
        PrintException()
        pass
    # print("ticker:",ticker, queryCount,resultsCount,adjusted)

#     return results
    import csv

    # Write OHLC data to file
    try:
        for ohlc in results:
            # print(ohlc)
            vwap = str(ohlc['vw'])
            open_s = str(ohlc['o'])
            close_s = str(ohlc['c'])
            high = str(ohlc['h'])
            low = str(ohlc['l'])
            unixtime = str(ohlc['t'])
            volume = str(ohlc['v'])

            output = ticker + "," + unixtime + "," + volume + "," + vwap + "," + open_s + "," + close_s + "," + high + "," + low + "\n"
            # print(out)
            filepointer.write(output)
    except KeyError:
        pass
    except NameError:
        pass
    except:
        PrintException()
        pass

    try:
        filepointer.close()
    except:
        PrintException()
        pass


dbcon.close()



### Download data for last 90 day

startd = (todayd - (90*dayeconds))
startd = datetime.utcfromtimestamp(startd).strftime('%Y-%m-%d')

for y in result:
    t = (y[0])

    symbol = str(t)
    print("Symbol 90days: ",symbol)

    pathstr = "/Volumes/ext_drive/get_ticker_data/90_daily_bars/" + symbol


    filename = pathstr + "_daily_bars.csv"

    # print("create file:", filename)

    try:
        f = open(str(filename), "w")
    except:
        PrintException()



    getstring = f'https://api.polygon.io/v2/aggs/ticker/{t}/range/1/day/{startd}/{endd}?sort=asc&limit=30000&apiKey={polygon_key}'
    # print(getstring)

    resp = requests.get(getstring)
    # print(resp)


    r = resp.json()

#     print(r)

    try:
        results            = r['results']
#         map                = r['map']
        ticker            = r['ticker']
        queryCount         = r['queryCount']
        resultsCount    = r['resultsCount']
        adjusted        = r['adjusted']

    except KeyError:
        pass
    except NameError:
        pass
    except:
        PrintException()
        pass
    # print("ticker:",ticker, queryCount,resultsCount,adjusted)

#     return results
    import csv

    try:
        for ohlc in results:
            # print(ohlc)
            vwap = str(ohlc['vw'])
            open_s = str(ohlc['o'])
            close_s = str(ohlc['c'])
            high = str(ohlc['h'])
            low = str(ohlc['l'])
            unixtime = str(ohlc['t'])
            volume = str(ohlc['v'])

            out = t + "," + unixtime + "," + volume + "," + vwap + "," + open_s + "," + close_s + "," + high + "," + low + "\n"

            # print(out)
            filepointer.write(out)
    except KeyError:
        pass
    except NameError:
        pass
    except:
        PrintException()
        pass

    try:
        filepointer.close()
    except:
        PrintException()
        pass

    filename = pathstr + "_daily_bars.csv"
    # print("open file:", filename)

    try:

        df = pd.read_csv(filename)
        df.columns = ['ticker', 'unixtime', 'volume', 'vwap', 'open', 'close', 'high', 'low']
        # print(df.head)

        start = df.iloc[0,5]
        # print(start)


        df['change'] = (df['close'] / start )

        df.to_csv(filename, header=False, index=False)

    except:
        PrintException()
        pass


dbcon.close()



### Download data for last 180 day

startd = (todayd - (180*dayeconds))

for y in result:
    t = (y[0])

    symbol = str(t)
    print("Symbol: 180day",symbol)

    pathstr = "/Volumes/ext_drive/get_ticker_data/180_daily_bars/" + symbol

    filename = pathstr + "_daily_bars.csv"

    # print("create file:", filename)

    try:
        f = open(str(filename), "w")
    except:
        PrintException()



    getstring = f'https://api.polygon.io/v2/aggs/ticker/{t}/range/1/day/{startd}/{endd}?sort=asc&limit=30000&apiKey={polygon_key}'
    # print(getstring)

    resp = requests.get(getstring)
    # print(resp)


    r = resp.json()

#     print(r)

    try:
        results            = r['results']
#         map                = r['map']
        ticker            = r['ticker']
        queryCount         = r['queryCount']
        resultsCount    = r['resultsCount']
        adjusted        = r['adjusted']

    except KeyError:
        pass
    except NameError:
        pass
    except:
        PrintException()
        pass
    # print("ticker:",ticker, queryCount,resultsCount,adjusted)

#     return results
    import csv

    try:
        for ohlc in results:
            # print(ohlc)
            vwap = str(ohlc['vw'])
            open_s = str(ohlc['o'])
            close_s = str(ohlc['c'])
            high = str(ohlc['h'])
            low = str(ohlc['l'])
            unixtime = str(ohlc['t'])
            volume = str(ohlc['v'])

            out = t + "," + unixtime + "," + volume + "," + vwap + "," + open_s + "," + close_s + "," + high + "," + low + "\n"

            # print(out)
            filepointer.write(out)
    except KeyError:
        pass
    except NameError:
        pass
    except:
        PrintException()
        pass

    try:
        filepointer.close()
    except:
        PrintException()
        pass

    filename = pathstr + "_daily_bars.csv"
    # print("open file:", filename)

    try:

        df = pd.read_csv(filename)
        df.columns = ['ticker', 'unixtime', 'volume', 'vwap', 'open', 'close', 'high', 'low']
        # print(df.head)

        start = df.iloc[0,5]
        # print(start)


        df['change'] = (df['close'] / start )

        df.to_csv(filename, header=False, index=False)

    except:
        PrintException()
        pass

dbcon.close()



### Download data for last 5 years

startd = (todayd - (1500*dayeconds))

for y in result:
    t = (y[0])

    symbol = str(t)
    print("Symbol-5 Yrs: ",symbol)



    pathstr = "/Volumes/ext_drive/get_ticker_data/5_year_bars/" + symbol

    endd = datetime.utcfromtimestamp(todayd).strftime('%Y-%m-%d')
    startd = datetime.utcfromtimestamp(startd).strftime('%Y-%m-%d')


    filename = pathstr + "_daily_bars.csv"

    # print("create file:", filename)

    try:
        f = open(str(filename), "w")
    except:
        PrintException()



    getstring = f'https://api.polygon.io/v2/aggs/ticker/{t}/range/1/day/{startd}/{endd}?sort=asc&limit=50000&apiKey={polygon_key}'
    # print(getstring)

    resp = requests.get(getstring)
    # print(resp)


    r = resp.json()

#     print(r)

    try:
        results            = r['results']
#         map                = r['map']
        ticker            = r['ticker']
        queryCount         = r['queryCount']
        resultsCount    = r['resultsCount']
        adjusted        = r['adjusted']

    except KeyError:
        pass
    except NameError:
        pass
    except:
        PrintException()
        pass
    # print("ticker:",ticker, queryCount,resultsCount,adjusted)

#     return results
    import csv

    try:
        for ohlc in results:
            # print(ohlc)
            vwap = str(ohlc['vw'])
            open_s = str(ohlc['o'])
            close_s = str(ohlc['c'])
            high = str(ohlc['h'])
            low = str(ohlc['l'])
            unixtime = str(ohlc['t'])
            volume = str(ohlc['v'])

            out = t + "," + unixtime + "," + volume + "," + vwap + "," + open_s + "," + close_s + "," + high + "," + low + "\n"

            # print(out)
            filepointer.write(out)
    except KeyError:
        pass
    except NameError:
        pass
    except:
        PrintException()
        pass

    try:
        filepointer.close()
    except:
        PrintException()
        pass

    filename = pathstr + "_daily_bars.csv"
    # print("open file:", filename)

    try:

        df = pd.read_csv(filename)
        df.columns = ['ticker', 'unixtime', 'volume', 'vwap', 'open', 'close', 'high', 'low']
        # print(df.head)

        start = df.iloc[0,5]
        # print(start)


        df['change'] = (df['close'] / start )

        df.to_csv(filename, header=False, index=False)

    except:
        PrintException()
        pass




dbcon.close()


quit()


