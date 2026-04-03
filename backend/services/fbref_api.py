"""
fbref_api.py — FBRef data access layer using the soccerdata package.

soccerdata FBref constructor:
    FBref(leagues, seasons, ...)
    seasons accepts: 2023 (int), '23-24', '2023-24', or a list of those.

Available read methods (confirmed from soccerdata docs):
    read_team_season_stats(stat_type)   index: [league, season, team]
    read_player_season_stats(stat_type) index: [league, season, team, player]
    read_schedule()                     index: [league, season, game]
    read_team_match_stats(stat_type, team)        index: [league, season, team, game]
    read_player_match_stats(stat_type, match_id)  index: [league, season, game, team, player]

NOTE: read_league_table does NOT exist on FBref — use read_team_season_stats("standard").
NOTE: read_team_match_stats does NOT accept match_id — filter by team, then by game.
"""

import logging
import re

import backend.mappings.fbref_mapping as fbm
import pandas as pd
import soccerdata as sd

logger = logging.getLogger(__name__)

BIG5_LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "FRA-Ligue 1",
    "GER-Bundesliga",
    "ITA-Serie A",
]

# Valid stat_type values per method (from soccerdata FBref docs).
VALID_TEAM_SEASON_STAT_TYPES = {
    "standard", "keeper", "keeper_adv", "shooting", "passing",
    "passing_types", "goal_shot_creation", "defense", "possession",
    "playing_time", "misc",
}
VALID_PLAYER_SEASON_STAT_TYPES = {
    "standard", "shooting", "passing", "passing_types", "goal_shot_creation",
    "defense", "possession", "playing_time", "misc", "keeper", "keeper_adv",
}
VALID_TEAM_MATCH_STAT_TYPES = {
    "schedule", "shooting", "keeper", "passing", "passing_types",
    "goal_shot_creation", "defense", "possession", "misc",
}
VALID_PLAYER_MATCH_STAT_TYPES = {
    "summary", "keepers", "passing", "passing_types", "defense", "possession", "misc",
}

# Map our internal stat_type names → FBref API names where they differ.
# "standard" is valid for both season and schedule purposes.
_TEAM_MATCH_STAT_TYPE_MAP = {
    "standard": "schedule",   # "standard" not valid for match stats → use "schedule"
    "keeper":   "keeper",
    "shooting": "shooting",
    "passing":  "passing",
    "defense":  "defense",
    "possession": "possession",
}


# ---------------------------------------------------------------------------
# Season normalisation
# ---------------------------------------------------------------------------

def _normalize_one_season(value):
    """
    Normalise internal season tokens to soccerdata-compatible values.

    soccerdata FBref accepts:
        - int  2023          → 2023/24 season
        - str  '23-24'       → 2023/24 season
        - str  '2023-24'     → 2023/24 season
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value  # already an integer start-year

    text = str(value).strip()
    if not text:
        return None

    # Already formatted as "23-24" or "2023-24".
    if re.fullmatch(r"\d{2}-\d{2}", text) or re.fullmatch(r"\d{4}-\d{2}", text):
        return text

    # Input like "2023/24" or "2023-24" → "23-24"
    m = re.fullmatch(r"(20\d{2})[/-](\d{2}|20\d{2})", text)
    if m:
        start = int(m.group(1))
        end_digits = int(m.group(2)[-2:])
        return f"{start % 100:02d}-{end_digits:02d}"

    # Compact parser code: "2324" → "23-24"; "2023" → 2023 (int start-year)
    if re.fullmatch(r"\d{4}", text):
        as_int = int(text)
        if 1900 <= as_int <= 2100:
            return as_int          # treat as start year integer
        return f"{text[:2]}-{text[2:]}"  # compact code like 2324 → "23-24"

    # Two-digit code "23" → 2023
    if re.fullmatch(r"\d{2}", text):
        return 2000 + int(text)

    return text


def _normalize_seasons(season) -> list:
    """Return a list of soccerdata-compatible season identifiers."""
    if isinstance(season, (list, tuple, set)):
        normalized = [_normalize_one_season(s) for s in season]
    else:
        normalized = [_normalize_one_season(season)]
    normalized = [s for s in normalized if s is not None]
    return normalized or [2025]   # default: 2025/26


# ---------------------------------------------------------------------------
# Player filtering helper
# ---------------------------------------------------------------------------

def _filter_player_df(df: pd.DataFrame, player) -> pd.DataFrame:
    """Filter DataFrame rows by player name (case-insensitive, partial match)."""
    if player is None or df.empty:
        return df

    # After reset_index(), "player" is a top-level column.
    if "player" not in df.columns:
        return df

    if isinstance(player, str):
        mask = df["player"].str.contains(player, case=False, na=False)
    elif isinstance(player, list):
        wanted = [p for p in player if isinstance(p, str) and p.strip()]
        if not wanted:
            return df
        pattern = "|".join(re.escape(p) for p in wanted)
        mask = df["player"].str.contains(pattern, case=False, na=False)
    else:
        return df

    return df[mask]


def _player_search_leagues(league: str | None) -> list[str]:
    """Return league search order for player queries (primary first, then Big5)."""
    if not league or league == "Big 5 European Leagues Combined":
        return list(BIG5_LEAGUES)
    leagues = [league]
    for lg in BIG5_LEAGUES:
        if lg != league:
            leagues.append(lg)
    return leagues


def _safe_stat_type(stat_type: str, valid_set: set, default: str) -> str:
    """Return stat_type if valid, otherwise the default."""
    if stat_type in valid_set:
        return stat_type
    logger.debug("stat_type '%s' not in valid set %s — using '%s'", stat_type, valid_set, default)
    return default


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_league_table(league: str = "ENG-Premier League", season = "2526") -> pd.DataFrame:
    """
    Return season-level team standings / stats for the given league.
    FBref has no dedicated league-table endpoint; we use read_team_season_stats
    with stat_type="standard" which includes W/D/L/GF/GA/Pts equivalents.
    """
    try:
        fb = sd.FBref(leagues=[league], seasons=_normalize_seasons(season))
        df = fb.read_team_season_stats(stat_type="standard")
        df = df.reset_index()
        df.drop(columns=["url"], inplace=True, errors="ignore")
        return df
    except Exception as exc:
        logger.error("get_league_table failed for %s %s: %s", league, season, exc)
        return pd.DataFrame()


def get_team_stats(
    league: str = "ENG-Premier League",
    season = "2526",
    stat_type: str = "standard",
    team: str | None = None,
) -> pd.DataFrame:
    """Return team-level season stats, optionally filtered to a specific team."""
    stat_type = _safe_stat_type(stat_type, VALID_TEAM_SEASON_STAT_TYPES, "standard")
    try:
        fb = sd.FBref(leagues=[league], seasons=_normalize_seasons(season))
        df = fb.read_team_season_stats(stat_type=stat_type)
        df = df.reset_index()
        df.drop(columns=["url"], inplace=True, errors="ignore")

        if team:
            canon = fbm.find_closest_team(team) or team
            if isinstance(canon, str):
                mask = df["team"].str.contains(re.escape(canon), case=False, na=False)
                df = df[mask]

        if df.empty:
            logger.warning("get_team_stats: no rows for team=%s league=%s season=%s", team, league, season)
        return df
    except Exception as exc:
        logger.error("get_team_stats failed for %s %s: %s", league, season, exc)
        return pd.DataFrame()


def get_player_stats(
    league: str = "ENG-Premier League",
    season = "2526",
    stat_type: str = "standard",
    player=None,
) -> pd.DataFrame:
    """Return player-level season stats, searching across leagues if needed."""
    stat_type = _safe_stat_type(stat_type, VALID_PLAYER_SEASON_STAT_TYPES, "standard")
    seasons = _normalize_seasons(season)
    candidate_leagues = _player_search_leagues(league)

    # Multi-player: collect rows from every league they might play in.
    if isinstance(player, list):
        frames: list[pd.DataFrame] = []
        for lg in candidate_leagues:
            try:
                fb = sd.FBref(leagues=[lg], seasons=seasons)
                df = fb.read_player_season_stats(stat_type=stat_type).reset_index()
                df.drop(columns=["url"], inplace=True, errors="ignore")
                filtered = _filter_player_df(df, player)
                if not filtered.empty:
                    frames.append(filtered)
            except Exception as exc:
                logger.debug("Player stats fetch failed for %s: %s", lg, exc)
        if frames:
            combined = pd.concat(frames, ignore_index=True).drop_duplicates()
            return combined
        logger.warning("No player data found for players=%s", player)
        return pd.DataFrame()

    # Single player: try leagues in order, return on first hit.
    for lg in candidate_leagues:
        try:
            fb = sd.FBref(leagues=[lg], seasons=seasons)
            df = fb.read_player_season_stats(stat_type=stat_type).reset_index()
            df.drop(columns=["url"], inplace=True, errors="ignore")
            filtered = _filter_player_df(df, player)
            if not filtered.empty:
                return filtered
        except Exception as exc:
            logger.debug("Player stats fetch failed for %s: %s", lg, exc)

    logger.warning("No player data found for player=%s league=%s season=%s", player, league, season)
    return pd.DataFrame()


def get_match_stats(
    league: str = "ENG-Premier League",
    season = "2526",
    stat_type: str = "schedule",
    team1: str | None = None,
    team2: str | None = None,
    player: bool = False,
) -> pd.DataFrame | None:
    """
    Return match-level stats for a specific fixture between team1 and team2.

    Strategy:
      1. Read the schedule to identify the game ID (index level 'game').
      2. For player stats: use read_player_match_stats(match_id=game_id).
      3. For team stats:   use read_team_match_stats(team=[t1,t2]) and filter
         to the specific game — read_team_match_stats does NOT accept match_id.
    """
    if not team1 or not team2:
        return None

    team1 = fbm.find_closest_team(team1) or team1
    team2 = fbm.find_closest_team(team2) or team2
    seasons = _normalize_seasons(season)

    try:
        fb = sd.FBref(leagues=[league], seasons=seasons)
        schedule = fb.read_schedule().reset_index()

        # The game identifier lives in the 'game' column (reset from index).
        if "game" not in schedule.columns:
            logger.warning("Schedule has no 'game' column; columns: %s", schedule.columns.tolist())
            return None

        home_col = "home_team" if "home_team" in schedule.columns else None
        away_col = "away_team" if "away_team" in schedule.columns else None
        if not home_col or not away_col:
            logger.warning("Schedule missing home_team/away_team columns: %s", schedule.columns.tolist())
            return None

        mask = (
            (
                schedule[home_col].str.contains(re.escape(team1), case=False, na=False) &
                schedule[away_col].str.contains(re.escape(team2), case=False, na=False)
            ) | (
                schedule[home_col].str.contains(re.escape(team2), case=False, na=False) &
                schedule[away_col].str.contains(re.escape(team1), case=False, na=False)
            )
        )
        match_rows = schedule[mask]

        if match_rows.empty:
            logger.warning("No fixture found between '%s' and '%s' in %s %s", team1, team2, league, season)
            return None

        game_id = match_rows.iloc[0]["game"]
        logger.info("Found fixture game_id=%s: %s vs %s", game_id, team1, team2)

        if player:
            # read_player_match_stats accepts match_id directly.
            match_stat_type = _safe_stat_type(
                stat_type if stat_type in VALID_PLAYER_MATCH_STAT_TYPES else "summary",
                VALID_PLAYER_MATCH_STAT_TYPES,
                "summary",
            )
            df = fb.read_player_match_stats(stat_type=match_stat_type, match_id=game_id)
            return df.reset_index()
        else:
            # read_team_match_stats does NOT accept match_id — filter by team, then game.
            match_stat_type = _TEAM_MATCH_STAT_TYPE_MAP.get(stat_type, "schedule")
            match_stat_type = _safe_stat_type(match_stat_type, VALID_TEAM_MATCH_STAT_TYPES, "schedule")
            df = fb.read_team_match_stats(
                stat_type=match_stat_type,
                team=[team1, team2],
            ).reset_index()
            # Filter to just this fixture.
            if "game" in df.columns:
                df = df[df["game"] == game_id]
            return df if not df.empty else None

    except Exception as exc:
        logger.error("get_match_stats failed for %s vs %s: %s", team1, team2, exc)
        return None
