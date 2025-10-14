# app.py
from dash import Dash, html, dcc
import dash_bootstrap_components as dbc
from components.prompt_ui import layout as prompt_layout
from components.visualization import layout as viz_layout, register_callbacks

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.SLATE],  # sleek modern dark theme
    suppress_callback_exceptions=True,
    title="Sports Analytics Copilot"
)

# Toast placeholder for notifications
toast_container = html.Div(id="toast-container")

# App layout
app.layout = dbc.Container(
    [
        html.H2("⚽ Sports Analytics Copilot", className="text-center mt-4 mb-2"),
        html.Hr(),
        dbc.Row(
            [
                dbc.Col(prompt_layout, width=4, className="mt-3"),
                dbc.Col(viz_layout, width=8, className="mt-3"),
            ],
            className="g-3",
        ),
        toast_container,
    ],
    fluid=True,
)

# Register callbacks
register_callbacks(app)

server = app.server

if __name__ == "__main__":
    app.run_server(debug=True, port=8050)