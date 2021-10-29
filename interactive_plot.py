# -*- coding: utf-8 -*-
"""
Created on Tue Nov 17 15:03:55 2020

@author: Jerzy
"""

"""
Script for interactive plot.
"""
# https://towardsdatascience.com/interactive-graphs-in-python-830b1e6c197f

import math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import figure
from ipywidgets import interact


@interact
def sinewave(c = 1):

    # Inputs, 100 evenly spaced points 0 through 2pi
    p = np.linspace(0, 2*math.pi, 100)
    # y, a set of outputs to those 100 evenly spaced points
    y = np.sin(p-c*4)
    
    plt.plot(p, y)
    plt.ylabel('sin(x)')
    plt.xlabel('x')
    plt.title('Sinwave function')
    return plt.figure()

# Produces static plot