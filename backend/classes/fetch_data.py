from backend.services.fbref_api import get_league_table, get_team_stats, get_player_stats, get_match_stats
import backend.mappings.fbref_mapping as fbm
import pandas as pd

class FetchData:
    def __init__(self, parsed: dict):
        """
        Initialize the FetchData object with a parsed query dictionary.
        """
        self.parsed = parsed
        self.team = parsed.get("team")
        self.league = parsed.get("league") or "ENG-Premier League"
        self.season = parsed.get("season") or "2324"
        self.metric = parsed.get("metric")
        self.metric_type = parsed.get("metric_type")
        self.player = parsed.get("player")
        self.stat_type = parsed.get("stat_type") or "standard"

    def fetch_data(self):
        """
        Routes the request to the correct function based on parsed query fields.
        """
        if isinstance(self.team, list) and len(self.team) == 2 and self.metric_type == "match":
            self.team[0] = fbm.find_closest_team(self.team[0]) or self.team[0]
            self.team[1] = fbm.find_closest_team(self.team[1]) or self.team[1]
            return get_match_stats(league=self.league, season=self.season, team1=self.team[0], team2=self.team[1])

        elif self.player and self.metric_type == "player":
            return get_player_stats(
                league=self.league,
                season=self.season,
                stat_type=self.stat_type,
                player=self.player if isinstance(self.player, str) else self.player
            )

        elif self.metric_type == "team":
            if isinstance(self.team, list):
                teams = [fbm.find_closest_team(t) or t for t in self.team]
                return pd.concat([
                    get_team_stats(
                        league=self.league,
                        season=self.season,
                        stat_type=self.stat_type,
                        team=t
                    ) for t in teams
                ], ignore_index=True)
            else:
                team = fbm.find_closest_team(self.team) or self.team
                return get_team_stats(
                    league=self.league,
                    season=self.season,
                    stat_type=self.stat_type,
                    team=team if isinstance(team, str) else team
                )

        else:
            return get_league_table(league=self.league, season=self.season)
