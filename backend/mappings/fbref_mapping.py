# FBref Metric Mapping
# Maps natural-language metric phrases to FBref table column abbreviations.
from rapidfuzz import process, fuzz

FBREF_METRIC_MAP = {
    # ⚽ Goals & Assists
    # FBref uses "Gls" for goals and "Ast" for assists in all major tables.
    "goal":                                 "Gls",
    "goals":                                "Gls",
    "assist":                               "Ast",   # was "A" — FBref uses "Ast"
    "assists":                              "Ast",   # was "A" — FBref uses "Ast"
    "goal + assist":                        "G+A",
    "goals + assists":                      "G+A",
    "goal involvement":                     "G+A",
    "goal contributions":                   "G+A",

    # 📊 Expected metrics
    "expected goals":                       "xG",
    "xg":                                   "xG",
    "non-penalty expected goals":           "npxG",
    "non penalty expected goals":           "npxG",
    "non-penalty xg":                       "npxG",
    "expected assists":                     "xAG",
    "expected goal assists":                "xAG",
    "xag":                                  "xAG",
    "expected goals plus expected assists": "xG+xAG",
    "expected goal involvement":            "xG+xAG",
    "expected goals + expected assists":    "xG+xAG",

    # 🎯 Shooting  (stat_type="shooting")
    "shots":                "Sh",
    "shots total":          "Sh",
    "shots on target":      "SoT",
    "shots per 90":         "Sh/90",
    "goals per 90":         "G/90",
    "assists per 90":       "A/90",
    "expected goals per 90":"xG/90",
    "xg per shot":          "xG/Sh",

    # 📦 Passing  (stat_type="passing")
    "passes completed":     "Cmp",
    "passes attempted":     "Att",
    "pass completion %":    "Cmp%",
    "pass accuracy":        "Cmp%",
    "key passes":           "KP",
    "progressive passes":   "PrgP",
    "through balls":        "TB",
    "crosses":              "Crs",
    "long passes":          "Long",
    "short passes":         "Short",
    "medium passes":        "Medium",

    # 🏃 Carrying & Dribbling  (stat_type="possession")
    "touches":              "Touches",
    "progressive carries":  "PrgC",
    "progressive carry":    "PrgC",
    "carries":              "Carries",
    "dribbles":             "Drib",
    "dribbles completed":   "DribCmp",
    "dribbles attempted":   "DribAtt",
    "successful dribbles":  "DribCmp",

    # 🧱 Defensive actions  (stat_type="defense")
    "tackles":              "Tkl",
    "tackles won":          "TklW",
    "interceptions":        "Int",
    "blocks":               "Blocks",
    "clearances":           "Clr",
    "fouls committed":      "Fls",
    "fouls suffered":       "Fld",
    "yellow cards":         "CrdY",
    "red cards":            "CrdR",
    "aerial duels won":     "AerWon",

    # 🧤 Goalkeeping  (stat_type="keeper")
    # FBref keeper table uses "Saves" (full word), not "Sv".
    "saves":                "Saves",  # was "Sv" — FBref uses "Saves"
    "save percentage":      "Save%",
    "save %":               "Save%",
    "goals conceded":       "GA",
    "clean sheets":         "CS",
    "post-shot xg":         "PSxG",
    "post shot xg":         "PSxG",
    "expected goals against":"xGA",

    # 📈 Possession  (stat_type="possession")
    "possession":                           "Poss",
    "possession %":                         "Poss",
    "possession percentage":                "Poss",
    "touches in final third":               "Touches3rd",
    "progressive dribbles":                 "ProgDrib",
    "carries into box":                     "CPA",
    "passes allowed per defensive action":  "PPDA",
    "ppda":                                 "PPDA",

    # 🔀 Passing types  (stat_type="passing_types")
    "corner kicks":     "CK",
    "throw ins":        "TI",
    "free kicks":       "FK",
    "offsides":         "Off",
    "out of bounds":    "Out",

    # 🎯 Goal / shot creation  (stat_type="goal_shot_creation")
    "shot creating actions":    "SCA",
    "sca":                      "SCA",
    "goal creating actions":    "GCA",
    "gca":                      "GCA",

    # ⏱ Playing time  (stat_type="playing_time")
    "minutes":              "Min",
    "minutes per 90":       "Min/90",
    "games started":        "Starts",
    "games":                "MP",
    "matches played":       "MP",
    "complete matches":     "Compl",

    # 🗒 Misc  (stat_type="misc")
    "fouls committed":      "Fls",
    "fouls suffered":       "Fld",
    "offsides caught":      "Off",
    "penalty kicks won":    "PKwon",
    "penalty kicks conceded":"PKcon",
    "own goals":            "OG",
}


# ---------------------------------------------------------------------------
# STAT_TYPE_METRICS
# Maps each FBref stat_type to the subset of FBREF_METRIC_MAP keys that are
# actually present in that stat table.  Used to filter the stats dropdown in
# the advanced UI so users can only pick valid combinations.
# ---------------------------------------------------------------------------
STAT_TYPE_METRICS: dict[str, list[str]] = {
    "standard": [
        "goals", "assists",
        "goal + assist", "goals + assists", "goal involvement", "goal contributions",
        "expected goals", "xg",
        "non-penalty expected goals", "non penalty expected goals", "non-penalty xg",
        "expected assists", "expected goal assists", "xag",
        "expected goals plus expected assists", "expected goal involvement",
        "expected goals + expected assists",
        "yellow cards", "red cards",
        "progressive carries", "progressive passes",
        "goals per 90", "assists per 90", "expected goals per 90",
        "matches played", "games",
    ],
    "shooting": [
        "goals",
        "shots", "shots total", "shots on target",
        "shots per 90", "goals per 90",
        "expected goals", "xg",
        "non-penalty expected goals", "non-penalty xg",
        "xg per shot",
    ],
    "passing": [
        "passes completed", "passes attempted",
        "pass completion %", "pass accuracy",
        "key passes", "progressive passes",
        "through balls", "crosses",
        "long passes", "short passes", "medium passes",
        "assists", "expected assists", "expected goal assists", "xag",
    ],
    "passing_types": [
        "crosses", "corner kicks", "throw ins", "free kicks",
        "through balls", "offsides", "out of bounds",
        "long passes", "short passes", "medium passes",
    ],
    "goal_shot_creation": [
        "shot creating actions", "sca",
        "goal creating actions", "gca",
        "key passes", "dribbles completed", "progressive carries",
    ],
    "defense": [
        "tackles", "tackles won",
        "interceptions", "blocks", "clearances",
        "fouls committed", "fouls suffered",
        "yellow cards", "red cards",
        "aerial duels won",
    ],
    "possession": [
        "touches",
        "progressive carries", "progressive carry",
        "carries",
        "dribbles", "dribbles completed", "dribbles attempted", "successful dribbles",
        "possession", "possession %", "possession percentage",
        "touches in final third", "progressive dribbles",
        "carries into box",
        "passes allowed per defensive action", "ppda",
    ],
    "playing_time": [
        "minutes", "minutes per 90",
        "games started", "games", "matches played", "complete matches",
        "goals", "assists",
    ],
    "keeper": [
        "saves", "save percentage", "save %",
        "goals conceded", "clean sheets",
        "post-shot xg", "post shot xg",
        "expected goals against",
    ],
    "keeper_adv": [
        "saves", "save percentage", "save %",
        "post-shot xg", "post shot xg",
        "expected goals against", "goals conceded",
        "clean sheets",
    ],
    "misc": [
        "yellow cards", "red cards",
        "fouls committed", "fouls suffered",
        "aerial duels won",
        "offsides caught",
        "penalty kicks won", "penalty kicks conceded",
        "own goals",
    ],
}

# ---------------------------------------------------------------------------
# Default starting metrics shown when a stat_type is first selected.
# ---------------------------------------------------------------------------
STAT_TYPE_DEFAULTS: dict[str, list[str]] = {
    "standard":          ["goals", "assists", "expected goals"],
    "shooting":          ["shots", "shots on target", "expected goals"],
    "passing":           ["passes completed", "key passes", "pass accuracy"],
    "passing_types":     ["crosses", "through balls", "corner kicks"],
    "goal_shot_creation":["shot creating actions", "goal creating actions", "key passes"],
    "defense":           ["tackles", "interceptions", "clearances"],
    "possession":        ["touches", "dribbles completed", "carries"],
    "playing_time":      ["minutes", "games started", "matches played"],
    "keeper":            ["saves", "clean sheets", "goals conceded"],
    "keeper_adv":        ["saves", "post-shot xg", "expected goals against"],
    "misc":              ["yellow cards", "red cards", "fouls committed"],
}

# ---------------------------------------------------------------------------
# League → teams mapping (used to filter the teams dropdown by selected league)
# ---------------------------------------------------------------------------
LEAGUE_TEAMS: dict[str, list[str]] = {
    "ENG-Premier League": [
        "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
        "Burnley", "Chelsea", "Crystal Palace", "Everton", "Fulham",
        "Leeds United", "Leicester City", "Liverpool", "Manchester City",
        "Manchester Utd", "Newcastle Utd", "Nott'm Forest", "Sheffield Utd",
        "Southampton", "Tottenham", "Watford", "West Ham", "Wolves",
        "Cardiff City", "Swansea City", "Hull City", "Stoke City", "West Brom",
        "QPR", "Blackburn Rovers", "Bolton Wanderers", "Wigan Athletic",
        "Sunderland", "Middlesbrough", "Derby County", "Reading",
        "Charlton Athletic", "Coventry City", "Ipswich Town", "Norwich City",
    ],
    "ESP-La Liga": [
        "Alaves", "Athletic Club", "Atletico Madrid", "Barcelona", "Celta Vigo",
        "Getafe", "Girona", "Granada", "Las Palmas", "Mallorca", "Osasuna",
        "Rayo Vallecano", "Real Betis", "Real Madrid", "Real Sociedad",
        "Sevilla", "Valencia", "Villarreal",
    ],
    "GER-Bundesliga": [
        "Augsburg", "Bayer Leverkusen", "Bayern Munich", "Bochum",
        "Borussia Dortmund", "Borussia M'gladbach", "Darmstadt 98",
        "Eint Frankfurt", "FC Cologne", "Heidenheim", "Hoffenheim",
        "Mainz 05", "RB Leipzig", "Union Berlin", "VfB Stuttgart",
        "Werder Bremen", "Wolfsburg", "Hamburger SV", "Köln", "St. Pauli",
        "Schalke 04", "Karlsruher SC", "Düsseldorf",
    ],
    "ITA-Serie A": [
        "AC Milan", "AS Roma", "Atalanta", "Bologna", "Cagliari", "Empoli",
        "Fiorentina", "Frosinone", "Genoa", "Inter Milan", "Juventus",
        "Lazio", "Lecce", "Monza", "Napoli", "Salernitana", "Sassuolo",
        "Torino", "Udinese", "Verona", "Pisa", "Parma", "Cremonese",
        "Spezia", "Modena",
    ],
    "FRA-Ligue 1": [
        "Angers", "Auxerre", "Brest", "Clermont Foot", "Lens", "Lille",
        "Lorient", "Lyon", "Marseille", "Metz", "Monaco", "Montpellier",
        "Nantes", "Nice", "Paris S-G", "Reims", "Rennes", "Strasbourg",
        "Toulouse", "Troyes", "Paris FC", "Le Havre", "Guingamp", "Dijon",
        "Sochaux", "Ajaccio", "Bordeaux", "Nîmes", "Valenciennes",
    ],
}

# All teams across all leagues (used as the fallback / Big 5 combined list).
FBREF_TEAMS = [
    # Premier League
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
    "Burnley", "Chelsea", "Crystal Palace", "Everton", "Fulham", "Leeds United",
    "Liverpool", "Manchester City", "Manchester Utd", "Newcastle Utd",
    "Nott'm Forest", "Tottenham", "West Ham", "Wolves", "Sheffield Utd",
    "Leicester City", "Southampton", "Watford", "Cardiff City",
    "Swansea City", "Hull City", "Stoke City", "West Brom",
    "QPR", "Blackburn Rovers", "Bolton Wanderers", "Wigan Athletic",
    "Sunderland", "Middlesbrough", "Derby County", "Reading",
    "Charlton Athletic", "Coventry City", "Ipswich Town", "Norwich City",

    # La Liga
    "Alaves", "Athletic Club", "Atletico Madrid", "Barcelona", "Celta Vigo",
    "Getafe", "Girona", "Granada", "Las Palmas", "Mallorca", "Osasuna",
    "Rayo Vallecano", "Real Betis", "Real Madrid", "Real Sociedad",
    "Sevilla", "Valencia", "Villarreal",

    # Bundesliga
    "Augsburg", "Bayer Leverkusen", "Bayern Munich", "Bochum", "Borussia Dortmund",
    "Borussia M'gladbach", "Darmstadt 98", "Eint Frankfurt", "FC Cologne",
    "Heidenheim", "Hoffenheim", "Mainz 05", "RB Leipzig", "Union Berlin",
    "VfB Stuttgart", "Werder Bremen", "Wolfsburg", "Hamburger SV", "Köln", "St. Pauli",
    "Schalke 04", "Karlsruher SC", "Düsseldorf",

    # Serie A
    "AC Milan", "AS Roma", "Atalanta", "Bologna", "Cagliari", "Empoli", "Fiorentina",
    "Frosinone", "Genoa", "Inter Milan", "Juventus", "Lazio", "Lecce",
    "Monza", "Napoli", "Salernitana", "Sassuolo", "Torino", "Udinese", "Verona",
    "Pisa", "Parma", "Cremonese", "Spezia", "Modena",

    # Ligue 1
    "Angers", "Auxerre", "Brest", "Clermont Foot", "Lens", "Lille", "Lorient",
    "Lyon", "Marseille", "Metz", "Monaco", "Montpellier", "Nantes",
    "Nice", "Paris S-G", "Reims", "Rennes", "Strasbourg", "Toulouse", "Troyes",
    "Paris FC", "Le Havre", "Guingamp", "Dijon", "Sochaux", "Ajaccio",
    "Bordeaux", "Nîmes", "Valenciennes",
]


def get_fbref_metric(metric_name: str) -> str | None:
    """Return the FBref column abbreviation for a natural-language metric name."""
    return FBREF_METRIC_MAP.get(metric_name.lower().strip())


def find_closest_team(user_input: str, threshold: int = 80) -> str | None:
    """Fuzzy-match user input to the nearest canonical FBref team name."""
    user_input = user_input.strip()
    if not user_input:
        return None
    match, score, _ = process.extractOne(user_input, FBREF_TEAMS, scorer=fuzz.WRatio)
    return match if score >= threshold else None
