import os
import sys

from dash import dcc, html
import dash_bootstrap_components as dbc

# Ensure project root is in sys.path so backend constants can be imported.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.classes.query_builder import ADVANCED_LEAGUES, ADVANCED_VIZ_TYPES
from backend.mappings.fbref_mapping import FBREF_METRIC_MAP, FBREF_TEAMS


LEAGUE_OPTIONS = [{"label": league, "value": league} for league in ADVANCED_LEAGUES]
TEAM_OPTIONS = [{"label": team, "value": team} for team in sorted(set(FBREF_TEAMS))]
STAT_OPTIONS = [{"label": stat.title(), "value": stat} for stat in sorted(set(FBREF_METRIC_MAP.keys()))]
VIZ_OPTIONS = [{"label": viz.title(), "value": viz} for viz in ADVANCED_VIZ_TYPES]


layout = dbc.Card(
    [
        dbc.CardBody(
            [
                html.Div(
                    className="panel-head",
                    children=[
                        html.H4("Structured Builder", className="panel-title"),
                        html.P(
                            "Build queries with direct controls instead of natural language prompts.",
                            className="panel-subtitle",
                        ),
                    ],
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label("League", className="query-label"),
                                dcc.Dropdown(
                                    id="adv-league",
                                    options=LEAGUE_OPTIONS,
                                    value="ENG-Premier League",
                                    clearable=False,
                                    className="advanced-dropdown",
                                ),
                            ],
                            md=12,
                        ),
                    ],
                    className="g-3",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label("Season Input Type", className="query-label"),
                                dbc.RadioItems(
                                    id="adv-year-mode",
                                    options=[
                                        {"label": "Single Year", "value": "single"},
                                        {"label": "Year Range", "value": "range"},
                                    ],
                                    value="single",
                                    inline=True,
                                    className="advanced-radio",
                                ),
                            ],
                            md=12,
                        ),
                        dbc.Col(
                            [
                                html.Label("Single Year (Season Start)", className="query-label"),
                                dbc.Input(
                                    id="adv-year-single",
                                    type="number",
                                    min=2000,
                                    max=2100,
                                    value=2023,
                                    className="advanced-input",
                                ),
                            ],
                            md=12,
                        ),
                        dbc.Col(
                            [
                                html.Label("Range Start Year", className="query-label"),
                                dbc.Input(
                                    id="adv-year-start",
                                    type="number",
                                    min=2000,
                                    max=2100,
                                    value=2021,
                                    className="advanced-input",
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                html.Label("Range End Year", className="query-label"),
                                dbc.Input(
                                    id="adv-year-end",
                                    type="number",
                                    min=2000,
                                    max=2100,
                                    value=2023,
                                    className="advanced-input",
                                ),
                            ],
                            md=6,
                        ),
                    ],
                    className="g-3 mt-1",
                ),
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label("Players (comma separated)", className="query-label"),
                                dbc.Input(
                                    id="adv-player-input",
                                    type="text",
                                    placeholder="e.g. Lionel Messi, Cristiano Ronaldo",
                                    className="advanced-input",
                                ),
                            ],
                            md=12,
                        ),
                        dbc.Col(
                            [
                                html.Label("Teams", className="query-label"),
                                dcc.Dropdown(
                                    id="adv-team-select",
                                    options=TEAM_OPTIONS,
                                    value=[],
                                    multi=True,
                                    searchable=True,
                                    placeholder="Type to search and select team(s)",
                                    className="advanced-dropdown",
                                ),
                            ],
                            md=12,
                        ),
                        dbc.Col(
                            [
                                html.Label("Stats", className="query-label"),
                                dcc.Dropdown(
                                    id="adv-stat-select",
                                    options=STAT_OPTIONS,
                                    value=["goals"],
                                    multi=True,
                                    searchable=True,
                                    placeholder="Select stat(s)",
                                    className="advanced-dropdown",
                                ),
                            ],
                            md=12,
                        ),
                        dbc.Col(
                            [
                                html.Label("Visualization Type", className="query-label"),
                                dcc.Dropdown(
                                    id="adv-viz-type",
                                    options=VIZ_OPTIONS,
                                    value="bar",
                                    clearable=False,
                                    className="advanced-dropdown",
                                ),
                            ],
                            md=12,
                        ),
                    ],
                    className="g-3 mt-1",
                ),
                dbc.Button("Run Structured Analysis", id="submit-advanced", className="analyze-btn w-100 mt-3"),
            ],
            className="panel-body",
        ),
    ],
    className="panel-card query-card h-100",
)
