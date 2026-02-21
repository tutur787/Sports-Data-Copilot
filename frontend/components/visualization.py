import os
import sys

# Ensure project root is in sys.path so imports work when running from VS Code
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# visualization.py
import json
from dash import html, dcc, Output, Input, State, ctx
import dash_bootstrap_components as dbc
import plotly.io as pio
import requests
from .config import BACKEND_URL
from backend.classes.fetch_data import FetchData
from backend.classes.visualization import Visualization

layout = dbc.Card(
    [
        dbc.CardBody(
            [
                html.Div(
                    className="panel-head",
                    children=[
                        html.H4("Results", className="panel-title"),
                        html.P("Parsed query + generated charts from your selected metrics.", className="panel-subtitle"),
                    ],
                ),
                html.Div(id="stats-summary", className="mb-3"),
                dcc.Loading(
                    id="loading-chart",
                    children=html.Div(id="stat-chart"),
                    type="circle",
                    color="#0f9d8d",
                ),
            ],
            className="panel-body",
        ),
    ],
    className="panel-card results-card h-100",
)


def register_callbacks(app):
    @app.callback(
        [
            Output("adv-year-single", "disabled"),
            Output("adv-year-start", "disabled"),
            Output("adv-year-end", "disabled"),
        ],
        [Input("adv-year-mode", "value")],
    )
    def toggle_year_inputs(year_mode):
        if year_mode == "range":
            return True, False, False
        return False, True, True

    @app.callback(
        [
            Output("stats-summary", "children"),
            Output("stat-chart", "children"),
            Output("query-feedback", "children"),
            Output("toast-container", "children"),
        ],
        [Input("submit-query", "n_clicks"), Input("submit-advanced", "n_clicks")],
        [
            State("query-input", "value"),
            State("adv-league", "value"),
            State("adv-year-mode", "value"),
            State("adv-year-single", "value"),
            State("adv-year-start", "value"),
            State("adv-year-end", "value"),
            State("adv-player-input", "value"),
            State("adv-team-select", "value"),
            State("adv-stat-select", "value"),
            State("adv-viz-type", "value"),
        ],
        prevent_initial_call=True,
    )
    def handle_query(
        n_clicks_prompt,
        n_clicks_advanced,
        query,
        adv_league,
        adv_year_mode,
        adv_year_single,
        adv_year_start,
        adv_year_end,
        adv_player_input,
        adv_team_select,
        adv_stat_select,
        adv_viz_type,
    ):
        triggered = ctx.triggered_id

        try:
            if triggered == "submit-query":
                if not query:
                    return "", {}, "⚠️ Please enter a question first.", create_toast("Please enter a question.", "warning")
                res = requests.post(f"{BACKEND_URL}/query", json={"prompt": query})
            else:
                payload = {
                    "league": adv_league,
                    "year_mode": adv_year_mode,
                    "year_single": adv_year_single,
                    "year_start": adv_year_start,
                    "year_end": adv_year_end,
                    "players": adv_player_input,
                    "teams": adv_team_select if isinstance(adv_team_select, list) else [],
                    "stats": adv_stat_select if isinstance(adv_stat_select, list) else [],
                    "viz_type": adv_viz_type,
                }
                res = requests.post(f"{BACKEND_URL}/advanced-query", json=payload)
            res.raise_for_status()
            data = res.json()

            # Extract data
            parsed = data.get("parsed", {})
            print(f"Parsed data: {parsed}")
            fetcher = FetchData(parsed)
            df = fetcher.fetch_data()
            print(df.head())
            charts = Visualization(parsed).create_graph(df)

            # Normalize backend output
            if isinstance(charts, str):
                try:
                    # Try to parse a JSON array string
                    charts = json.loads(charts)
                except Exception:
                    # Split malformed concatenated JSONs if needed
                    charts = [c for c in charts.split("}") if c.strip()]
                    charts = [c + "}" if not c.endswith("}") else c for c in charts]
            elif not isinstance(charts, list):
                charts = [charts]

            if not charts:
                return html.P("No data available."), {}, "", create_toast("No data available.", "warning")

            graphs = []
            for chart in charts:
                try:
                    # Ensure we have a proper JSON string
                    chart_str = chart if isinstance(chart, str) else json.dumps(chart)
                    chart_str = chart_str.strip()

                    # Skip empty or invalid JSON
                    if not chart_str or not chart_str.startswith("{"):
                        print("⚠️ Skipping invalid chart payload:", chart_str[:50])
                        continue

                    # Try parsing into a Plotly figure
                    fig = pio.from_json(chart_str)

                    # Validate figure content before rendering
                    if not hasattr(fig, "data") or len(fig.data) == 0:
                        print("⚠️ Empty figure received, skipping.")
                        continue

                    graphs.append(dcc.Graph(figure=fig, className="chart-figure"))

                except Exception as e:
                    print(f"❌ Error loading chart: {e}")
                    # fallback visual
                    fallback = html.Div(f"Chart could not be loaded: {e}", className="chart-error")
                    graphs.append(fallback)

            if len(graphs) == 1:
                chart_output = graphs[0]
            else:
                chart_output = html.Div(graphs, className="chart-stack")

            # Summary
            summary = html.Div(
                [
                    html.H5("Parsed Query", className="summary-title"),
                    html.Pre(
                        json.dumps(parsed, indent=2),
                        className="parsed-json",
                    ),
                    html.Small(f"Previewing first {len(df)} records.", className="summary-meta"),
                ],
                className="parsed-summary",
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
        className="app-toast position-fixed top-0 end-0 m-4",
        style={"zIndex": 2000},
    )
