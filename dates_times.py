# -*- coding: utf-8 -*-
"""
Script with examples of using Python date and time functions

Date and time types:
https://docs.python.org/3/library/datetime.html

https://stackoverflow.com/questions/7479777/difference-between-python-datetime-vs-time-modules
https://stackoverflow.com/questions/13031559/how-to-change-a-struct-time-object

Comment:
    The function strptime() creates a date-time structure from a string.
    The function strftime() formats a date-time structure into a string.

"""

## Import package for time commands

# Package time for time functions
import time

# Create date and time structure from string, as a struct_time structure
datev = time.strptime("23.10.2012", "%d.%m.%Y")
print("Date and time object:", datev)
type(datev)

# Get current time in seconds since epoch
secondsn = time.time()
print("Seconds since epoch =", secondsn)

# Get date and local clock time object from seconds since epoch
datev = time.ctime(secondsn)
print("Local date and clock time:", datev)
# Create the date and time from seconds since epoch, as a struct_time structure
datev = time.localtime(secondsn)
# Create Greenwich date-time structure from seconds since epoch
timegm = time.gmtime(secondsn)
print("Greenwich date and time structure:", timegm)

# Get time in seconds from date-time structure
secondsn = time.mktime(datev)
print("Seconds since epoch:", secondsn)

# Get date and local clock time as struct_time structure
datev = time.localtime()
print("Date and local clock time structure:", datev)
# Get year
print("Year:", datev.tm_year)
# Get hour
print("Hour:", datev.tm_hour)

# Get date and time string from date-time structure
datestr = time.asctime(datev)
print("Local date and clock time:", datestr)
# Get date and time string from date-time structure
datestr = time.strftime("%d.%m.%Y %H:%M:%S", datev)
# Get date string from date-time structure
datestr = time.strftime("%Y-%m-%d", datev)
print("Date:", datestr)



## Module datetime for date and time functions
# https://www.w3schools.com/python/python_datetime.asp
"""
Comment:
    Importing whole datetime module later requires
    using the double datetime syntax:
    datetime.datetime.strptime()
"""

# Import datetime for dates and times
# Don't import the whole module because it requires the double datetime syntax
# import datetime
from datetime import date, datetime, timedelta

# Create a datetime object from the year, month, and day
datev = datetime(2020, 5, 17)
print(datev)
# Get the year
print(datev.year)
# Create a datetime object for May 5, 2023, 12:00 PM
datev = datetime(2023, 5, 5, 12, 0)
# Create a datetime object from the attributes: 
# year, month, day, hour, minute, second, and microsecond
datev = datetime(2024, 8, 25, 11, 36, 7, 204690)

# Get current date and local clock time as a datetime object
datev = datetime.now()
print(datev)

# Get the seconds since epoch from date-time structure
datev.timestamp()

# Get the timezone - by default it's US/Eastern
datev.astimezone().tzinfo

# Create datetime object from string
datev = datetime.strptime("23.10.2012", "%d.%m.%Y")
print("Date and time object:", datev)

# Print date and time with seconds
datev = datetime.now()
datev.strftime("%d.%m.%Y %H:%M:%S")
# Print with microseconds
print(datev)

# Format datetime object into string
datev.strftime("%Y-%m-%d")
# Get day of week
datev.strftime("%A")
# Get name of month
datev.strftime("%B")
datev.strftime("%Y-%m-%d_%H-%M-%S.%f %z")

# Extract the date from the datetime object
datobj = datev.date()
# Coerce the date to a string
str(datobj)
# Add 30 days to date
datobj + timedelta(days=30)

# Get today's date as a datetime object
todayd = date.today()
type(todayd)
print(todayd)
yesterdayd = (todayd - timedelta(days = 1))
# Format datetime objects into strings
todayd = str(todayd)
print(todayd)
yesterdayd = str(yesterdayd)
# Remove hyphens
mdate = todayd.replace("-", "")


# Add 1 month to date 2020-01-31 (use proper calendar)
datev = datetime.strptime("2020-01-31", "%Y-%m-%d")
datev = datev.date()
from dateutil.relativedelta import relativedelta
datev + relativedelta(months=1)


## Import zoneinfo for time zones
from zoneinfo import ZoneInfo, available_timezones
# Don't use pytz because it's deprecated - use zoneinfo instead
# from pytz import timezone

# Local clock time without the time zone
datev = datetime.now()
print(datev)
print(datev.utcoffset())
# Get the timezone - by default it's US/Eastern
print(datev.astimezone().tzinfo)

# Define the Pacific time zone
tzone = ZoneInfo("US/Pacific")
# Clock time in the Pacific zone, at the same moment of time as now
# The timezone object is passed to datetime.now()
datev = datetime.now(tz=tzone)
print(datev)
# Get the timezone - returns EDT, not PT
datev.astimezone().tzinfo
datev = datev.isoformat(timespec="seconds")
print(f"Pacific time {datev}")

# Print the available time zones
available_timezones()
# Define the Pacific time zone
tzone = ZoneInfo("US/Pacific")
str(tzone)
# Clock time in the Pacific zone, at the same moment of time as now
datev = datetime.now()
print(datev)
datep = datev.astimezone(tzone)
print(datep)
datep.tzname()
datep.utcoffset()

# Change the time zone but keep the same clock time, at a different moment of time
# "Seemingly simple but I cannot get it to work."
# https://stackoverflow.com/questions/64390568/set-timezone-without-changing-time-python
# Define the Eastern time zone
tzone = ZoneInfo("US/Eastern")
# Add the time zone to the clock time
# datev = datev.astimezone(tzone)
datev = datev.replace(tzinfo=tzone)
print(datev)
# Define the Pacific time zone
tzone = ZoneInfo("US/Pacific")
# Change the time zone but keep the same clock time, at a different moment of time
datep = datev.replace(tzinfo=tzone)
print(datep)


# Get the UTC time as a datetime object
datutc = datetime.utcnow()
# Get the seconds since epoch (UTC)
secutc = datutc.timestamp()
# Get the datetime object from the seconds since epoch
datev = datetime.fromtimestamp(secutc)
datev == datutc

# pytz is deprecated
# Local clock time with timezone object passed to datetime.now()
# tzone = timezone("US/Pacific")
# datev = datetime.now(tz=tzone)
# Get the timezone - returns EDT, not PT
# datev.astimezone().tzinfo

