# https://shiny.posit.co/blog/posts/shiny-express/
# In terminal run: shiny run shine1.py
# In browser open: http://127.0.0.1:8000

from shiny.express import input, render, ui

ui.input_text("name", "What's your name?", value="World")

@render.text
def greeting():
    return f"Hello, {input.name()}!"
