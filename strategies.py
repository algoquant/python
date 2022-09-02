## Strategy functions

import pandas as pd
import numpy as np


## Calculate the strategy returns
def run_movavg(closep, returnts, lookback):
    # Calculate moving average stock prices
    pricema = closep.ewm(span=lookback, adjust=False).mean()
    # Calculate differences between the stock prices and the moving average
    posit = closep - pricema
    # Positions are equal to the sign of the differences
    posit = posit.apply(np.sign)
    # Lag the positions by 1 period
    posit = posit.shift(1)
    # Calculate the cumulative strategy returns
    strategy_returns = posit*returnts
    return strategy_returns.cumsum()
# end run_movavg


