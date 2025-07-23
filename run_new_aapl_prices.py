# rev 8-5-2020

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

for y in range (1,60):

	try:
		subprocess.Popen(["/usr/local/bin/python3", "/Users/danielsavage/flagler/trading/new_aapl_prices.py"])
	
	except:
		print("price update failed:")

	time.sleep(1)
	y  += 1
