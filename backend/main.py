import logging
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ai.parser import parse_prompt
from .classes.fetch_data import FetchData
from .classes.query_builder import (
    ADVANCED_LEAGUES,
    ADVANCED_VIZ_TYPES,
    build_parsed_from_advanced,
)
from .classes.visualization import Visualization
from .mappings.fbref_mapping import (
    FBREF_METRIC_MAP,
    FBREF_TEAMS,
    STAT_TYPE_METRICS,
    STAT_TYPE_DEFAULTS,
)

app = FastAPI(title="Sports Data Copilot")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    prompt: str


class QueryResponse(BaseModel):
    parsed: Dict[str, Any]
    data_preview: Optional[List[Dict]] = None
    charts: Optional[List[str]] = None
    viz_error: Optional[str] = None  # surfaced when visualization fails

    class Config:
        arbitrary_types_allowed = True


class AdvancedQueryRequest(BaseModel):
    league: Optional[str] = None
    year_mode: Optional[str] = "single"
    year_single: Optional[int] = None
    year_start: Optional[int] = None
    year_end: Optional[int] = None
    players: Optional[str] = None
    teams: Optional[List[str]] = None
    stats: Optional[List[str]] = None
    stat_type: Optional[str] = None   # explicit stat category from UI
    viz_type: Optional[str] = "table"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_response(parsed: dict, df: Optional[pd.DataFrame]) -> QueryResponse:
    """Build data preview + charts and return a complete QueryResponse."""
    data_preview: Optional[List[Dict]] = None
    charts: Optional[List[str]] = None
    viz_error: Optional[str] = None

    if df is not None and not df.empty:
        try:
            data_preview = df.head(10).to_dict(orient="records")
        except Exception:
            data_preview = None

        try:
            charts = Visualization(parsed).create_graph(df)
        except Exception as exc:
            viz_error = str(exc)
            logger.warning("Visualization failed: %s", exc)
    elif df is not None and df.empty:
        viz_error = "No data found for this query. Try a different season, league, or team name."

    return QueryResponse(
        parsed=parsed,
        data_preview=data_preview,
        charts=charts,
        viz_error=viz_error,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    try:
        parsed = parse_prompt(request.prompt)
        df = FetchData(parsed).fetch_data()
        return _build_response(parsed, df)
    except Exception as exc:
        logger.error("Error in /query: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/advanced-query", response_model=QueryResponse)
async def advanced_query(request: AdvancedQueryRequest):
    try:
        parsed = build_parsed_from_advanced(request.model_dump())
        df = FetchData(parsed).fetch_data()
        return _build_response(parsed, df)
    except Exception as exc:
        logger.error("Error in /advanced-query: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/advanced-options")
async def advanced_options():
    return {
        "leagues": ADVANCED_LEAGUES,
        "teams": sorted(set(FBREF_TEAMS)),
        "stats_by_type": STAT_TYPE_METRICS,
        "stat_type_defaults": STAT_TYPE_DEFAULTS,
        "viz_types": ADVANCED_VIZ_TYPES,
    }


@app.get("/")
async def root():
    return {"message": "Welcome to Sports Data Copilot!"}
