import os
import sys

from dash import dcc, html
import dash_bootstrap_components as dbc

# Ensure project root is in sys.path so backend constants can be imported.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.classes.query_builder import ADVANCED_LEAGUES, ADVANCED_VIZ_TYPES
from backend.mappings.fbref_mapping import (
    FBREF_TEAMS,
    LEAGUE_TEAMS,
    STAT_TYPE_METRICS,
    STAT_TYPE_DEFAULTS,
)


LEAGUE_OPTIONS = [{"label": league, "value": league} for league in ADVANCED_LEAGUES]
VIZ_OPTIONS    = [{"label": viz.title(), "value": viz} for viz in ADVANCED_VIZ_TYPES]

# Initial team options match the default league (ENG-Premier League).
_DEFAULT_LEAGUE = "ENG-Premier League"
_INITIAL_TEAM_OPTIONS = [
    {"label": t, "value": t}
    for t in sorted(LEAGUE_TEAMS.get(_DEFAULT_LEAGUE, FBREF_TEAMS))
]

# Stat-type selector options — descriptive labels so the user knows what each
# category contains before they expand the stats dropdown.
STAT_TYPE_OPTIONS = [
    {"label": "Standard        —  Goals, xG, Cards, Progression",       "value": "standard"},
    {"label": "Shooting        —  Shots, SoT, xG/Shot",                 "value": "shooting"},
    {"label": "Passing         —  Passes, Key Passes, Completion %",     "value": "passing"},
    {"label": "Passing Types   —  Crosses, Free Kicks, Corners",         "value": "passing_types"},
    {"label": "Shot Creation   —  SCA, GCA, Key Passes",                 "value": "goal_shot_creation"},
    {"label": "Defense         —  Tackles, Interceptions, Blocks",       "value": "defense"},
    {"label": "Possession      —  Touches, Carries, Dribbles",           "value": "possession"},
    {"label": "Playing Time    —  Minutes, Starts, Games",               "value": "playing_time"},
    {"label": "Goalkeeping     —  Saves, Clean Sheets, xGA",             "value": "keeper"},
    {"label": "Goalkeeping Adv —  Post-Shot xG, PSxG/SoT",              "value": "keeper_adv"},
    {"label": "Miscellaneous   —  Cards, Fouls, Offsides, PKs",         "value": "misc"},
]

# Initial options and default value shown before any callback fires (standard).
_INITIAL_STAT_TYPE = "standard"
_INITIAL_STAT_OPTIONS = [
    {"label": m.title(), "value": m}
    for m in sorted(STAT_TYPE_METRICS[_INITIAL_STAT_TYPE])
]
_INITIAL_STAT_VALUE = STAT_TYPE_DEFAULTS[_INITIAL_STAT_TYPE]


layout = dbc.Card(
    [
        dbc.CardBody(
            [
                html.Div(
                    className="panel-head",
                    children=[
                        html.H4("Query Builder", className="panel-title"),
                        html.P(
                            "Pick a league, season, teams or players, and the stats you want to visualize.",
                            className="panel-subtitle",
                        ),
                    ],
                ),

                # ── League ────────────────────────────────────────────────
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

                # ── Season ────────────────────────────────────────────────
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label("Season", className="query-label"),
                                dbc.RadioItems(
                                    id="adv-year-mode",
                                    options=[
                                        {"label": "Single season", "value": "single"},
                                        {"label": "Season range", "value": "range"},
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
                                html.Label("Season start year", className="query-label"),
                                dbc.Input(
                                    id="adv-year-single",
                                    type="number",
                                    min=2000, max=2100, value=2023,
                                    placeholder="e.g. 2023 → 2023/24",
                                    className="advanced-input",
                                ),
                            ],
                            md=12,
                        ),
                        dbc.Col(
                            [
                                html.Label("From", className="query-label"),
                                dbc.Input(
                                    id="adv-year-start",
                                    type="number",
                                    min=2000, max=2100, value=2021,
                                    className="advanced-input",
                                ),
                            ],
                            md=6,
                        ),
                        dbc.Col(
                            [
                                html.Label("To", className="query-label"),
                                dbc.Input(
                                    id="adv-year-end",
                                    type="number",
                                    min=2000, max=2100, value=2023,
                                    className="advanced-input",
                                ),
                            ],
                            md=6,
                        ),
                    ],
                    className="g-3 mt-1",
                ),

                # ── Players / Teams ───────────────────────────────────────
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label("Players", className="query-label"),
                                dbc.Input(
                                    id="adv-player-input",
                                    type="text",
                                    placeholder="Comma-separated — e.g. Messi, Ronaldo",
                                    className="advanced-input",
                                ),
                            ],
                            md=12,
                        ),
                        dbc.Col(
                            [
                                html.Label("Teams", className="query-label"),
                                html.P("Filtered to the selected league.", className="query-hint"),
                                dcc.Dropdown(
                                    id="adv-team-select",
                                    options=_INITIAL_TEAM_OPTIONS,
                                    value=[],
                                    multi=True,
                                    searchable=True,
                                    placeholder="Type to search and select team(s)",
                                    className="advanced-dropdown",
                                ),
                            ],
                            md=12,
                        ),
                    ],
                    className="g-3 mt-1",
                ),

                # ── Stat category + Stats ─────────────────────────────────
                dbc.Row(
                    [
                        dbc.Col(
                            [
                                html.Label("Stat Category", className="query-label"),
                                html.P("Metrics update automatically when you change this.", className="query-hint"),
                                dcc.Dropdown(
                                    id="adv-stat-type",
                                    options=STAT_TYPE_OPTIONS,
                                    value=_INITIAL_STAT_TYPE,
                                    clearable=False,
                                    className="advanced-dropdown",
                                ),
                            ],
                            md=12,
                        ),
                        dbc.Col(
                            [
                                html.Label("Metrics", className="query-label"),
                                dcc.Dropdown(
                                    id="adv-stat-select",
                                    options=_INITIAL_STAT_OPTIONS,
                                    value=_INITIAL_STAT_VALUE,
                                    multi=True,
                                    searchable=True,
                                    placeholder="Select one or more metrics",
                                    className="advanced-dropdown",
                                ),
                            ],
                            md=12,
                        ),
                    ],
                    className="g-3 mt-1",
                ),

                # ── Visualization type ────────────────────────────────────
                dbc.Row(
                    [
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

                dbc.Button(
                    "Run Analysis",
                    id="submit-advanced",
                    className="analyze-btn w-100 mt-3",
                ),
            ],
            className="panel-body",
        ),
    ],
    className="panel-card query-card h-100",
)
