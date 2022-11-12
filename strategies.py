## Strategy functions

import math
import pandas as pd
import numpy as np
from utils import lagit, calc_rollsum


## Calculate the moving average strategy returns
def strat_movavg(closep, retsp, lookback, lagv):
    # Calculate moving average stock prices
    pricema = closep.ewm(span=lookback, adjust=False).mean()
    # Calculate differences between the stock prices and the moving average
    posit = closep - pricema
    # Positions are equal to the sign of the differences
    posit = np.sign(posit)
    # Lag the positions by lagv periods
    posit = posit.shift(lagv)
    # Calculate the strategy returns
    return posit*retsp
# end strat_movavg


## Calculate the moving average strategy returns - increase positions gradually
def strat_movavg2(closep, retsp, lookback, lagv):
    # Calculate moving average stock prices
    pricema = closep.ewm(span=lookback, adjust=False).mean()
    # Calculate differences between the stock prices and the moving average
    indic = np.sign(closep - pricema)
    # Positions are equal to the sign of the differences
    posit = calc_rollsum(indic.to_numpy(), lagv)
    # Lag the positions by 1 period
    posit = lagit(posit, 1)
    # Calculate the strategy returns
    return posit*retsp/lagv
# end strat_movavg2

