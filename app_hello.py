# Run the app in terminal:
# shiny run --reload --launch-browser /Users/jerzy/Develop/Python/app_hello.py

from shiny import App, ui, render

app_ui = ui.page_fluid(
    ui.input_text("name", "What's your name?", value="World"),
    ui.output_text("greeting"),
)

def server(input, output, session):
    @render.text
    def greeting():
        return f"Hello, {input.name()}!"

app = App(app_ui, server)
