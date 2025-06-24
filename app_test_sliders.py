from shiny import App, ui, render, reactive

app_ui = ui.page_fluid(
    ui.div(
        ui.h1("My Centered Title"),
        style="display: flex; justify-content: center; margin-top: 40px; margin-bottom: 40px;"
    ),
    ui.card(
        ui.card_header("Slider Controls"),
        ui.div(
            ui.div(
                ui.input_slider("slider1", "Slider 1", min=0, max=100, value=50),
                style="width: 20%; display: inline-block; padding-left: 50px; padding-right: 15px;"
            ),
            ui.div(
                ui.input_slider("slider2", "Slider 2", min=0, max=10, value=5),
                style="width: 30%; display: inline-block;"
            ),
            style="display: flex; align-items: flex-end;"
        ),
        ui.output_text("slider_values")
    )
)

def server(input, output, session):
    @output
    @render.text
    def slider_values():
        return f"Slider 1: {input.slider1()}, Slider 2: {input.slider2()}"

app = App(app_ui, server)
