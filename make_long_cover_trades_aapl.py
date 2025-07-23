# rev 4-21-2020

import os
import sys
import datetime
import time
import mysql.connector
import subprocess

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

#for y in range (1,22000):
for y in range (1,3):

	try:
		subprocess.Popen(["/usr/local/bin/python3", "/Users/danielsavage/flagler/trading/long_trade_cover_aapl_dan1.py"])
		#subprocess.Popen(["/usr/local/bin/python3", "/Users/danielsavage/flagler/trading/long_trade_cover_aapl_dan1_timed.py"])
	
	except:
		print("long trade buy failed:")

	time.sleep(30)
	y  += 1
