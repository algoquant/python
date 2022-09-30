
import datetime
import pandas as pd
import numpy as np

from utils import calc_rollsum, get_symbol, calc_sharpe

foo = np.ones(21)
bar = calc_rollsum(foo, 5)

print(bar.size)
print(np.where(bar >= 5, 1, 0))
