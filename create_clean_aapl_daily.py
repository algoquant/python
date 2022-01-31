import datetime
import time
import mysql.connector
import sys, os

# copy current aapl price data into the large file and start a clean table


con = mydb = mysql.connector.connect(user='root', password='[your pw]', host='127.0.0.1', database='aapl')


timestamp = int(time.time())
localtime = time.ctime(timestamp)
print("Local time:", localtime)


table = "prices_aapl_daily"
table1 = "prices_aapl_daily_all"
table2 = "vxx.vxx_polygon"

sql = "create table IF NOT EXISTS " +table1+ " like " +table
print(sql)
cursor = con.cursor()
cursor.execute(sql)
con.commit()
cursor.close()



sql = "replace into " +table1+ " select * from " +table
print(sql)
cursor = con.cursor()
cursor.execute(sql)
con.commit()
cursor.close()

sql = "drop table " +table
print(sql)
cursor = con.cursor()
cursor.execute(sql)
con.commit()
cursor.close()

sql = "create table " +table+ " like " +table1
print(sql)
cursor = con.cursor()
cursor.execute(sql)
con.commit()
cursor.close()

