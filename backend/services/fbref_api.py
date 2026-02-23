"""
fbref_api.py — FBRef data access layer using soccerdata package.
"""
import re

import backend.mappings.fbref_mapping as fbm
import pandas as pd
import soccerdata as sd

BIG5_LEAGUES = [
    "ENG-Premier League",
    "ESP-La Liga",
    "FRA-Ligue 1",
    "GER-Bundesliga",
    "ITA-Serie A",
]


def _normalize_one_season(value):
    """
    Normalize internal season values to soccerdata-compatible formats.
    Accepted by soccerdata (examples): '16-17', 2016, '2016-17', [14, 15, 16].
    """
    if value is None:
        return None

    if isinstance(value, int):
        return value

    text = str(value).strip()
    if not text:
        return None

    # Already valid season strings.
    if re.fullmatch(r"\d{2}-\d{2}", text) or re.fullmatch(r"\d{4}-\d{2}", text):
        return text

    # e.g. 2023/24 or 2023-24 -> 23-24
    match = re.fullmatch(r"(20\d{2})[/-](\d{2}|20\d{2})", text)
    if match:
        start_year = int(match.group(1))
        end_part = match.group(2)
        end_two_digits = int(end_part[-2:])
        return f"{start_year % 100:02d}-{end_two_digits:02d}"

    # Compact parser format: 2324 -> 23-24, 2122 -> 21-22
    if re.fullmatch(r"\d{4}", text):
        as_year = int(text)
        if 1900 <= as_year <= 2100:
            return as_year
        return f"{text[:2]}-{text[2:]}"

    # Two-digit season/year code: "23" -> 23
    if re.fullmatch(r"\d{2}", text):
        return int(text)

    return text


def _normalize_seasons(season):
    """
    Return season(s) as a list in formats soccerdata accepts.
    """
    if isinstance(season, (list, tuple, set)):
        normalized = [_normalize_one_season(s) for s in season]
    else:
        normalized = [_normalize_one_season(season)]

    normalized = [s for s in normalized if s is not None]
    return normalized or ["25-26"]


def _filter_player_df(df: pd.DataFrame, player: str | list | None) -> pd.DataFrame:
    if player is None:
        return df
    if isinstance(player, str):
        return df[df["player"].str.contains(player, case=False, na=False)]
    if isinstance(player, list):
        wanted = [p for p in player if isinstance(p, str) and p.strip()]
        if not wanted:
            return df
        pattern = "|".join(re.escape(p) for p in wanted)
        return df[df["player"].str.contains(pattern, case=False, na=False)]
    return df


def _player_search_leagues(league: str | None) -> list[str]:
    if not league or league == "Big 5 European Leagues Combined":
        return list(BIG5_LEAGUES)

    leagues = [league]
    for lg in BIG5_LEAGUES:
        if lg != league:
            leagues.append(lg)
    return leagues


def get_league_table(league: str = "ENG-Premier League", season: str = "2526"):
    """Return the league table for a given season."""
    fb = sd.FotMob(leagues=[league], seasons=_normalize_seasons(season))
    df = fb.read_league_table()
    df = df.reset_index()
    return df

def get_team_stats(league: str = "ENG-Premier League", season: str = "2526", stat_type: str = "standard", team: str = None):
    """Return team-level season stats."""
    fb = sd.FBref(leagues=[league], seasons=_normalize_seasons(season))
    df = fb.read_team_season_stats(stat_type=stat_type)
    df = df.reset_index()
    if team:
        team = fbm.find_closest_team(team) or team
        if isinstance(team, str):
            df = df[df["team"].str.contains(team, case=False)]
        elif isinstance(team, list):
            df = df[df["team"].isin(team)]
    # Drop URL column if it exists to avoid clutter
    df.drop(columns=["url"], inplace=True, errors="ignore")
    return df

def get_player_stats(league: str = "ENG-Premier League", season: str = "2324", stat_type: str = "standard", player: str = None):
    """Return player-level season stats."""
    seasons = _normalize_seasons(season)
    candidate_leagues = _player_search_leagues(league)

    # For multi-player requests, collect across leagues (players may be in different leagues).
    if isinstance(player, list):
        found_frames: list[pd.DataFrame] = []
        for lg in candidate_leagues:
            try:
                fb = sd.FBref(leagues=[lg], seasons=seasons)
                df = fb.read_player_season_stats(stat_type=stat_type).reset_index()
                filtered = _filter_player_df(df, player)
                if not filtered.empty:
                    found_frames.append(filtered)
            except Exception:
                continue

        if found_frames:
            combined = pd.concat(found_frames, ignore_index=True)
            combined = combined.drop_duplicates()
            return combined

    # For single-player (or no player), try requested league first then fallback leagues.
    last_df = pd.DataFrame()
    for lg in candidate_leagues:
        try:
            fb = sd.FBref(leagues=[lg], seasons=seasons)
            df = fb.read_player_season_stats(stat_type=stat_type).reset_index()
            last_df = df
            filtered = _filter_player_df(df, player)
            if not filtered.empty:
                return filtered
        except Exception:
            continue

    # Preserve previous behavior shape: return a dataframe even when no match is found.
    return _filter_player_df(last_df, player)

def get_match_stats(
    league: str = "ENG-Premier League",
    season: str = "2324",
    stat_type: str = "summary",
    team1: str = None,
    team2: str = None,
    player: bool = False
):
    """Return match-level stats for a specific game."""
    fb = sd.FBref(leagues=[league], seasons=_normalize_seasons(season))
    epl_schedule = fb.read_schedule()

    # Optional: reset index for easier viewing/debugging
    epl_schedule_reset = epl_schedule.reset_index()

    if team1 and team2:
        team1 = fbm.find_closest_team(team1) or team1
        team2 = fbm.find_closest_team(team2) or team2
        mask = (
            ((epl_schedule_reset["home_team"].str.contains(team1, case=False)) &
             (epl_schedule_reset["away_team"].str.contains(team2, case=False)))
            |
            ((epl_schedule_reset["home_team"].str.contains(team2, case=False)) &
             (epl_schedule_reset["away_team"].str.contains(team1, case=False)))
        )

        match_row = epl_schedule_reset[mask]

        if not match_row.empty:
            match_id = match_row.iloc[0]["game_id"]

            if player:
                df = fb.read_player_match_stats(stat_type=stat_type, match_id=match_id)
                df = df.reset_index()
                return df
            else:
                df = fb.read_team_match_stats(stat_type=stat_type, match_id=match_id)
                df = df.reset_index()
                return df
        else:
            return None
    return None
