import os
import sys

# Ensure project root is in sys.path so imports work when running from VS Code
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# visualization.py
import json
from dash import html, dcc, Output, Input, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.io as pio
import pandas as pd
import requests
from .config import BACKEND_URL
from backend.classes.fetch_data import FetchData

layout = dbc.Card(
    [
        dbc.CardHeader("Results & Visualizations"),
        dbc.CardBody(
            [
                html.Div(id="stats-summary", className="mb-3"),
                dcc.Loading(
                    id="loading-chart",
                    children=html.Div(id="stat-chart"),
                    type="circle",
                    color="#0dcaf0",
                ),
            ]
        ),
    ],
    className="shadow-lg bg-dark text-light rounded-4",
)


def register_callbacks(app):
    @app.callback(
        [
            Output("stats-summary", "children"),
            Output("stat-chart", "children"),
            Output("query-feedback", "children"),
            Output("toast-container", "children"),
        ],
        [Input("submit-query", "n_clicks")],
        [State("query-input", "value")],
        prevent_initial_call=True,
    )
    def handle_query(n_clicks, query):
        if not query:
            return "", {}, "⚠️ Please enter a question first.", create_toast("Please enter a question.", "warning")

        try:
            res = requests.post(f"{BACKEND_URL}/query", json={"prompt": query})
            res.raise_for_status()
            data = res.json()

            # Extract data
            parsed = data.get("parsed", {})
            fetcher = FetchData(parsed)
            df = fetcher.fetch_data()
            charts = fetcher.create_graph(df)

            if not charts:
                return html.P("No data available."), {}, "", create_toast("No data available.", "warning")

            graphs = []
            for chart in charts:
                fig = pio.from_json(chart)
                graphs.append(dcc.Graph(figure=fig))

            if len(graphs) == 1:
                chart_output = graphs[0]
            else:
                chart_output = html.Div(graphs, style={"display": "flex", "flexDirection": "column", "gap": "20px"})

            # Summary
            summary = html.Div(
                [
                    html.H5(f"Parsed Query", className="mb-2"),
                    html.Pre(
                        json.dumps(parsed, indent=2),
                        style={
                            "whiteSpace": "pre-wrap",
                            "backgroundColor": "#1a1d21",
                            "padding": "10px",
                            "borderRadius": "8px",
                            "fontSize": "14px",
                        },
                    ),
                    html.Small(f"Previewing first {len(df)} records."),
                ]
            )

            feedback = "✅ Query processed successfully."
            toast = create_toast("Query processed successfully.", "success")

            return summary, chart_output, feedback, toast

        except requests.exceptions.RequestException as e:
            msg = f"Backend error: {str(e)}"
            return html.P(msg), {}, "", create_toast(msg, "danger")


def create_toast(message, color):
    """Reusable toast notification"""
    return dbc.Toast(
        message,
        header="Sports Analytics Copilot",
        icon=color,
        duration=4000,
        is_open=True,
        dismissable=True,
        className="position-fixed top-0 end-0 m-4",
        style={"zIndex": 2000},
    )