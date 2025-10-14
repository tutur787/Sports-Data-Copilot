# prompt_ui.py
from dash import html, dcc
import dash_bootstrap_components as dbc

layout = dbc.Card(
    [
        dbc.CardHeader("Ask Your Football Analytics Question"),
        dbc.CardBody(
            [
                dcc.Textarea(
                    id="query-input",
                    placeholder="e.g. Show me Arsenal's passing stats for last season",
                    style={"width": "100%", "height": "120px", "resize": "none"},
                    className="mb-3",
                ),
                dbc.Button("Analyze", id="submit-query", color="primary", className="w-100"),
                html.Div(id="query-feedback", className="mt-3"),
            ]
        ),
    ],
    className="shadow-lg bg-dark text-light rounded-4",
)