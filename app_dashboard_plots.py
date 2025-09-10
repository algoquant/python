# A shiny app for a 3x3 dashboard of random plotly plots
# If the user clicks on any of the plots then enlarge it
# Run the app from the terminal with the following command:
#   shiny run --reload --launch-browser app_dashboard_plots.py


from shiny import App, reactive, render, ui
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import random
from datetime import datetime, timedelta

app_ui = ui.page_fluid(
    ui.h1("Interactive Time Series Dashboard", class_="text-center mb-4"),
    
    ui.row(
        ui.column(12,
            ui.input_action_button("refresh", "Generate New Time Series", class_="btn-primary mb-3")
        )
    ),
    
    # 3x3 grid of plots
    ui.row(
        ui.column(4, ui.card(ui.output_plot("plot1", height="300px", click=True))),
        ui.column(4, ui.card(ui.output_plot("plot2", height="300px", click=True))),
        ui.column(4, ui.card(ui.output_plot("plot3", height="300px", click=True)))
    ),
    ui.row(
        ui.column(4, ui.card(ui.output_plot("plot4", height="300px", click=True))),
        ui.column(4, ui.card(ui.output_plot("plot5", height="300px", click=True))),
        ui.column(4, ui.card(ui.output_plot("plot6", height="300px", click=True)))
    ),
    ui.row(
        ui.column(4, ui.card(ui.output_plot("plot7", height="300px", click=True))),
        ui.column(4, ui.card(ui.output_plot("plot8", height="300px", click=True))),
        ui.column(4, ui.card(ui.output_plot("plot9", height="300px", click=True)))
    ),
    
    # Enlarged plot section
    ui.row(
        ui.column(12,
            ui.card(
                ui.card_header(
                    ui.h4(ui.output_text("enlarged_title")),
                    ui.input_action_button("hide_enlarged", "Hide Enlarged Plot", class_="btn-secondary")
                ),
                ui.output_plot("enlarged_plot", height="500px")
            )
        )
    )
)

def server(input, output, session):
    # Reactive value to trigger plot regeneration
    plot_trigger = reactive.value(1)
    
    # Track which plot is currently enlarged
    enlarged_plot_id = reactive.value(None)
    
    # Function to generate time series data
    def generate_time_series_plot(plot_id, large=False):
        random.seed(plot_id * 42 + plot_trigger())
        np.random.seed(plot_id * 42 + plot_trigger())
        
        # Different time series patterns
        series_types = ["trend", "seasonal", "random_walk", "volatile", "cyclical", "exponential"]
        series_type = random.choice(series_types)
        
        figsize = (12, 8) if large else (4, 3)
        fig, ax = plt.subplots(figsize=figsize)
        
        # Generate time range
        n_points = random.randint(100, 365)
        start_date = datetime.now() - timedelta(days=n_points)
        dates = pd.date_range(start=start_date, periods=n_points, freq='D')
        
        if series_type == "trend":
            # Linear trend with noise
            trend = np.linspace(random.randint(10, 50), random.randint(80, 150), n_points)
            noise = np.random.normal(0, random.uniform(2, 8), n_points)
            values = trend + noise
            title = f"Trend Series {plot_id}"
            color = 'blue'
            
        elif series_type == "seasonal":
            # Seasonal pattern
            base_value = random.randint(30, 70)
            seasonal = 20 * np.sin(2 * np.pi * np.arange(n_points) / 30)  # 30-day cycle
            trend = np.linspace(0, random.randint(10, 30), n_points)
            noise = np.random.normal(0, 3, n_points)
            values = base_value + seasonal + trend + noise
            title = f"Seasonal Series {plot_id}"
            color = 'green'
            
        elif series_type == "random_walk":
            # Random walk
            steps = np.random.normal(0, random.uniform(1, 3), n_points)
            values = np.cumsum(steps) + random.randint(20, 80)
            title = f"Random Walk {plot_id}"
            color = 'red'
            
        elif series_type == "volatile":
            # High volatility series
            base = random.randint(40, 80)
            volatility = random.uniform(10, 25)
            values = base + np.random.normal(0, volatility, n_points)
            title = f"Volatile Series {plot_id}"
            color = 'purple'
            
        elif series_type == "cyclical":
            # Multiple cycles
            base_value = random.randint(30, 70)
            cycle1 = 15 * np.sin(2 * np.pi * np.arange(n_points) / 50)
            cycle2 = 8 * np.cos(2 * np.pi * np.arange(n_points) / 20)
            noise = np.random.normal(0, 4, n_points)
            values = base_value + cycle1 + cycle2 + noise
            title = f"Cyclical Series {plot_id}"
            color = 'orange'
            
        else:  # exponential
            # Exponential growth/decay
            growth_rate = random.uniform(-0.01, 0.02)
            base = random.randint(10, 50)
            values = base * np.exp(growth_rate * np.arange(n_points))
            noise = np.random.normal(1, 0.1, n_points)
            values = values * noise
            title = f"Exponential Series {plot_id}"
            color = 'brown'
        
        # Plot the time series
        ax.plot(dates, values, color=color, linewidth=3 if large else 2, alpha=0.8)
        
        # Add some styling
        ax.set_title(title, fontsize=18 if large else 12, fontweight='bold')
        ax.set_xlabel("Date", fontsize=14 if large else 10)
        ax.set_ylabel("Value", fontsize=14 if large else 10)
        
        # Format x-axis
        if large:
            ax.tick_params(axis='x', labelsize=12, rotation=45)
            ax.tick_params(axis='y', labelsize=12)
        else:
            ax.tick_params(axis='x', labelsize=8, rotation=45)
            ax.tick_params(axis='y', labelsize=8)
        
        # Add grid
        ax.grid(True, alpha=0.3)
        
        # Add some statistical info for large plots
        if large:
            mean_val = np.mean(values)
            std_val = np.std(values)
            ax.axhline(y=mean_val, color='gray', linestyle='--', alpha=0.7, linewidth=1)
            ax.text(0.02, 0.98, f'Mean: {mean_val:.2f}\nStd: {std_val:.2f}', 
                   transform=ax.transAxes, verticalalignment='top',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
                   fontsize=12)
        
        plt.tight_layout()
        return fig
    
    # Regenerate plots when refresh button is clicked
    @reactive.effect
    @reactive.event(input.refresh)
    def _():
        plot_trigger.set(plot_trigger() + 1)
        enlarged_plot_id.set(None)
    
    # Hide enlarged plot
    @reactive.effect
    @reactive.event(input.hide_enlarged)
    def _():
        enlarged_plot_id.set(None)
    
    # Generate all 9 plots
    @render.plot
    def plot1():
        return generate_time_series_plot(1)
    
    @render.plot
    def plot2():
        return generate_time_series_plot(2)
    
    @render.plot
    def plot3():
        return generate_time_series_plot(3)
    
    @render.plot
    def plot4():
        return generate_time_series_plot(4)
    
    @render.plot
    def plot5():
        return generate_time_series_plot(5)
    
    @render.plot
    def plot6():
        return generate_time_series_plot(6)
    
    @render.plot
    def plot7():
        return generate_time_series_plot(7)
    
    @render.plot
    def plot8():
        return generate_time_series_plot(8)
    
    @render.plot
    def plot9():
        return generate_time_series_plot(9)
    
    # Handle clicks on plots
    @reactive.effect
    @reactive.event(input.plot1_click)
    def _():
        enlarged_plot_id.set(1)
    
    @reactive.effect
    @reactive.event(input.plot2_click)
    def _():
        enlarged_plot_id.set(2)
    
    @reactive.effect
    @reactive.event(input.plot3_click)
    def _():
        enlarged_plot_id.set(3)
    
    @reactive.effect
    @reactive.event(input.plot4_click)
    def _():
        enlarged_plot_id.set(4)
    
    @reactive.effect
    @reactive.event(input.plot5_click)
    def _():
        enlarged_plot_id.set(5)
    
    @reactive.effect
    @reactive.event(input.plot6_click)
    def _():
        enlarged_plot_id.set(6)
    
    @reactive.effect
    @reactive.event(input.plot7_click)
    def _():
        enlarged_plot_id.set(7)
    
    @reactive.effect
    @reactive.event(input.plot8_click)
    def _():
        enlarged_plot_id.set(8)
    
    @reactive.effect
    @reactive.event(input.plot9_click)
    def _():
        enlarged_plot_id.set(9)
    
    # Title for enlarged plot
    @render.text
    def enlarged_title():
        plot_id = enlarged_plot_id()
        if plot_id is not None:
            return f"Enlarged View - Time Series {plot_id} (Click on any plot above to change)"
        else:
            return "Click on any time series above to see enlarged view"
    
    # Render enlarged plot
    @render.plot
    def enlarged_plot():
        plot_id = enlarged_plot_id()
        if plot_id is not None:
            return generate_time_series_plot(plot_id, large=True)
        else:
            # Show a placeholder when no plot is selected
            fig, ax = plt.subplots(figsize=(12, 8))
            ax.text(0.5, 0.5, 'Click on any time series above to see enlarged view', 
                   horizontalalignment='center', verticalalignment='center',
                   transform=ax.transAxes, fontsize=20, alpha=0.5)
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.axis('off')
            return fig

app = App(app_ui, server)


