from __future__ import annotations

from typing import Any

import backend.mappings.fbref_mapping as fbm


ADVANCED_LEAGUES = [
    "Big 5 European Leagues Combined",
    "ENG-Premier League",
    "ESP-La Liga",
    "FRA-Ligue 1",
    "GER-Bundesliga",
    "ITA-Serie A",
    "INT-World Cup",
    "INT-Women's World Cup",
    "INT-European Championship",
]

ADVANCED_VIZ_TYPES = ["bar", "line", "scatter", "pie", "table", "heatmap", "radar"]

DEFAULT_METRICS = {
    "standard": ["goals", "assists", "minutes"],
    "keeper": ["saves", "clean sheets", "goals conceded"],
    "shooting": ["shots", "shots on target", "goals"],
    "passing": ["passes completed", "pass accuracy", "passes attempted"],
    "defense": ["tackles", "interceptions", "clearances"],
    "possession": ["possession %", "touches", "dribbles completed"],
}

METRIC_TO_STAT_TYPE_HINTS = {
    "xg": "shooting",
    "expected goals": "shooting",
    "shots on target": "shooting",
    "shots": "shooting",
    "shot": "shooting",
    "save": "keeper",
    "clean sheet": "keeper",
    "passes": "passing",
    "pass": "passing",
    "assist": "passing",
    "tackles": "defense",
    "interceptions": "defense",
    "clearances": "defense",
    "possession": "possession",
    "touches": "possession",
    "dribble": "possession",
}


def _as_scalar_or_list(values: list[str]) -> str | list[str] | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return values


def _parse_players(players: str | None) -> list[str]:
    if not players:
        return []
    split_players = [p.strip() for p in players.split(",")]
    return [p for p in split_players if p]


def _parse_teams(teams: list[str] | str | None) -> list[str]:
    if teams is None:
        return []
    if isinstance(teams, str):
        candidates = [teams]
    else:
        candidates = [t for t in teams if t]

    normalized: list[str] = []
    for team in candidates:
        closest = fbm.find_closest_team(team) or team
        normalized.append(closest)
    return list(dict.fromkeys(normalized))


def _infer_stat_type(metrics: list[str]) -> str:
    metric_blob = " ".join(metrics).lower()
    for token, stat_type in METRIC_TO_STAT_TYPE_HINTS.items():
        if token in metric_blob:
            return stat_type
    return "standard"


def _year_to_season_code(year: int) -> str:
    # Treat input as season start year: 2023 -> 2324.
    return f"{year % 100:02d}{(year + 1) % 100:02d}"


def _normalize_season(
    year_mode: str | None,
    year_single: int | None,
    year_start: int | None,
    year_end: int | None,
) -> str | list[str] | None:
    if year_mode == "single":
        if year_single is None:
            return None
        return _year_to_season_code(int(year_single))

    if year_mode == "range":
        if year_start is None or year_end is None:
            return None
        start = int(year_start)
        end = int(year_end)
        if end < start:
            start, end = end, start
        seasons = [_year_to_season_code(y) for y in range(start, end + 1)]
        if len(seasons) == 1:
            return seasons[0]
        return seasons

    # Fallback if mode was not set but a single year was provided.
    if year_single is not None:
        return _year_to_season_code(int(year_single))

    return None


def build_parsed_from_advanced(payload: dict[str, Any]) -> dict[str, Any]:
    league = payload.get("league") or "ENG-Premier League"
    year_mode = payload.get("year_mode") or "single"
    year_single = payload.get("year_single")
    year_start = payload.get("year_start")
    year_end = payload.get("year_end")
    players = _parse_players(payload.get("players"))
    teams = _parse_teams(payload.get("teams"))

    metrics_input = payload.get("stats")
    if isinstance(metrics_input, str):
        metrics = [metrics_input] if metrics_input else []
    elif isinstance(metrics_input, list):
        metrics = [m for m in metrics_input if isinstance(m, str) and m.strip()]
    else:
        metrics = []

    stat_type = _infer_stat_type(metrics)
    if not metrics:
        metrics = DEFAULT_METRICS.get(stat_type, ["all"])

    if players:
        metric_type = "player"
    elif teams:
        metric_type = "team"
    else:
        metric_type = "league"

    return {
        "team": _as_scalar_or_list(teams),
        "league": league,
        "player": _as_scalar_or_list(players),
        "season": _normalize_season(year_mode, year_single, year_start, year_end),
        "stat_type": stat_type,
        "metric": _as_scalar_or_list(metrics),
        "metric_type": metric_type,
        "chart_type": (payload.get("viz_type") or "table").lower(),
    }
