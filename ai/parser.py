"""
Rule-based NLP parser for sports queries.

Architecture:
- SpaCy for tokenization / entity extraction
- Regex for season and query pattern extraction
- RapidFuzz for robust team-name matching
"""

from __future__ import annotations
import re
from datetime import datetime
from typing import Any
import difflib
import spacy
from rapidfuzz import fuzz, process
from backend.mappings.fbref_mapping import FBREF_METRIC_MAP, FBREF_TEAMS

DEFAULT_METRICS = {
    "standard": ["goals", "assists", "minutes"],
    "keeper": ["saves", "clean sheets", "goals conceded"],
    "shooting": ["shots", "shots on target", "goals"],
    "passing": ["passes completed", "pass accuracy", "passes attempted"],
    "defense": ["tackles", "interceptions", "clearances"],
    "possession": ["possession %", "touches", "dribbles completed"],
}

DEFAULT_PARSE = {
    "team": None,
    "league": None,
    "player": None,
    "season": None,
    "stat_type": "standard",
    "metric": None,
    "metric_type": None,
    "chart_type": None,
    "top_n": None,          # int — limit results to top/bottom N entities
    "top_n_ascending": False,  # False = highest first, True = lowest first
}

LEAGUE_PATTERNS = {
    "Big 5 European Leagues Combined": ["big 5", "big five", "top 5 leagues", "big 5 european leagues"],
    "ENG-Premier League": ["premier league", "epl", "english premier league"],
    "ESP-La Liga": ["la liga", "laliga", "spanish league"],
    "FRA-Ligue 1": ["ligue 1", "french league"],
    "GER-Bundesliga": ["bundesliga", "german league"],
    "ITA-Serie A": ["serie a", "italian league"],
    "INT-World Cup": ["world cup", "fifa world cup"],
    "INT-Women's World Cup": ["women's world cup", "fifa women's world cup"],
    "INT-European Championship": ["euro", "euros", "european championship", "uefa european championship"],
}

DEFAULT_LEAGUE = "Big 5 European Leagues Combined"

LEAGUE_TEAM_GROUPS = {
    "ENG-Premier League": [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton", "Burnley",
        "Chelsea", "Crystal Palace", "Everton", "Fulham", "Leeds United", "Liverpool",
        "Manchester City", "Manchester Utd", "Newcastle Utd", "Nott'm Forest",
        "Tottenham", "West Ham", "Wolves", "Sheffield Utd", "Leicester City",
        "Southampton", "Watford", "Cardiff City", "Swansea City", "Hull City",
        "Stoke City", "West Brom", "QPR", "Blackburn Rovers", "Bolton Wanderers",
        "Wigan Athletic", "Sunderland", "Middlesbrough", "Derby County", "Reading",
        "Charlton Athletic", "Coventry City", "Ipswich Town", "Norwich City",
    ],
    "ESP-La Liga": [
        "Alaves", "Athletic Club", "Atletico Madrid", "Barcelona", "Celta Vigo",
        "Getafe", "Girona", "Granada", "Las Palmas", "Mallorca", "Osasuna",
        "Rayo Vallecano", "Real Betis", "Real Madrid", "Real Sociedad", "Sevilla",
        "Valencia", "Villarreal",
    ],
    "GER-Bundesliga": [
        "Augsburg", "Bayer Leverkusen", "Bayern Munich", "Bochum", "Borussia Dortmund",
        "Borussia M'gladbach", "Darmstadt 98", "Eint Frankfurt", "FC Cologne",
        "Heidenheim", "Hoffenheim", "Mainz 05", "RB Leipzig", "Union Berlin",
        "VfB Stuttgart", "Werder Bremen", "Wolfsburg", "Hamburger SV", "Köln",
        "St. Pauli", "Schalke 04", "Karlsruher SC", "Düsseldorf",
    ],
    "ITA-Serie A": [
        "AC Milan", "AS Roma", "Atalanta", "Bologna", "Cagliari", "Empoli",
        "Fiorentina", "Frosinone", "Genoa", "Inter Milan", "Juventus", "Lazio",
        "Lecce", "Monza", "Napoli", "Salernitana", "Sassuolo", "Torino", "Udinese",
        "Verona", "Pisa", "Parma", "Cremonese", "Spezia", "Modena",
    ],
    "FRA-Ligue 1": [
        "Angers", "Auxerre", "Brest", "Clermont Foot", "Lens", "Lille", "Lorient",
        "Lyon", "Marseille", "Metz", "Monaco", "Montpellier", "Nantes", "Nice",
        "Paris S-G", "Reims", "Rennes", "Strasbourg", "Toulouse", "Troyes",
        "Paris FC", "Le Havre", "Guingamp", "Dijon", "Sochaux", "Ajaccio",
        "Bordeaux", "Nîmes", "Valenciennes",
    ],
}

TEAM_TO_LEAGUE = {
    team: league
    for league, teams in LEAGUE_TEAM_GROUPS.items()
    for team in teams
}

# ── Chart-type keyword dictionaries ──────────────────────────────────────────
#
# EXPLICIT_CHART_KEYWORDS  — the user names a specific chart type.
#   These always win: no inference or override may contradict them.
#
# CONTEXTUAL_CHART_HINTS   — words that *suggest* a chart family but are not
#   explicit requests.  They are only consulted when smart shape-based inference
#   cannot make a confident decision (e.g. "distribution" → pie).
#   Checked in the order listed; first match wins.

EXPLICIT_CHART_KEYWORDS: dict[str, list[str]] = {
    "bar":      ["bar chart", "bar graph", "bar plot"],
    "line":     ["line chart", "line graph", "line plot"],
    # "scatter" alone (without "plot/chart") is also unambiguous enough to honour
    "scatter":  ["scatter plot", "scatter chart", "scatter graph", "scatter"],
    "pie":      ["pie chart", "pie graph", "donut chart"],
    "table":    ["table", "tabular", "list"],
    "heatmap":  ["heatmap", "heat map", "correlation matrix"],
    "radar":    ["radar chart", "radar plot", "spider chart", "spider web chart"],
}

CONTEXTUAL_CHART_HINTS: dict[str, list[str]] = {
    # Proportional / compositional language → pie (only valid for ≤8 entities;
    # entity-count guard is applied in _smart_chart_type).
    "pie":      ["share", "breakdown", "proportion", "percentage of", "distribution of"],
    # Time-series language → line, but ONLY when n_seasons > 1 (guard in
    # _smart_chart_type prevents a single-season "trend" query becoming a
    # one-point line chart).
    "line":     ["over time", "across seasons", "by season", "trend", "evolution", "progression"],
    # Ranking / best-of language → bar.
    # Note: "vs " and "versus" are intentionally REMOVED here — they caused
    # "goals vs xG" queries to become bar charts instead of scatter.
    "bar":      ["top ", "ranking", "ranked", "best", "worst", "highest", "lowest",
                 "most", "fewest"],
    "heatmap":  ["correlation", "correlate"],
    # Natural analyst phrasing for scatter — added alongside the explicit keywords.
    "scatter":  ["relationship between", "plotted against", "against each other"],
}

STAT_TYPE_PATTERNS = {
    "keeper": ["keeper", "goalkeeper", "goalkeeping", "save", "clean sheet", "goals conceded"],
    "shooting": ["shooting", "shots", "shot", "xg", "finishing"],
    "passing": ["passing", "pass", "assists", "key pass", "through ball"],
    "defense": ["defense", "defensive", "tackles", "interceptions", "clearances", "blocks"],
    "possession": ["possession", "touches", "dribbles", "carries"],
}

TEAM_ALIASES = {
    "manchester united": "Manchester Utd",
    "man united": "Manchester Utd",
    "man utd": "Manchester Utd",
    "manchester city": "Manchester City",
    "psg": "Paris S-G",
    "inter": "Inter Milan",
    "spurs": "Tottenham",
    "wolves": "Wolves",
    "atletico": "Atletico Madrid",
    "newcastle": "Newcastle Utd",
    "nottingham forest": "Nott'm Forest",
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

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "couple": 2,
    "few": 3,
}

PLAYER_LEADING_STOPWORDS = {
    "compare",
    "show",
    "display",
    "analyze",
    "analyse",
    "find",
    "get",
    "give",
    "prompt",
}

PLAYER_TRAILING_STOPWORDS = {
    "stat",
    "stats",
    "goal",
    "goals",
    "assist",
    "assists",
    "shot",
    "shots",
    "season",
    "seasons",
}


def _load_nlp():
    if spacy is None:  # pragma: no cover
        return None

    try:
        return spacy.load("en_core_web_sm")
    except Exception:
        nlp = spacy.blank("en")
        if "sentencizer" not in nlp.pipe_names:
            nlp.add_pipe("sentencizer")
        return nlp


NLP = _load_nlp()


class SportsQueryParser:
    def __init__(self):
        self.metric_phrases = sorted(FBREF_METRIC_MAP.keys(), key=len, reverse=True)

        imported_team_to_league: dict[str, str] = {}
        imported_team_names: list[str] = []

        if isinstance(FBREF_TEAMS, dict):
            imported_team_to_league = {
                str(team): str(league)
                for team, league in FBREF_TEAMS.items()
                if team and league
            }
            imported_team_names = list(imported_team_to_league.keys())
        else:
            imported_team_names = [str(team) for team in FBREF_TEAMS if team]

        self.team_to_league = dict(TEAM_TO_LEAGUE)
        self.team_to_league.update(imported_team_to_league)

        self.team_names = sorted(set(list(self.team_to_league.keys()) + imported_team_names))
        self.team_to_league_lower = {
            team.lower(): league
            for team, league in self.team_to_league.items()
            if league
        }

    @staticmethod
    def _normalize(text: str) -> str:
        lowered = text.lower().replace("&", " and ")
        return re.sub(r"\s+", " ", lowered).strip()

    @staticmethod
    def _as_scalar_or_list(values: list[str]) -> str | list[str] | None:
        if not values:
            return None
        if len(values) == 1:
            return values[0]
        return values

    def _extract_league(self, normalized_text: str) -> str | None:
        for league, patterns in LEAGUE_PATTERNS.items():
            if any(p in normalized_text for p in patterns):
                return league
        return None

    def _infer_league_from_teams(self, teams: list[str]) -> str | None:
        team_leagues: list[str] = []

        for team in teams:
            canonical_team = TEAM_ALIASES.get(team.lower(), team)
            league = self.team_to_league_lower.get(canonical_team.lower()) or self.team_to_league_lower.get(team.lower())
            if league:
                team_leagues.append(league)

        unique_leagues = list(dict.fromkeys(team_leagues))
        if len(unique_leagues) == 1:
            return unique_leagues[0]
        if len(unique_leagues) > 1:
            return "Big 5 European Leagues Combined"
        return None

    @staticmethod
    def _extract_explicit_chart_type(normalized_text: str) -> str | None:
        """Return a chart type only when the user names one explicitly."""
        for chart_type, keywords in EXPLICIT_CHART_KEYWORDS.items():
            if any(kw in normalized_text for kw in keywords):
                return chart_type
        return None

    @staticmethod
    def _extract_contextual_chart_hint(normalized_text: str) -> str | None:
        """Return a suggestive chart type from loose contextual keywords."""
        for chart_type, hints in CONTEXTUAL_CHART_HINTS.items():
            if any(h in normalized_text for h in hints):
                return chart_type
        return None

    @staticmethod
    def _smart_chart_type(
        normalized_text: str,
        n_seasons: int,
        n_entities: int,
        n_metrics: int,
        metric_type: str | None,
        contextual_hint: str | None,
    ) -> str:
        """
        Choose the most appropriate chart type from the *shape* of the data,
        applying sports-analytics best practices.

        Priority order (first matching rule wins):

        1.  Multi-season + league-wide           → heatmap
            (20 lines on one chart is unreadable)
        2.  Multi-season + specific entities     → line
        3.  Single season + 2 metrics + league   → scatter
            (each team/player is a dot; reveals correlations)
        4.  Single season + 2 metrics + players  → scatter
        5.  Proportional hint + ≤8 entities      → pie
            (only when data is genuinely parts-of-a-whole)
        6.  League-wide + ≥4 metrics             → heatmap
            (many teams × many metrics; bar becomes a wall)
        7.  2–4 entities + 5–8 metrics           → radar
            (profile polygon; minimum 5 axes to be meaningful)
        8.  2+ entities                          → bar
        9.  League-wide + 1–3 metrics            → bar (ranking)
        10. "trend" hint requires n_seasons > 1  → ignore if single season
        11. Other contextual hint                → honour it
        12. Default                              → table
        """
        # Convenience booleans
        is_league = metric_type == "league"
        is_player = metric_type == "player"

        # 1. Multi-season + league-wide → heatmap (teams on y-axis, seasons on x)
        #    A line chart here means 20 overlapping lines — completely unreadable.
        if n_seasons > 1 and is_league:
            return "heatmap"

        # 2. Multi-season + known entities → line (time-series trend per team)
        if n_seasons > 1:
            return "line"

        # 3. League-wide + exactly 2 metrics → scatter
        #    Classic analytics: each team as a dot on (metric_x, metric_y) plane.
        #    Reveals correlations (xG vs Goals, Shots vs xG, etc.).
        if is_league and n_metrics == 2 and n_entities == 0:
            return "scatter"

        # 4. Player context + exactly 2 metrics, no specific players named
        #    → scatter (each player is a dot).
        if is_player and n_metrics == 2 and n_entities == 0:
            return "scatter"

        # 5. Proportional / share language → pie, but ONLY when:
        #    - ≤8 entities (20-slice pie is unusable)
        #    - exactly 1 metric (pie requires a single "size" value per slice)
        share_words = {"share", "breakdown", "proportion", "percentage of", "distribution of"}
        if (
            any(w in normalized_text for w in share_words)
            and n_metrics == 1
            and (n_entities == 0 or n_entities <= 8)
            and not is_league  # league-wide with share hint → bar is cleaner
        ):
            return "pie"

        # 6. League-wide + 3+ metrics → heatmap
        #    (20 teams × 3+ metrics as grouped bars = unusable wall of colour;
        #     heatmap gives instant visual ranking across all dimensions)
        if is_league and n_metrics >= 3:
            return "heatmap"

        # 7. Radar: multi-entity profile comparison.
        #    Minimum 5 metrics so the polygon has enough axes to be meaningful
        #    (3-axis radar = triangle; 4-axis = square — both worse than bar).
        #    Cap at 4 entities: 5+ filled areas overlap too heavily.
        if 2 <= n_entities <= 3 and 5 <= n_metrics <= 8:
            return "radar"

        # 8. Multiple explicit entities → bar (grouped side-by-side)
        if n_entities >= 2:
            return "bar"

        # 9. League-wide + 1–3 metrics → bar (ranked teams on one axis)
        if is_league and n_metrics <= 3:
            return "bar"

        # 10. "trend" contextual hint is only meaningful with multiple seasons;
        #     ignore it for single-season queries (would produce a one-point line).
        if contextual_hint == "line" and n_seasons <= 1:
            contextual_hint = None

        # 10b. "correlation" heatmap hint is only meaningful when there are
        #      enough observations to form a matrix (≥3 entities OR ≥3 seasons).
        #      With 1 team + 1 season there is a single data row — a correlation
        #      matrix is mathematically undefined and visually useless.
        if contextual_hint == "heatmap" and n_entities < 3 and n_seasons < 3:
            contextual_hint = None

        # 11. Honour remaining contextual hints (top/ranking/best → bar, etc.)
        if contextual_hint:
            return contextual_hint

        # 12. Default: table — most precise fallback for single-entity lookups
        return "table"

    def _extract_metrics(self, normalized_text: str) -> list[str]:
        found: list[str] = []
        occupied_spans: list[tuple[int, int]] = []
        for phrase in self.metric_phrases:
            phrase_norm = phrase.lower().strip()
            for match in re.finditer(re.escape(phrase_norm), normalized_text):
                span = (match.start(), match.end())
                if any(not (span[1] <= s or span[0] >= e) for s, e in occupied_spans):
                    continue
                occupied_spans.append(span)
                found.append(phrase)
                break

        # Keep insertion order while deduplicating.
        return list(dict.fromkeys(found))

    def _extract_stat_type(self, normalized_text: str, metrics: list[str]) -> str:
        for stat_type, patterns in STAT_TYPE_PATTERNS.items():
            if any(p in normalized_text for p in patterns):
                return stat_type

        metric_blob = " ".join(metrics).lower()
        for token, stat_type in METRIC_TO_STAT_TYPE_HINTS.items():
            if token in metric_blob:
                return stat_type

        return "standard"

    def _extract_teams(self, normalized_text: str) -> list[str]:
        teams: list[str] = []

        # Alias-first lookup for common shorthand forms.
        for alias, canonical in TEAM_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", normalized_text):
                teams.append(canonical)

        # Exact name matches from fbref list.
        for team in self.team_names:
            if re.search(rf"\b{re.escape(team.lower())}\b", normalized_text):
                teams.append(team)

        # Fuzzy fallback on 1-4 token windows.
        words = re.findall(r"[a-z0-9']+", normalized_text)
        candidates: set[str] = set()
        for size in range(1, 5):
            for i in range(len(words) - size + 1):
                candidates.add(" ".join(words[i : i + size]))

        already_found = set(teams)
        for candidate in candidates:
            if process is not None and fuzz is not None:
                match = process.extractOne(candidate, self.team_names, scorer=fuzz.WRatio)
                if match is None:
                    continue
                team_name, score, _ = match
                if score >= 92 and team_name not in already_found:
                    teams.append(team_name)
                    already_found.add(team_name)
            else:
                closest = difflib.get_close_matches(candidate, self.team_names, n=1, cutoff=0.92)
                if closest and closest[0] not in already_found:
                    teams.append(closest[0])
                    already_found.add(closest[0])

        # Deduplicate while preserving order.
        return list(dict.fromkeys(teams))

    def _extract_players(self, prompt: str, teams: list[str]) -> list[str]:
        doc = NLP(prompt) if NLP is not None else None
        team_tokens = {t.lower() for team in teams for t in team.split()}
        known_team_names = {t.lower() for t in self.team_names}
        alias_names = set(TEAM_ALIASES.keys()) | {v.lower() for v in TEAM_ALIASES.values()}

        def is_team_name(candidate: str) -> bool:
            normalized_candidate = candidate.lower().strip()
            return normalized_candidate in known_team_names or normalized_candidate in alias_names

        def clean_player_candidate(candidate: str) -> str:
            cleaned = re.sub(r"\s+", " ", candidate).strip(" ,.;:!?")
            if not cleaned:
                return ""

            tokens = cleaned.split()
            while len(tokens) > 1 and tokens[0].lower() in PLAYER_LEADING_STOPWORDS:
                tokens = tokens[1:]

            while len(tokens) > 1 and tokens[-1].lower() in PLAYER_TRAILING_STOPWORDS:
                tokens = tokens[:-1]

            return " ".join(tokens).strip()

        players: list[str] = []

        if doc is not None and doc.ents:
            for ent in doc.ents:
                if ent.label_ != "PERSON":
                    continue
                candidate = clean_player_candidate(ent.text)
                if not candidate:
                    continue
                candidate_tokens = {t.lower() for t in candidate.split()}
                if candidate_tokens and candidate_tokens.issubset(team_tokens):
                    continue
                if is_team_name(candidate):
                    continue
                players.append(candidate)

        if not players and not teams:
            # Fallback without NER model: compare X and Y ...
            compare_match = re.search(
                r"\b[Cc]ompare\s+([A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+)?)\s+and\s+([A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+)?)",
                prompt,
            )
            if compare_match:
                for idx in (1, 2):
                    candidate = clean_player_candidate(compare_match.group(idx))
                    if candidate and not is_team_name(candidate):
                        players.append(candidate)

            # "<name>'s stats" pattern.
            poss_match = re.search(r"\b([A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+)?)'s\b", prompt)
            if poss_match:
                candidate = clean_player_candidate(poss_match.group(1))
                if candidate and not is_team_name(candidate):
                    players.append(candidate)

        return list(dict.fromkeys(players))

    @staticmethod
    def _compact_season(start_year: int, end_year: int | None = None) -> str:
        if end_year is None:
            return f"{start_year % 100:02d}"
        return f"{start_year % 100:02d}{end_year % 100:02d}"

    @staticmethod
    def _current_season_start_year() -> int:
        """
        Approximate football season boundary at July.
        Feb 2026 -> current season starts in 2025 (2025/26).
        """
        now = datetime.now()
        return now.year if now.month >= 7 else now.year - 1

    @staticmethod
    def _parse_count_token(token: str) -> int | None:
        token = token.strip().lower()
        if token.isdigit():
            return int(token)
        return NUMBER_WORDS.get(token)

    def _extract_top_n(self, normalized_text: str) -> tuple[int | None, bool]:
        """
        Extract a numeric entity limit from ranking phrases.

        Returns (n, ascending) where ascending=True means "lowest first"
        (e.g. "worst 5", "bottom 3").

        Examples
        --------
        "top 10 scorers"        → (10, False)
        "best five teams"       → (5,  False)
        "bottom 3 clubs"        → (3,  True)
        "worst 5 goalkeepers"   → (5,  True)
        "leading 8 players"     → (8,  False)
        """
        # Descending keywords: higher value = better
        desc_match = re.search(
            r'\b(?:top|best|leading|highest|most)\s+([a-z0-9]+)\b',
            normalized_text,
        )
        if desc_match:
            n = self._parse_count_token(desc_match.group(1))
            if n:
                return n, False

        # Ascending keywords: lower value = "worst"
        asc_match = re.search(
            r'\b(?:bottom|worst|lowest|fewest|least)\s+([a-z0-9]+)\b',
            normalized_text,
        )
        if asc_match:
            n = self._parse_count_token(asc_match.group(1))
            if n:
                return n, True

        return None, False

    def _extract_season(self, prompt: str, normalized_text: str) -> str | list[str] | None:
        # Formats like 2023/24 or 2023-24.
        range_matches = re.findall(r"\b(20\d{2})\s*[-/]\s*(\d{2}|\d{4})\b", prompt)
        compact_ranges: list[str] = []
        for start, end in range_matches:
            start_year = int(start)
            end_year = int(end)
            if end_year < 100:
                end_year = (start_year // 100) * 100 + end_year
            compact_ranges.append(self._compact_season(start_year, end_year))
        if compact_ranges:
            compact_ranges = list(dict.fromkeys(compact_ranges))
            return compact_ranges[0] if len(compact_ranges) == 1 else compact_ranges

        # Explicit single season years (e.g., "in 2023 season").
        # Treat 2023 as the 2023/24 season start → compact code "2324".
        year_matches = re.findall(r"\b(20\d{2})\b", prompt)
        if year_matches:
            compact_years = [self._compact_season(int(y), int(y) + 1) for y in year_matches]
            compact_years = list(dict.fromkeys(compact_years))
            return compact_years[0] if len(compact_years) == 1 else compact_years

        # Relative references.
        if "this season" in normalized_text:
            start_year = self._current_season_start_year()
            return self._compact_season(start_year, start_year + 1)
        if "last season" in normalized_text:
            start_year = self._current_season_start_year() - 1
            return self._compact_season(start_year, start_year + 1)

        span = re.search(r"(last|past)\s+([a-z0-9]+)\s+seasons?", normalized_text)
        if span:
            parsed_count = self._parse_count_token(span.group(2))
            if parsed_count is None:
                return None
            count = max(1, parsed_count)
            base_start_year = self._current_season_start_year()
            seasons = [
                self._compact_season(base_start_year - offset, base_start_year - offset + 1)
                for offset in range(count - 1, -1, -1)
            ]
            return seasons if len(seasons) > 1 else seasons[0]

        return None

    def _infer_metric_type(
        self,
        normalized_text: str,
        teams: list[str],
        players: list[str],
        league: str | None,
    ) -> str | None:
        # Only treat as a specific match query when the user explicitly asks for
        # head-to-head match data ("vs" / "against"). "compare" alone means a
        # season-stat comparison, not a single-game lookup.
        if len(teams) >= 2 and (
            " vs " in normalized_text
            or " versus " in normalized_text
            or " against " in normalized_text
        ):
            return "match"
        if len(players) > 0:
            return "player"
        if len(teams) > 0:
            return "team"
        if league or "standings" in normalized_text or "table" in normalized_text:
            return "league"
        return None

    def parse(self, prompt: str) -> dict[str, Any]:
        if not isinstance(prompt, str) or not prompt.strip():
            empty_result = dict(DEFAULT_PARSE)
            empty_result["league"] = DEFAULT_LEAGUE
            return empty_result

        # Allow debug-style input like "Prompt: Compare Messi and Ronaldo..."
        prompt = re.sub(r"^\s*prompt\s*:\s*", "", prompt, flags=re.IGNORECASE)

        normalized_text = self._normalize(prompt)
        teams = self._extract_teams(normalized_text)
        players = self._extract_players(prompt, teams)
        league_from_text = self._extract_league(normalized_text)
        league_from_team = self._infer_league_from_teams(teams)
        league = league_from_text or league_from_team
        metrics = self._extract_metrics(normalized_text)
        stat_type = self._extract_stat_type(normalized_text, metrics)
        season = self._extract_season(prompt, normalized_text)
        metric_type = self._infer_metric_type(normalized_text, teams, players, league)
        top_n, top_n_ascending = self._extract_top_n(normalized_text)

        result = dict(DEFAULT_PARSE)
        result["team"]        = self._as_scalar_or_list(teams)
        result["player"]      = self._as_scalar_or_list(players)
        result["league"]      = league or DEFAULT_LEAGUE
        result["season"]      = season
        result["stat_type"]      = stat_type
        result["metric_type"]    = metric_type
        result["top_n"]          = top_n
        result["top_n_ascending"] = top_n_ascending

        if not metrics:
            metrics = list(DEFAULT_METRICS.get(stat_type, ["all"]))
        result["metric"] = self._as_scalar_or_list(metrics)

        # ── Chart-type resolution (priority order) ────────────────────────
        #
        # P1: User explicitly names a chart type ("bar chart", "radar", …)
        #     → always respected, no further inference.
        #
        # P2: Smart shape-based inference + contextual hints
        #     → chosen when no explicit keyword is present.

        explicit = self._extract_explicit_chart_type(normalized_text)

        if explicit:
            result["chart_type"] = explicit
        else:
            n_seasons  = len(season) if isinstance(season, list) else (1 if season else 0)
            n_teams    = len(teams)   if isinstance(teams, list)  else (1 if teams   else 0)
            n_players  = len(players) if isinstance(players, list) else (1 if players else 0)
            n_entities = n_teams + n_players
            n_metrics  = len(metrics) if isinstance(metrics, list) else (1 if metrics else 0)
            contextual = self._extract_contextual_chart_hint(normalized_text)

            result["chart_type"] = self._smart_chart_type(
                normalized_text,
                n_seasons,
                n_entities,
                n_metrics,
                metric_type,
                contextual,
            )

        return result


PARSER = SportsQueryParser()


def parse_prompt(prompt: str, max_tokens: int = 200) -> dict:
    """
    Parse a natural language sports query into structured JSON fields.
    `max_tokens` is kept for backward compatibility with previous parser signature.
    """
    _ = max_tokens
    return PARSER.parse(prompt)


if __name__ == "__main__":
    examples = [
        "Show me Arsenal's expected goals in the 2023 Premier League season",
        "Compare Real Madrid and Barcelona goals in La Liga 2022/23",
        "Liverpool possession stats past 5 seasons",
        "Show me Manchester United passing stats last season",
        "Top 10 goalkeepers in Serie A 2021/22 by clean sheets",
        "Compare Messi and Ronaldo assists in 2021",
    ]

    print(f"Parser runtime year: {datetime.now().year}")
    for q in examples:
        print(f"\nPrompt: {q}")
        print(parse_prompt(q))
