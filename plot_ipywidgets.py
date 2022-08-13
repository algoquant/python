# -*- coding: utf-8 -*-
"""
Script for interactive plot using ipywidgets.
https://towardsdatascience.com/interactive-graphs-in-python-830b1e6c197f
Created on Nov 17 2020
Produces static plot - not interactive.
Can't install ipywidgets on MacBook
pip3 install ipywidgets
pip3 install git+https://github.com/jupyter-widgets/ipywidgets
"""

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

