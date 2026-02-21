# prompt_ui.py
from dash import html, dcc
import dash_bootstrap_components as dbc

layout = dbc.Card(
    [
        dbc.CardBody(
            [
                html.Div(
                    className="panel-head",
                    children=[
                        html.H4("Query Studio", className="panel-title"),
                        html.P("Describe the team, player, metric, and season you want to analyze.", className="panel-subtitle"),
                    ],
                ),
                html.Label("Your Question", htmlFor="query-input", className="query-label"),
                dcc.Textarea(
                    id="query-input",
                    placeholder="e.g. Compare Arsenal and Liverpool expected goals over the last 3 seasons",
                    className="query-textarea mb-3",
                ),
                dbc.Button("Analyze Query", id="submit-query", className="analyze-btn w-100"),
                html.Div(id="query-feedback", className="query-feedback mt-3"),
            ],
            className="panel-body",
        ),
    ],
    className="panel-card query-card h-100",
)
