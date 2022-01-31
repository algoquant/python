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

for y in range (1,5):

	try:
		subprocess.Popen(["/usr/local/bin/python3", "/Users/danielsavage/flagler/trading/short_limit_buy_aapl_dan2.py"])
	
	except:
		print("short trade buy failed:")

	time.sleep(13)
	y  += 1
