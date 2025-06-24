# -*- coding: utf-8 -*-
"""
Created on Sun Nov 29 12:37:12 2020

"""

# Get the current working directory
import os
os.getcwd()
# Change the current working directory
os.chdir("/Users/jerzy/Develop/Python")

# List files in some other directory
filev = os.listdir("/Users/jerzy/Develop/data/etfdaily/")
# Extract symbol from file name
(filev[1].split("."))[0].split("_")[0]
# Extract symbols from file names in a directory
symbolv = [(lambda x: ((x.split("."))[0].split("_")[0]))(x) for x in filev]


# Package for date and time functions
import datetime

datev = datetime.datetime.now()
print(f"Modified on {datev:%B %d, %Y}")


# Simple for loop
fruitv = ["apple", "banana", "cherry"]
for x in fruitv:
  print(x)


# Loop using map() with lambda
symbolv = ["amzn", "spy", "bac", "qqq"]
list(map((lambda i: (i + "_ma")), symbolv))

# Or using a function
def testfunc(i):
  return (i + "_ma")
testfunc(symbolv[0])
list(map(testfunc, symbolv))


# Alternative to map(): Using list comprehension

[testfunc(x) for x in symbolv]
# Or
[(lambda x: (x + "_ma"))(x) for x in symbolv]

# Zip together two lists
list(zip(symbolv, "_ma"))

a = ("John", "Charles", "Mike")
b = ("Jenny", "Christy", "Monica")

x = zip(a, b)
list(x)

# Get list of parameters of a function
# https://www.geeksforgeeks.org/how-to-get-list-of-parameters-name-from-a-function-in-python/
import inspect 
print(inspect.signature(datetime.now)) 


# Calculate the exponential moving average and standard deviation

import pandas as pd
import numpy as np

randv = pd.Series(np.random.randn(1000))
alphap = 0.2
x = randv.iloc[-2]
emav = randv.ewm(alpha=alphap).mean()
varv = (1-alphap)*randv.ewm(alpha=alphap).var(bias=True)
stdv = np.sqrt(1-alphap)*randv.ewm(alpha=alphap).std(bias=True)
# Use (1-alphap) to calculate the EMA
emav = randv.ewm(alpha=(1-alphap)).mean()
varv = alphap*randv.ewm(alpha=(1-alphap)).var(bias=True)
stdv = np.sqrt(alphap)*randv.ewm(alpha=(1-alphap)).std(bias=True)

bias = (2-alphap)/2/(1-alphap)
print(np.sqrt( bias*(1-alphap) * (varv + alphap * (x - emav)**2)), stdv)


# Calculate the exponential moving average and variance using loop and pandas

lenv = len(randv)
emal = pd.Series(np.zeros(lenv))
emal[0] = randv[0]
varl = pd.Series(np.zeros(lenv))
varl[0] = 0

for i in range(1, lenv):
    emal[i] = (randv[i] * alphap) + (emal[i - 1] * (1 - alphap))
    varl[i] = ((randv[i] - emal[i])**2 * alphap) + (varl[i - 1] * (1 - alphap))

# Use (1-alphap) to calculate the EMA
for i in range(1, lenv):
    emal[i] = (randv[i] * (1 - alphap)) + (emal[i - 1] * alphap)
    varl[i] = ((randv[i] - emal[i])**2 * (1 - alphap)) + (varl[i - 1] * alphap)


# Compare the results
np.allclose(emav.tail(100), emal.tail(100))
# Compare the variance
np.allclose(varv.tail(100), varl.tail(100))
np.allclose(stdv.tail(100), np.sqrt(varl.tail(100)))

# Plot the results using plotly
import plotly.graph_objects as go
# Create plotly line graph object from data frame
plotfig = go.Figure(go.Scatter(y=varl, name='EWMA Variance', line=dict(color='blue')))
plotfig.show()


# Calculate the exponential moving average and variance using numpy
# https://stackoverflow.com/questions/42869495/numpy-version-of-exponential-weighted-moving-average-equivalent-to-pandas-ewm

randv = np.random.randn(1000).cumsum()
alphap = 0.2
emav = randv.ewm(alpha=alphap).mean()
varv = randv.ewm(alpha=alphap).var()
stdv = randv.ewm(alpha=alphap).std()


# Calculate the exponential moving average and variance using loop and numpy

lenv = len(randv)
emal = np.zeros(lenv)
emal[0] = randv[0]
varl = np.zeros(lenv)
varl[0] = 0

for i in range(1, lenv):
    emal[i] = (randv[i] * alphap) + (emal[i - 1] * (1 - alphap))
    varl[i] = ((randv[i] - emal[i])**2 * alphap) + (varl[i - 1] * (1 - alphap))


