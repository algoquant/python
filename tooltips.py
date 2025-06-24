from shiny import App, ui, reactive, render

app_ui = ui.page_fluid(
    # Add Bootstrap JS for tooltips
    ui.tags.script(src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"),
    
    ui.h1("Tooltip Examples in Shiny for Python", class_="text-center mb-4"),
    
    ui.layout_column_wrap(
        ui.card(
            ui.card_header("Basic Tooltip"),
            ui.p("Hover over the ", 
                ui.tags.span(
                    "highlighted text", 
                    style="color: blue; text-decoration: underline; cursor: help;",
                    title="This is a basic tooltip",
                    **{"data-bs-toggle": "tooltip"}
                ),
                " to see a simple tooltip."),
            class_="mb-3"
        ),
        
        ui.card(
            ui.card_header("Positioned Tooltips"),
            ui.p(
                ui.tags.span(
                    "Top tooltip", 
                    class_="btn btn-outline-primary me-2",
                    title="Tooltip on top",
                    **{"data-bs-toggle": "tooltip", "data-bs-placement": "top"}
                ),
                ui.tags.span(
                    "Right tooltip", 
                    class_="btn btn-outline-primary me-2",
                    title="Tooltip on right",
                    **{"data-bs-toggle": "tooltip", "data-bs-placement": "right"}
                ),
                ui.tags.span(
                    "Bottom tooltip", 
                    class_="btn btn-outline-primary me-2",
                    title="Tooltip on bottom",
                    **{"data-bs-toggle": "tooltip", "data-bs-placement": "bottom"}
                ),
                ui.tags.span(
                    "Left tooltip", 
                    class_="btn btn-outline-primary",
                    title="Tooltip on left",
                    **{"data-bs-toggle": "tooltip", "data-bs-placement": "left"}
                )
            ),
            class_="mb-3"
        ),
        
        cols=2
    ),
    
    ui.card(
        ui.card_header("Input with Tooltip"),
        ui.layout_column_wrap(
            ui.input_text(
                "name", 
                "Name", 
                placeholder="Enter your name",
                # help_text="Enter your full name here"
            ),
            ui.div(
                ui.input_numeric(
                    "age", 
                    ui.span(
                        "Age ",
                        ui.tags.i(
                            class_="bi bi-question-circle",
                            title="Enter your age in years",
                            **{"data-bs-toggle": "tooltip"}
                        )
                    ), 
                    value=25
                )
            ),
            cols=2
        ),
        class_="mb-3"
    ),
    
    ui.card(
        ui.card_header("Button with HTML Tooltip"),
        ui.p(
            ui.tags.button(
                "Hover for formatted tooltip",
                class_="btn btn-info",
                **{
                    "data-bs-toggle": "tooltip",
                    "data-bs-html": "true",
                    "title": "<em>Formatted</em> <u>tooltip</u> with <strong>HTML</strong>"
                }
            )
        ),
        class_="mb-3"
    ),
    
    ui.card(
        ui.card_header("Custom Tooltip Content"),
        ui.output_ui("dynamic_tooltip"),
        ui.input_action_button("update_tooltip", "Update Tooltip Content"),
        class_="mb-3"
    ),
    
    # Initialize all tooltips
    ui.tags.script("""
    document.addEventListener('DOMContentLoaded', function() {
        var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
        var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl)
        })
        
        // For reinitializing tooltips when content changes
        window.initTooltips = function() {
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
            var tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
                return new bootstrap.Tooltip(tooltipTriggerEl)
            })
        }
    });
    """)
)

def server(input, output, session):
    tooltip_count = reactive.value(0)
    
    @reactive.effect
    @reactive.event(input.update_tooltip)
    def _():
        tooltip_count.set(tooltip_count.get() + 1)
        
    @output
    @render.ui
    def dynamic_tooltip():
        count = tooltip_count.get()
        return ui.div(
            ui.tags.span(
                f"Tooltip updated {count} times. Hover here!",
                style="background-color: #f0f0f0; padding: 8px; border-radius: 4px; cursor: help;",
                title=f"This tooltip content was updated {count} times",
                **{"data-bs-toggle": "tooltip", "data-bs-placement": "top"}
            ),
            ui.tags.script("window.initTooltips();")
        )

app = App(app_ui, server)
