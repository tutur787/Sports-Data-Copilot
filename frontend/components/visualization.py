import json
import os
import sys

# Ensure project root is in sys.path so imports work when running from VS Code
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

import requests
import plotly.io as pio
from dash import html, dcc, Output, Input, State, ctx
import dash_bootstrap_components as dbc

from .config import BACKEND_URL
from backend.mappings.fbref_mapping import (
    STAT_TYPE_METRICS,
    STAT_TYPE_DEFAULTS,
    LEAGUE_TEAMS,
    FBREF_TEAMS,
)

layout = dbc.Card(
    [
        dbc.CardBody(
            [
                html.Div(
                    className="panel-head",
                    children=[
                        html.H4("Results", className="panel-title"),
                        html.P(
                            "Charts generated from your query.",
                            className="panel-subtitle",
                        ),
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

    # ── 0. Toggle parsed query collapse ───────────────────────────────────
    @app.callback(
        [Output("parsed-collapse", "is_open"),
         Output("toggle-parsed", "children")],
        [Input("toggle-parsed", "n_clicks")],
        [State("parsed-collapse", "is_open")],
        prevent_initial_call=True,
    )
    def toggle_parsed_query(n, is_open):
        new_open = not is_open
        label = "Hide query details" if new_open else "Show query details"
        return new_open, label

    # ── 1. Toggle year inputs based on mode ───────────────────────────────
    @app.callback(
        [
            Output("adv-year-single", "disabled"),
            Output("adv-year-start",  "disabled"),
            Output("adv-year-end",    "disabled"),
        ],
        [Input("adv-year-mode", "value")],
    )
    def toggle_year_inputs(year_mode):
        if year_mode == "range":
            return True, False, False
        return False, True, True

    # ── 2. Filter teams dropdown to clubs in the selected league ──────────
    @app.callback(
        [
            Output("adv-team-select", "options"),
            Output("adv-team-select", "value"),
        ],
        [Input("adv-league", "value")],
    )
    def update_team_options(league):
        # Big 5 combined and international leagues have no fixed team list.
        teams = LEAGUE_TEAMS.get(league) or sorted(set(FBREF_TEAMS))
        options = [{"label": t, "value": t} for t in sorted(teams)]
        return options, []   # reset selection when league changes

    # ── 3. Filter stats dropdown to the chosen stat category ──────────────
    @app.callback(
        [
            Output("adv-stat-select", "options"),
            Output("adv-stat-select", "value"),
        ],
        [Input("adv-stat-type", "value")],
    )
    def update_stat_options(stat_type):
        stat_type = stat_type or "standard"
        metrics = STAT_TYPE_METRICS.get(stat_type, [])
        options = [{"label": m.title(), "value": m} for m in sorted(metrics)]
        default = STAT_TYPE_DEFAULTS.get(stat_type, metrics[:3])
        return options, default

    # ── 3. Main query handler ─────────────────────────────────────────────
    @app.callback(
        [
            Output("stats-summary",    "children"),
            Output("stat-chart",       "children"),
            Output("query-feedback",   "children"),
            Output("toast-container",  "children"),
        ],
        [Input("submit-query",    "n_clicks"),
         Input("submit-advanced", "n_clicks")],
        [
            State("query-input",      "value"),
            State("adv-league",       "value"),
            State("adv-year-mode",    "value"),
            State("adv-year-single",  "value"),
            State("adv-year-start",   "value"),
            State("adv-year-end",     "value"),
            State("adv-player-input", "value"),
            State("adv-team-select",  "value"),
            State("adv-stat-type",    "value"),   # explicit stat category
            State("adv-stat-select",  "value"),
            State("adv-viz-type",     "value"),
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
        adv_stat_type,
        adv_stat_select,
        adv_viz_type,
    ):
        triggered = ctx.triggered_id

        try:
            if triggered == "submit-query":
                if not query:
                    return (
                        "",
                        {},
                        "⚠️ Please enter a question first.",
                        create_toast("Please enter a question.", "warning"),
                    )
                res = requests.post(f"{BACKEND_URL}/query", json={"prompt": query})
            else:
                payload = {
                    "league":       adv_league,
                    "year_mode":    adv_year_mode,
                    "year_single":  adv_year_single,
                    "year_start":   adv_year_start,
                    "year_end":     adv_year_end,
                    "players":      adv_player_input,
                    "teams":        adv_team_select if isinstance(adv_team_select, list) else [],
                    "stat_type":    adv_stat_type,   # send explicit category to backend
                    "stats":        adv_stat_select  if isinstance(adv_stat_select,  list) else [],
                    "viz_type":     adv_viz_type,
                }
                res = requests.post(f"{BACKEND_URL}/advanced-query", json=payload)

            res.raise_for_status()
            data = res.json()

            parsed       = data.get("parsed", {})
            data_preview = data.get("data_preview") or []
            charts       = data.get("charts")       or []
            viz_error    = data.get("viz_error")

            summary = _build_summary(parsed, data_preview, viz_error)

            if not charts:
                msg = viz_error or "No chart data returned."
                return (
                    summary,
                    html.P(msg, className="text-muted"),
                    "",
                    create_toast(msg, "warning"),
                )

            graphs = _render_charts(charts)

            if not graphs:
                return (
                    summary,
                    html.P("Charts could not be rendered.", className="text-muted"),
                    "",
                    create_toast("Charts could not be rendered.", "warning"),
                )

            chart_output = (
                graphs[0]
                if len(graphs) == 1
                else html.Div(graphs, className="chart-stack")
            )
            return (
                summary,
                chart_output,
                "✅ Query processed successfully.",
                create_toast("Query processed successfully.", "success"),
            )

        except requests.exceptions.RequestException as exc:
            msg = f"Backend error: {exc}"
            return html.P(msg), {}, "", create_toast(msg, "danger")
        except Exception as exc:
            msg = f"Error: {exc}"
            return html.P(msg), {}, "", create_toast(msg, "danger")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _render_charts(charts: list) -> list:
    """Convert a list of Plotly JSON strings into dcc.Graph components."""
    graphs = []
    for chart in charts:
        try:
            chart_str = chart if isinstance(chart, str) else json.dumps(chart)
            chart_str = chart_str.strip()
            if not chart_str or not chart_str.startswith("{"):
                continue
            fig = pio.from_json(chart_str)
            if not hasattr(fig, "data") or len(fig.data) == 0:
                continue
            graphs.append(dcc.Graph(figure=fig, className="chart-figure"))
        except Exception as exc:
            graphs.append(
                html.Div(f"Chart could not be loaded: {exc}", className="chart-error")
            )
    return graphs


def _build_summary(parsed: dict, data_preview: list, viz_error: str | None = None) -> html.Div:
    children = []

    if viz_error:
        children.append(
            dbc.Alert(f"⚠️ {viz_error}", color="warning", className="mb-2 py-2")
        )

    record_label = f"{len(data_preview)} row{'s' if len(data_preview) != 1 else ''} returned"

    children.append(
        html.Div(
            className="parsed-summary",
            children=[
                # Header row: record count + toggle button
                html.Div(
                    className="parsed-summary-header",
                    children=[
                        html.Small(record_label, className="summary-meta"),
                        dbc.Button(
                            "Show query details",
                            id="toggle-parsed",
                            size="sm",
                            color="link",
                            className="parsed-toggle-btn",
                            n_clicks=0,
                        ),
                    ],
                ),
                # Collapsible parsed JSON — hidden by default
                dbc.Collapse(
                    html.Pre(json.dumps(parsed, indent=2), className="parsed-json mt-2"),
                    id="parsed-collapse",
                    is_open=False,
                ),
            ],
        )
    )
    return html.Div(children)


def create_toast(message: str, color: str):
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
