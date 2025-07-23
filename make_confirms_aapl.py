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
for y in range (1,6):

	try:
		subprocess.Popen(["/usr/local/bin/python3", "/Users/danielsavage/flagler/trading/confirm_orders_qqq_dan1.py"])
		subprocess.Popen(["/usr/local/bin/python3", "/Users/danielsavage/flagler/trading/confirm_orders_qqq_dan2.py"])
	
	except:
		print("confirm_orders_qqq_dan1.py failed:")

	time.sleep(10)
	y  += 1
