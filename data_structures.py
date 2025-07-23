# -*- coding: utf-8 -*-
"""
Script for manipulating data in Python.


"""

import numpy as np
import pandas as pd


## Import package for OS commands
import os

# Show current working directory
os.getcwd()
# List files in the directory
os.listtir()
# Change working directory
os.chdir("/Users/jerzy/Develop/Python/")
os.listtir()


## Strings

# https://waymoot.org/home/python_string/


## Boolean objects
# https://realpython.com/python-boolean/

# Negation
not(True)


## Lists
# https://docs.python.org/3/tutorial/datastructures.html

# Numeric list enclosed by square brackets
listt = [1, 5, 7, 9, 3]

# Boolean list
listt = [True, False, True, False, True]

# Boolean list in loop
listt = [True for x in range(11)]
listt = list(bytearray(11))

# Sum of list
sum(listt)

# Return True if all elements are True
all(listt)

# Return True if any element is True
any(listt)


# Negation of list using list comprehension loop
[not x for x in listt]


# Negation using numpy - returns numpy array
~np.array(listt)

# Negative of numpy array
-np.array(listt)


# Mixed list
listt = ["abc", 34, True, 40, "male"]

# Class of list
type(listt)
# Length of list
len(listt)
# Second list element
listt[1]


# Numeric list enclosed by square brackets

# Sequence of numbers using range
seqd = range(10, 100, 10)
# Coerce range to list
listt = list(seqd)

# Select several list elements
listt[2:5]


## List comprehension to simplify for() loops over list elements

fruits = ['apple', 'banana', 'cherry', 'kiwi', 'mango']

# Check if letter belongs in string
'a' in 'apple'

# Standard loop
# Select all fruit containing letter 'a'
letter = 'a'
newlist = []
for fruit in fruits:
  if letter in fruit:
    newlist.append(fruit)

print(newlist)


# Perform list comprehension to obtain same output as standard loop

newerlist = [fruit for fruit in fruits if 'a' in fruit]


# Note:
# The code 'a' in 'apple' produced FutureWarning
# https://stackoverflow.com/questions/40659212/futurewarning-elementwise-comparison-failed-returning-scalar-but-in-the-futur


## Compare two lists to see if they contain the same values.
# The '==' operator returns true only if the two objects are the same object 
# (i.e. if they refer to the same address in memory).

# Numeric list enclosed by square brackets
list1 = [1, 5, 7, 9, 3]
list2 = [1, 5, 7, 9, 3]

for x in list(range(len(newlist))):
  newlist[x] == newerlist[x]

outp = []




## Sets
# https://www.w3schools.com/python/python_sets.asp

# Set enclosed by curly brackets - duplicate values are ignored
setd = {'apple', 'banana', 'cherry', 'apple'}
# Set from loop over range
setd = {i for i in range(10, 61, 10)}

# Sets cannot be subset
setd[2]


## Dictionaries store key:value pairs

dictd = {'brand': 'Ford', 'model': 'Mustang', 'year': 1964}
# Check if dictd is a dictionary
isinstance(dictd, dict)

# Subset using keys
dictd['brand']
dictd['model']

# Check for key
'brando' in dictd

# Show all the keys
dictd.keys()

# Iterations
for k, v in dictd.items():
    print(k, v)


## Scripts

# Create list of symbols using map() and lambda function
# map() is similar to apply()
symbols = ['amzn', 'spy', 'bac', 'qqq']
list(map((lambda i: (i + '_ma')), symbols))
# Or explicit function
def addma(i):
  return (i + '_ma')
addma(symbols[0])
list(map(addma, symbols))


# Alternative to map(): Using list comprehension
[addma(x) for x in symbols]
# Or
[(lambda x: (x + '_ma'))(x) for x in symbols]

list(zip(symbols, '_ma'))

a = ('John', 'Charles', 'Mike')
b = ('Jenny', 'Christy', 'Monica')

x = zip(a, b)
list(x)


## Python - Magic or Dunder Methods
# Magic methods in Python are the special methods that start and end with the double underscores.



# Create a dictionary - a list of key-value pairs
dictv = {'it1': 420, 'it2': False, 'it3': 'hello'}
dictv['it1'] # First element
dictv['it2']
dictv['it3']
# Convert dictionary to a pandas Series
dictv = pd.Series(dictv)
dictv.it1 # Second element
dictv.iloc[1] # Second element

# Create an array (vector) of numpy numbers
vecc = np.arange(11, 17, 0.5)
# Convert to a list (vector) of numpy numbers
vecc = vecc.tolist()

vecc[0]  # First element
vecc[1:4]  # Elements 2, 3, 4
vecc[-1]  # Last element

# Create an array (matrix) of numpy numbers
matv = np.array([[1, 2, 3], [4, 5, 6]])
matv[1, 2]  # Output: 6
# Create a list (vector) of numpy numbers
matv = np.array([[1, 2, 3], [4, 5, 6]]).tolist()
matv[1][2]  # Output: 6

vecc.iloc[-1]  # Last element


# https://pynative.com/python-range-function/
range(11, 17)

# Create a 15x4 data frame of random integers
df = pd.DataFrame(np.random.randint(0, 10, size=(15, 4)), columns=list('ABCD'))

# Select two rows in first column
df.iloc[2:4, 0]
# Or
df.iloc[2:4, 0:1]
# Select the last column
df.iloc[:, -1]
# Select all columns except the last one
df.iloc[:, :-1]

# Select the last row
df.iloc[-1]
# Select the last two rows
df.iloc[-2:]
# Select all rows except the last one
df.iloc[:-1]

# Perform an ifelse loop
np.where(df['A'] > df['B'], df['A'], df['B'])

# Set two rows in first column to nan
df.iloc[2:4, 0] = np.nan

# Perform an locf loop forward
df.fillna(method='ffill')
# Perform an locf loop backward
df.fillna(method='bfill')

# Create a list of strings using list comprehension
coln = ['col' + str(i) for i in range(1,df.shape[1]+1)]
rown = ['row' + str(i) for i in range(1,len(df)+1)]

# Add column and row names
df.columns = coln
df.index = rown

# Write to CSV file
df.to_csv('/Users/jerzy/Develop/lecture_slides/data/pandadf.csv', index=False)


## Allocate data frame, ifelse, and locf on the data
# Use numpy arrays instead of pandas?
# https://stackoverflow.com/questions/41190852/most-efficient-way-to-forward-fill-nan-values-in-numpy-array


# Allocate a data frame with two columns filled with nan values
df = pd.DataFrame(np.nan, index=range(11, 17), columns=['A', 'B'])
# Set one cell to zero
df.iloc[3, 1] = 0


