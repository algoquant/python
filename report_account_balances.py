
import datetime
import time as timecode
import mysql.connector
import sys, os
import alpaca_trade_api as tradeapi
import telegram_send

#connect to database, but create database if not found

con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='127.0.0.1', database='qqq')
#con = mydb = mysql.connector.connect(user='root', password='waWWii21156!', host='108.21.219.93', database='qqq')

from datetime import date, timedelta
today = date.today()
print(today)


from settings import login6p, acct_name6p, keya6p, keyb6p

login = login6p
acct_name = acct_name6p
key1 = keya6p
key2 = keyb6p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
#print(account)

# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)

telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\n\nSPY Benchmark(pta6) 4:1 leverage : " + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])
# --------------------------------------------------------------------------------

from settings import loginf1p, acct_namef1p, keyaf1p, keybf1p

login = loginf1p
acct_name = acct_namef1p
key1 = keyaf1p
key2 = keybf1p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
#print(account)

# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nSPY ML Trading Long/Short: " + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])


# --------------------------------------------------------------------------------


from settings import loginf2p, acct_namef2p, keyaf2p, keybf2p

login = loginf2p
acct_name = acct_namef2p
key1 = keyaf2p
key2 = keybf2p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
#print(account)

# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nQQQ ML Trading Long/Short: " + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])


# --------------------------------------------------------------------------------


from settings import login1p, acct_name1p, keya1p, keyb1p

login = login1p
acct_name = acct_name1p
key1 = keya1p
key2 = keyb1p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)
# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nAAPL ML Trading Long/Short: " + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])


# --------------------------------------------------------------------------------


from settings import login2p, acct_name2p, keya2p, keyb2p

login = login2p
acct_name = acct_name2p
key1 = keya2p
key2 = keyb2p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)
# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nVXX  ML Trading Long/Short: " + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])



# --------------------------------------------------------------------------------


from settings import login3p, acct_name3p, keya3p, keyb3p

login = login3p
acct_name = acct_name3p
key1 = keya3p
key2 = keyb3p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)
# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nTrade on StockNewsAPI daily sentiment: " + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])

# --------------------------------------------------------------------------------


from settings import login4p, acct_name4p, keya4p, keyb4p

login = login4p
acct_name = acct_name4p
key1 = keya4p
key2 = keyb4p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)
# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nShort Best 10 Performers Yesterday: " + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])


# --------------------------------------------------------------------------------


from settings import login5p, acct_name5p, keya5p, keyb5p

login = login5p
acct_name = acct_name5p
key1 = keya5p
key2 = keyb5p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)
# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nBuy Dividend Stocks on exDate: " + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])


# --------------------------------------------------------------------------------


from settings import login7p, acct_name7p, keya7p, keyb7p

login = login7p
acct_name = acct_name7p
key1 = keya7p
key2 = keyb7p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)
# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nHigh Beta Large Cap:\n" + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])


# --------------------------------------------------------------------------------


from settings import login8p, acct_name8p, keya8p, keyb8p

login = login8p
acct_name = acct_name8p
key1 = keya8p
key2 = keyb8p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)
# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nNegative Beta: \n" + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])


# --------------------------------------------------------------------------------



from settings import login9p, acct_name9p, keya9p, keyb9p

login = login9p
acct_name = acct_name9p
key1 = keya9p
key2 = keyb9p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)

# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nSmall Cap (< 100M): \n" + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])


# --------------------------------------------------------------------------------



from settings import login10p, acct_name10p, keya10p, keyb10p

login = login10p
acct_name = acct_name10p
key1 = keya10p
key2 = keyb10p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)
# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nValue Stocks, Large Cap, Low PE: \n" + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])



# --------------------------------------------------------------------------------



from settings import login11p, acct_name11p, keya11p, keyb11p

login = login11p
acct_name = acct_name11p
key1 = keya11p
key2 = keyb11p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)
# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nSPY 1,000 Shares Short: \n" + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])


# --------------------------------------------------------------------------------

try:

	from settings import login12p, acct_name12p, keya12p, keyb12p
	
	login = login12p
	acct_name = acct_name12p
	key1 = keya12p
	key2 = keyb12p
	endpoint = "https://paper-api.alpaca.markets"
	
	print(login)
	print(acct_name)
	print(key1)
	print(key2)
	print(endpoint)
	
	acctname = acct_name
	os.environ["APCA_API_BASE_URL"] = endpoint
	os.environ["APCA_API_KEY_ID"] = key1
	os.environ["APCA_API_SECRET_KEY"] = key2
	
	import alpaca_trade_api as tradeapi
	
	api = tradeapi.REST()
	
	
	# Get account info
	account = api.get_account()
	##print(account)
	# Check our current balance vs. our balance at the last market close
	balance_change = float(account.equity) - float(account.last_equity)
	cash = float(account.cash)
	balance = float(account.equity)
	account = account.account_number
	portfolio = float((cash * -1) + balance)
	
	account = str(account)
	balance = int(balance)
	portfolio = int(portfolio)
	
	balance = "{:,d}".format(balance)
	portfolio = "{:,d}".format(portfolio)
	
	print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)
	
	telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nDev Server: \n" + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])
except:
	pass	
	
# --------------------------------------------------------------------------------



from settings import login13p, acct_name13p, keya13p, keyb13p

login = login13p
acct_name = acct_name13p
key1 = keya13p
key2 = keyb13p
endpoint = "https://paper-api.alpaca.markets"

print(login)
print(acct_name)
print(key1)
print(key2)
print(endpoint)

acctname = acct_name
os.environ["APCA_API_BASE_URL"] = endpoint
os.environ["APCA_API_KEY_ID"] = key1
os.environ["APCA_API_SECRET_KEY"] = key2

import alpaca_trade_api as tradeapi

api = tradeapi.REST()


# Get account info
account = api.get_account()
##print(account)
# Check our current balance vs. our balance at the last market close
balance_change = float(account.equity) - float(account.last_equity)
cash = float(account.cash)
balance = float(account.equity)
account = account.account_number
portfolio = float((cash * -1) + balance)

account = str(account)
balance = int(balance)
portfolio = int(portfolio)

balance = "{:,d}".format(balance)
portfolio = "{:,d}".format(portfolio)

print("Account: ", account, "Balance: ", balance, "Portfolio: ", portfolio)


telegram_send.send(conf="/Users/danielsavage/flagler/trader_api/telegram-stats-send.conf",messages=["\nShort TSLA: \n" + account + "\n Balance: " + balance + "\n Portfolio: " + portfolio])



exit()
