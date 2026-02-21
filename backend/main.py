from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import pandas as pd

from ai.parser import parse_prompt
from .classes.fetch_data import FetchData
from .classes.query_builder import (
    ADVANCED_LEAGUES,
    ADVANCED_VIZ_TYPES,
    build_parsed_from_advanced,
)
from .mappings.fbref_mapping import FBREF_METRIC_MAP, FBREF_TEAMS

app = FastAPI(title="Sports Data Copilot")

class QueryRequest(BaseModel):
    prompt: str

class QueryResponse(BaseModel):
    parsed: Dict
    data_preview: Optional[List[Dict]] = None
    
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
    viz_type: Optional[str] = "table"


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    try:
        parsed = parse_prompt(request.prompt)
        fetcher = FetchData(parsed)
        df = fetcher.fetch_data()
        data_preview = df.head(10).to_dict(orient="records") if df is not None else None
        return QueryResponse(parsed=parsed, data_preview=data_preview)
    except Exception as e:
        logging.error(f"Error processing query: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/advanced-query", response_model=QueryResponse)
async def advanced_query(request: AdvancedQueryRequest):
    try:
        parsed = build_parsed_from_advanced(request.model_dump())
        fetcher = FetchData(parsed)
        df = fetcher.fetch_data()
        data_preview = df.head(10).to_dict(orient="records") if df is not None else None
        return QueryResponse(parsed=parsed, data_preview=data_preview)
    except Exception as e:
        logging.error(f"Error processing advanced query: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/advanced-options")
async def advanced_options():
    return {
        "leagues": ADVANCED_LEAGUES,
        "teams": sorted(set(FBREF_TEAMS)),
        "stats": sorted(set(FBREF_METRIC_MAP.keys())),
        "viz_types": ADVANCED_VIZ_TYPES,
    }


@app.get("/")
async def root():
    return {"message": "Welcome to Sports Data Copilot!"}
