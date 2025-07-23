import pandas as pd
import numpy as np

# Read CSV file (replace with your actual file and column names)
df = pd.read_csv("/Users/jerzy/Develop/data/minutes/SPY/2025-06-20.csv", parse_dates=True, date_format="%Y-%m-%d", index_col="Index")

# Ensure the column is float
close = df["SPY.Close"].astype(float)
vwap = df["SPY.VWAP"].astype(float)
diff = close - vwap

# Calculate daily returns
# returns = close.pct_change()

# Calculate volatility (standard deviation of returns)
volatility = diff.std()

print(f"Volatility (std of daily returns): {volatility:.4f}")

