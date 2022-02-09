# Produces error:
# ImportError: cannot import name 'ParamSpec' from 'typing_extensions'

import justpy as jp

def hello_world():
    wp = jp.WebPage()
    d = jp.Div(text='Hello world!')
    wp.add(d)
    return wp

jp.justpy(hello_world)
