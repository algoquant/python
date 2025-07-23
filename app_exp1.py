# Shiny Express example
# https://shiny.posit.co/blog/posts/shiny-express/

# Run this Shiny app in VS Code by clicking the "Run" button in the top right corner of the editor.
#
# Or in a terminal run:
# shiny run --reload --launch-browser /Users/jerzy/Develop/Python/app_exp1.py

from shiny.express import input, render, ui

ui.input_text("namev", "What's your name?", value="Jerzy")

@render.text
def greetfun():
    return f"Hello, {input.namev()}!"
