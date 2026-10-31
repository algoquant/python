## Strategy functions

import math
import pandas as pd
import numpy as np
from utils import lagit, calc_rollsum


## Simulate the Moving Average Crossover strategy returns
def strat_movavg(closep, retp, lookb, lagv):
    # Calculate moving average stock prices
    pricema = closep.ewm(span=lookb, adjust=False).mean()
    # Calculate differences between the stock price minus the moving average
    posv = closep - pricema
    # Positions are equal to the sign of the difference
    posv = np.sign(posv)
    # Lag the positions by lagv periods
    posv = posv.shift(lagv)
    # Calculate the strategy PnLs
    return posv*retp
# end strat_movavg


## Simulate the Moving Average Crossover strategy returns - increase positions gradually
def strat_movavg2(closep, retp, lookb, lagv):
    # Calculate moving average stock prices
    pricema = closep.ewm(span=lookb, adjust=False).mean()
    # Calculate differences between the stock price minus the moving average
    indic = np.sign(closep - pricema)
    # Positions are equal to the rolling sum of the signs of the differences
    indic = calc_rollsum(indic.to_numpy(), lagv)
    posv = np.sign(indic)*(np.abs(indic) == lagv)
    # Lag the positions by 1 period
    posv = lagit(posv, 1)
    # Calculate the strategy PnLs
    return posv*retp
# end strat_movavg2


## Calculate the crossover strategy with moving average of returns
# If price exceeds MA by n standard deviations then sell.
# If price is below MA by n standard deviations then buy.

def strat_movavg3(closep, retp, lookb, numsd, lagv):
    # Calculate standard deviations
    stdev = retp.rolling(lookb).std()
    stdev[0:lookb] = 1
    # Calculate moving average stock prices
    pricema = closep.ewm(span=lookb, adjust=False).mean()
    # Calculate differences between the stock price minus the moving average
    indic = closep - pricema
    posv = pd.DataFrame(np.nan, index=range(0, retp.shape[0]), columns=['posv'])
    posv = np.where(indic > numsd*stdev, -1, posv)
    # Positions are equal to the sign of the difference
    posv = np.sign(posv)
    # Lag the positions by lagv periods
    posv = posv.shift(lagv)
    # Calculate the strategy PnLs
    return posv*retp
# end strat_movavg


