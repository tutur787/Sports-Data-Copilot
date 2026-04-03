from __future__ import annotations

import logging

import pandas as pd

import backend.mappings.fbref_mapping as fbm
from backend.services.fbref_api import (
    get_league_table,
    get_match_stats,
    get_player_stats,
    get_team_stats,
)


class FetchData:
    def __init__(self, parsed: dict):
        self.parsed = parsed
        self.team = parsed.get("team")
        self.league = parsed.get("league") or "ENG-Premier League"
        self.season = parsed.get("season") or "2526"
        self.metric = parsed.get("metric")
        self.metric_type = parsed.get("metric_type")
        self.player = parsed.get("player")
        self.stat_type = parsed.get("stat_type") or "standard"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_data(self) -> pd.DataFrame:
        """Route the request to the correct FBRef function."""
        teams = self._teams_list()

        # Head-to-head match query (explicit "vs" / "against" in original prompt)
        if self.metric_type == "match" and len(teams) == 2:
            result = self._fetch_match(teams[0], teams[1])
            if result is not None and not result.empty:
                return result
            # Graceful fallback: return season team stats when no match is found
            logging.warning(
                "Match not found for %s vs %s — falling back to team season stats.",
                teams[0],
                teams[1],
            )
            return self._fetch_team_stats(teams)

        # Player stats
        if self.player or self.metric_type == "player":
            return get_player_stats(
                league=self.league,
                season=self.season,
                stat_type=self.stat_type,
                player=self.player,
            ) or pd.DataFrame()

        # Team stats (explicit type, or teams present but type unknown)
        if teams or self.metric_type == "team":
            return self._fetch_team_stats(teams)

        # League table / standings
        result = get_league_table(league=self.league, season=self.season)
        return result if result is not None else pd.DataFrame()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _teams_list(self) -> list[str]:
        if isinstance(self.team, list):
            return [t for t in self.team if t]
        if isinstance(self.team, str) and self.team:
            return [self.team]
        return []

    def _fetch_match(self, team1: str, team2: str) -> pd.DataFrame | None:
        t1 = fbm.find_closest_team(team1) or team1
        t2 = fbm.find_closest_team(team2) or team2
        return get_match_stats(
            league=self.league,
            season=self.season,
            stat_type=self.stat_type,
            team1=t1,
            team2=t2,
        )

    def _fetch_team_stats(self, teams: list[str]) -> pd.DataFrame:
        normalized = [fbm.find_closest_team(t) or t for t in teams]

        if not normalized:
            # No specific team — fetch all teams in the league
            result = get_team_stats(
                league=self.league,
                season=self.season,
                stat_type=self.stat_type,
            )
            return result if result is not None else pd.DataFrame()

        frames: list[pd.DataFrame] = []
        for team in normalized:
            df = get_team_stats(
                league=self.league,
                season=self.season,
                stat_type=self.stat_type,
                team=team,
            )
            if df is not None and not df.empty:
                frames.append(df)

        if frames:
            return pd.concat(frames, ignore_index=True)
        return pd.DataFrame()
