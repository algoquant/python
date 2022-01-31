#import os
#import sys
import datetime
import time
import mysql.connector
import telegram_send

#connect to database, but create database if not found

con = mydb = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='qqq')
#con = mydb = mysql.connector.connect(user='root', password='[your pw]', host='108.21.219.93', database='qqq')

from datetime import date, timedelta
today = date.today()
print(today)

today = str(today)


timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)


#testing
#timestamp = 1586426401

print(timestamp)

x = (timestamp - 50000)
y = str(x)
# check to see if polygon stopped update the all_pries tableInsertModeElements
 
p1 = p2 = a1 = a2 =0

 
cursor = con.cursor()
qy = "select sum(profit), avg(profit), count(profit) from long_trades_qqq_dan1 where unixtime > " +y+ " and profit <> 0" 
print ("sql:", (qy))
cursor.execute(qy)
result = cursor.fetchall()
for profit in result:
	p1 = (profit[0])
	a1 = (profit[1])
	c1 = (profit[2])

if (p1 == 'NULL'):
	p1 = 0
if (a1 == 'NULL'):
	a1 = 0


cursor.close()
p1s = str(p1)
a1s = str(a1)
c1s = str(c1)


cursor = con.cursor()


print("Profit: ",p1,"Average: ",a1, "Trades: ",c1)

cursor1 = con.cursor()
qy1 = "select sum(profit), avg(profit), count(profit) from short_trades_qqq_dan2 where unixtime > " +y+ " and profit <> 0" 
print ("sql1:", (qy1))
cursor.execute(qy1)
result1 = cursor.fetchall()
for profit1 in result1:
	p2 = (profit1[0])
	a2 = (profit1[1])
	c2 = (profit1[2])


if (p2 == 'NULL'):
	p2 = 0
if (a2 == 'NULL'):
	a2 = 0


cursor1.close()
p2s = str(p2)
a2s = str(a2)
c2s = str(c2)


print("Profit: ",p2,"Average: ",a2, "Trades: ",c2)


print("these are the totals")
	

telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["Long Account QQQ \n Profit: " + p1s + "\n Trades: " + c1s + "\n Avg Trade: " + a1s])


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["Short Account QQQ \n Profit: " + p2s + "\n Trades: " + c2s + "\n Avg Trade: " + a2s])


try:

	tp = (p1 + p2)
	tt = (c1 + c2)
	ta = (tp / tt)
	roi = (tp / 1100)
	
	tps = str(tp)
	tts = str(tt)
	tas = str(ta)
	rois = str(roi)
	rois = rois[0:5] 

except OSError as e:
	pass

print("Total Profit: ",tps,"Average: ",tas, "Trades: ",tts)
telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["Daily Total QQQ \n Profit: " + tps + "\n Trades: " + tts + "\n Avg Trade: " + tas+ "% Gain: " +rois])
	
	
