# -*- coding: utf-8 -*-
"""
Created on Sun Nov 29 12:37:12 2020

"""

# Using map()
sym_bols = ['amzn', 'spy', 'bac', 'qqq']
list(map((lambda i: (i + '_ma')), sym_bols))

# Or
def myfunc(i):
  return (i + '_ma')

myfunc(sym_bols[0])
list(map(myfunc, sym_bols))


# Alternative to map(): Using list comprehension

[myfunc(x) for x in sym_bols]
# Or
[(lambda x: (x + '_ma'))(x) for x in sym_bols]

list(zip(sym_bols, '_ma'))

a = ("John", "Charles", "Mike")
b = ("Jenny", "Christy", "Monica")

x = zip(a, b)
list(x)
