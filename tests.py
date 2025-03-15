# -*- coding: utf-8 -*-
"""
Created on Sun Nov 29 12:37:12 2020

"""
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


