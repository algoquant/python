
import datetime
import pandas as pd
import numpy as np

from utils import get_symbol, calc_rollsum, calc_sharpe
from strategies import strat_movavg


# markv = {i: str(i) for i in range(50, 120, 10)}
# print(markv)

# Define parameters
symbol = "SPY"
range = "day"
startd = datetime.date(2000, 1, 1)
endd = datetime.date.today()
# Download stock prices from Polygon for the symbol
ohlc = get_symbol(symbol=symbol, startd=startd, endd=endd, range=range)
# Calculate log stock prices
# ohlc[["Open", "High", "Low", "Close"]] = np.log(ohlc[["Open", "High", "Low", "Close"]])
# Calculate log asset returns
closep = np.log(ohlc.Close)
returnts = closep.diff()
sharpass = round(calc_sharpe(returnts), 3)

# Calculate the strategy Sharpe ratio
lookback = 21
lagv = 5
retstrat = strat_movavg(closep, returnts, lookback, lagv)
sharpestrat = calc_sharpe(retstrat)
textv = "Strategy Sharpe = " + str(round(sharpestrat, 3)) + "\n" + symbol + " Sharpe = " + str(sharpass)

print(textv)

