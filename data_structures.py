# -*- coding: utf-8 -*-
"""
Script for manipulating data in Python.


"""

## Import package for OS commands
import os

# Show current working directory
os.getcwd()
# List files in the directory
os.listdir()
# Change working directory
os.chdir("/Users/jerzy/Develop/python/scripts")
os.listdir()


## Strings

# https://waymoot.org/home/python_string/


## Boolean objects
# https://realpython.com/python-boolean/

# Negation
not(True)


## Lists
# https://docs.python.org/3/tutorial/datastructures.html

# Numeric list enclosed by square brackets
listd = [1, 5, 7, 9, 3]

# Boolean list
listd = [True, False, True, False, True]

# Boolean list in loop
listd = [True for x in range(11)]
listd = list(bytearray(11))

# Sum of list
sum(listd)

# Return True if all elements are True
all(listd)

# Return True if any element is True
any(listd)


# Negation of list using list comprehension loop
[not x for x in listd]

# Negation using numpy - returns numpy array
import numpy
~numpy.array(listd)


# Mixed list
listd = ["abc", 34, True, 40, "male"]

# Class of list
type(listd)
# Length of list
len(listd)
# Second list element
listd[1]

# Numeric list enclosed by square brackets

# Sequence of numbers using range
seqd = range(10, 100, 10)
# Coerce range to list
listd = list(seqd)

# Select several list elements
listd[2:5]


## List comprehension to simplify for loops over list elements

fruits = ["apple", "banana", "cherry", "kiwi", "mango"]

# Check if letter belongs in string
"a" in "apple"

# Standard loop
# Select all fruit containing letter "a"
letter = "a"
newlist = []
for fruit in fruits:
  if letter in fruit:
    newlist.append(fruit)

print(newlist)


# Perform list comprehension to obtain same output as standard loop

newerlist = [fruit for fruit in fruits if "a" in fruit]


# Note:
# The code "a" in "apple" produced FutureWarning
# https://stackoverflow.com/questions/40659212/futurewarning-elementwise-comparison-failed-returning-scalar-but-in-the-futur


## Compare two lists to see if they contain the same values.
# The "==" operator returns true only if the two objects are the same object 
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
setd = {"apple", "banana", "cherry", "apple"}
# Set from loop over range
setd = {i for i in range(10, 61, 10)}

# Sets cannot be subset
setd[2]


## Dictionaries store key:value pairs

dictd = {"brand": "Ford", "model": "Mustang", "year": 1964}

# Subset using keys
dictd["brand"]
dictd["model"]

# Check for key
"brando" in dictd

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

a = ("John", "Charles", "Mike")
b = ("Jenny", "Christy", "Monica")

x = zip(a, b)
list(x)


## Python - Magic or Dunder Methods
# Magic methods in Python are the special methods that start and end with the double underscores.


