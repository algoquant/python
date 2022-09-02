# -*- coding: utf-8 -*-
"""
Created on Sun Nov 29 12:37:12 2020

"""

# Using map()
symbolv = ['amzn', 'spy', 'bac', 'qqq']
list(map((lambda i: (i + '_ma')), symbolv))

# Or
def testfunc(i):
  return (i + '_ma')

testfunc(symbolv[0])
list(map(testfunc, symbolv))


# Alternative to map(): Using list comprehension

[testfunc(x) for x in symbolv]
# Or
[(lambda x: (x + '_ma'))(x) for x in symbolv]

list(zip(symbolv, '_ma'))

a = ("John", "Charles", "Mike")
b = ("Jenny", "Christy", "Monica")

x = zip(a, b)
list(x)
