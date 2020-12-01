# -*- coding: utf-8 -*-
"""
Script for Python date and time functions

https://stackoverflow.com/questions/13031559/how-to-change-a-struct-time-object

Comment:
    The function strptime() creates a date-time structure from a string.
    The function strftime() formats a date-time structure into a string.

"""

## Import package for time commands

# Module time for time functions
import time

# Get current time in seconds since epoch
seconds = time.time()
print("Seconds since epoch =", seconds)    

# Get date and local clock time object from seconds since epoch
local_time = time.ctime(seconds)
print("Local date and clock time:", local_time)
# Create date and local clock time struct_time structure from seconds since epoch
date_time = time.localtime(seconds)
# Create Greenwich date-time structure from seconds since epoch
gm_time = time.gmtime(seconds)
print("Greenwich date and time structure:", gm_time)

# Get time in seconds from date-time structure
seconds = time.mktime(date_time)
print("Seconds since epoch:", seconds)

# Get date and local clock time as struct_time structure
date_time = time.localtime()
print("Date and local clock time structure:", date_time)
# Get year
print("Year:", date_time.tm_year)
# Get hour
print("Hour:", date_time.tm_hour)

# Get date and time string from date-time structure
local_time = time.asctime(date_time)
print("Local date and clock time:", local_time)
# Get date and time string from date-time structure
local_time = time.strftime("%d.%m.%Y %H:%M:%S", date_time)
print("Local date and clock time:", local_time)

# Create date-time structure from string
date_time = time.strptime("23.10.2012", "%d.%m.%Y")
print("Date and time object:", date_time)



## Module datetime for date and time functions
# https://www.w3schools.com/python/python_datetime.asp
"""
Comment:
    Importing whole datetime module later requires 
    using the double datetime syntax:
    datetime.datetime.strptime()
"""

# import datetime

from datetime import date, datetime, timedelta

# Get today's date as datetime structure
to_day = date.today()
yesterday = (to_day - timedelta(days = 1))
# Format datetime structures into strings
to_day = str(to_day)
yesterday = str(yesterday)
# Remove hyphens
m_date = to_day.replace("-", "")


# Create a datetime structure from integers
date_time = datetime(2020, 5, 17)
print(date_time)
# Get year
print(date_time.year)

# Create datetime structure from string
date_time = datetime.strptime("23.10.2012", "%d.%m.%Y")
print("Date and time object:", date_time)

# Format datetime structure into string
date_time.strftime("%Y-%m-%d")
# Get day of week
date_time.strftime("%A")
# Get name of month
date_time.strftime("%B")

# Get current date and time as datetime structure
date_time = datetime.now()
# Print with seconds
date_time.strftime("%d.%m.%Y %H:%M:%S")
# Print with microseconds
print(date_time)


# Get date from datetime structure
dat_e = date_time.date()

# Add 30 days to date
dat_e + timedelta(days=30)

# Add 1 month to date 2020-01-31 (use proper calendar)
date_time = datetime.strptime("2020-01-31", "%Y-%m-%d")
dat_e = date_time.date()
from dateutil.relativedelta import relativedelta
dat_e + relativedelta(months=1)

