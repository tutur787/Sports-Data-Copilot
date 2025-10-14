from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import logging
import pandas as pd

from ai.parser import parse_prompt
from .classes.fetch_data import FetchData

app = FastAPI(title="Sports Data Copilot")

class QueryRequest(BaseModel):
    prompt: str

class QueryResponse(BaseModel):
    parsed: Dict
    data_preview: Optional[List[Dict]] = None
    
    class Config:
        arbitrary_types_allowed = True

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

@app.get("/")
async def root():
    return {"message": "Welcome to Sports Data Copilot!"}
