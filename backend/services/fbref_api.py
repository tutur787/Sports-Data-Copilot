"""
fbref_api.py — FBRef data access layer using soccerdata package.
"""
import backend.mappings.fbref_mapping as fbm
import soccerdata as sd

def get_league_table(league: str = "ENG-Premier League", season: str = "2324"):
    """Return the league table for a given season."""
    fb = sd.FotMob(leagues=[league], seasons=[season] if isinstance(season, str) else [str(s) for s in season])
    df = fb.read_league_table()
    df = df.reset_index()
    return df

def get_team_stats(league: str = "ENG-Premier League", season: str = "2324", stat_type: str = "standard", team: str = None):
    """Return team-level season stats."""
    fb = sd.FBref(leagues=[league], seasons=[season] if isinstance(season, str) else [str(s) for s in season])
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
    fb = sd.FBref(leagues=[league], seasons=[season] if isinstance(season, str) else [str(s) for s in season])
    df = fb.read_player_season_stats(stat_type=stat_type)
    df = df.reset_index()
    if player:
        if isinstance(player, str):
            df = df[df["player"].str.contains(player, case=False)]
        elif isinstance(player, list):
            df = df[df["player"].isin(player)]
    return df

def get_match_stats(
    league: str = "ENG-Premier League",
    season: str = "2324",
    stat_type: str = "summary",
    team1: str = None,
    team2: str = None,
    player: bool = False
):
    """Return match-level stats for a specific game."""
    fb = sd.FBref(leagues=[league], seasons=[season] if isinstance(season, str) else [str(s) for s in season])
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