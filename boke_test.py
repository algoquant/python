# -*- coding: utf-8 -*-
"""
Created on Mon Nov 16 16:12:55 2020

@author: Jerzy
"""

# Standard imports 

from bokeh.io import output_notebook, show
output_notebook()

# Create and deploy interactive data applications

from IPython.display import IFrame
IFrame('https://demo.bokeh.org/sliders', width=900, height=500)
