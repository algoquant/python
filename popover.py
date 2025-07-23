from shiny import App, ui

app_ui = ui.page_fluid(
    ui.popover(
        ui.input_action_button("btn", "Click me"),
        "This is the popover content!",
        id="btn_popover"
    ) # end popover
)

def server(input, output, session):
    pass

app = App(app_ui, server)
