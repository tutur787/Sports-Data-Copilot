# FBref Metric Mapping
# Maps natural-language metric phrases to FBref table abbreviations
from rapidfuzz import process, fuzz

FBREF_METRIC_MAP = {
    # ⚽️ Goals & Assists
    "goal": "Gls",
    "goals": "Gls",
    "assist": "A",
    "assists": "A",
    "goal + assist": "G+A",
    "goals + assists": "G+A",
    "goal involvement": "G+A",
    "goal contributions": "G+A",

    # 📊 Expected metrics
    "expected goals": "xG",
    "xg": "xG",
    "non-penalty expected goals": "npxG",
    "non penalty expected goals": "npxG",
    "non-penalty xg": "npxG",
    "expected assists": "xAG",
    "expected goal assists": "xAG",
    "xag": "xAG",
    "expected goals plus expected assists": "xG+xAG",
    "expected goal involvement": "xG+xAG",
    "expected goals + expected assists": "xG+xAG",

    # 🎯 Shooting
    "shots": "Sh",
    "shots total": "Sh",
    "shots on target": "SoT",
    "shots off target": "SoOT",
    "shots inside box": "Sh In",
    "shots outside box": "Sh Out",
    "shots per 90": "Sh/90",
    "goals per 90": "G/90",
    "assists per 90": "A/90",
    "expected goals per 90": "xG/90",
    "xg per shot": "xG/Sh",

    # 📦 Passing
    "passes completed": "Cmp",
    "passes attempted": "Att",
    "pass completion %": "Cmp%",
    "pass accuracy": "Cmp%",
    "key passes": "KP",
    "progressive passes": "Prog",
    "through balls": "TB",
    "crosses": "Crs",
    "long passes": "Long",
    "short passes": "Short",
    "medium passes": "Medium",
    "passes per 90": "Passes/90",

    # 🏃‍♂️ Carrying & Dribbling
    "touches": "Touches",
    "progressive carries": "ProgC",
    "progressive carry": "ProgC",
    "carries": "Carries",
    "dribbles": "Drib",
    "dribbles completed": "DribCmp",
    "dribbles attempted": "DribAtt",
    "successful dribbles": "DribCmp",

    # 🧱 Defensive actions
    "tackles": "Tkl",
    "tackles won": "TklW",
    "interceptions": "Int",
    "blocks": "Blocks",
    "clearances": "Clr",
    "fouls committed": "Fls",
    "fouls suffered": "Fld",
    "yellow cards": "CrdY",
    "red cards": "CrdR",
    "aerial duels won": "AerWon",
    "duels won": "DuelsWon",
    "duels lost": "DuelsLost",

    # 🧤 Goalkeeping
    "saves": "Sv",
    "save percentage": "Save%",
    "save %": "Save%",
    "goals conceded": "GA",
    "clean sheets": "CS",
    "post-shot xg": "PSxG",
    "post shot xg": "PSxG",
    "expected goals against": "xGA",

    # 📈 Possession
    "possession": "Poss",
    "possession %": "Poss",
    "possession percentage": "Poss",
    "touches in final third": "Touches3rd",
    "progressive dribbles": "ProgDrib",
    "carries into box": "CarrBox",
    "passes allowed per defensive action": "PPDA",
    "ppda": "PPDA",

    # 🧮 Composite / per90 stats
    "per 90": "/90",
    "per game": "/90"
}

# club_name_map_fbref.py

# fbref_teams.py

FBREF_TEAMS = [
    # Premier League
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
    "Burnley", "Chelsea", "Crystal Palace", "Everton", "Fulham", "Leeds United",
    "Liverpool", "Manchester City", "Manchester Utd", "Newcastle Utd",
    "Nott'm Forest", "Tottenham", "West Ham", "Wolves", "Sheffield Utd",
    "Leicester City", "Southampton", "Watford", "Cardiff City",
    "Swansea City", "Hull City", "Stoke City", "West Brom",
    "QPR", "Blackburn Rovers", "Bolton Wanderers", "Wigan Athletic",
    "Sunderland", "Middlesbrough", "Derby County", "Reading", "Burnley",
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
    "Monza", "Napoli", "Salernitana", "Sassuolo", "Torino", "Udinese", "Verona", "Pisa",
    "Parma", "Cremonese", "Spezia", "Modena",

    # Ligue 1
    "Angers", "Auxerre", "Brest", "Clermont Foot", "Lens", "Lille", "Lorient",
    "Lyon", "Marseille", "Metz", "Monaco", "Montpellier", "Nantes",
    "Nice", "Paris S-G", "Reims", "Rennes", "Strasbourg", "Toulouse", "Troyes",
    "Paris FC", "Le Havre", "Guingamp", "Dijon", "Sochaux", "Ajaccio", "Bordeaux", "Nîmes", "Valenciennes"
]

def get_fbref_metric(metric_name: str) -> str | None:
    """
    Retrieve the FBref abbreviation for a given natural-language metric.
    Returns None if not found.
    """
    return FBREF_METRIC_MAP.get(metric_name.lower().strip())

def find_closest_team(user_input: str, threshold: int = 80) -> str | None:
    """
    Find the closest FBref team name to the user input using fuzzy string matching.
    Returns None if no good match is found.
    """
    user_input = user_input.strip()
    if not user_input:
        return None

    match, score, _ = process.extractOne(user_input, FBREF_TEAMS, scorer=fuzz.WRatio)
    return match if score >= threshold else None