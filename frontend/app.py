# app.py
from dash import Dash, html
import dash_bootstrap_components as dbc
from components.prompt_ui import layout as prompt_layout
from components.visualization import layout as viz_layout, register_callbacks

app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.LUX],
    suppress_callback_exceptions=True,
    title="Sports Analytics Copilot"
)

# Toast placeholder for notifications
toast_container = html.Div(id="toast-container")

# App layout
app.layout = html.Div(
    [
        html.Div(className="bg-orb orb-a"),
        html.Div(className="bg-orb orb-b"),
        dbc.Container(
            [
                html.Header(
                    className="hero-panel mb-4",
                    children=[
                        html.Div(
                            className="hero-copy",
                            children=[
                                html.P("Sports Data Copilot", className="hero-eyebrow"),
                                html.H1("Ask Better Football Questions", className="hero-title"),
                                html.P(
                                    "Turn natural language into clear football analytics with structured parsing and instant visual output.",
                                    className="hero-subtitle",
                                ),
                            ],
                        ),
                        html.Div(
                            className="hero-stats",
                            children=[
                                html.Div([html.Span("NLP"), html.Small("Local parser")], className="stat-chip"),
                                html.Div([html.Span("FBref"), html.Small("Team + player stats")], className="stat-chip"),
                                html.Div([html.Span("Dash"), html.Small("Interactive visuals")], className="stat-chip"),
                            ],
                        ),
                    ],
                ),
                dbc.Row(
                    [
                        dbc.Col(prompt_layout, lg=4, md=12),
                        dbc.Col(viz_layout, lg=8, md=12),
                    ],
                    className="g-4 dashboard-grid",
                ),
                toast_container,
            ],
            className="page-wrap py-4 py-lg-5",
        ),
    ],
    className="app-shell",
)

# Register callbacks
register_callbacks(app)

server = app.server

if __name__ == "__main__":
    app.run(debug=True, port=8050)
