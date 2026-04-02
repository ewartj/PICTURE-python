"""
FastAPI application entry point.

Run with:
    uvicorn api.main:app --reload --port 8000

Interactive docs:
    http://localhost:8000/docs
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import analytics, apps, cohorts, data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
)

app = FastAPI(
    title="PICTURE Analytics API",
    description=(
        "Clinical analytics platform — Python port of the R PICTURE system. "
        "This API will be consumed by the React frontend."
    ),
    version="0.1.0",
)

# Allow the Streamlit UI (and eventually React dev server) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(apps.router)
app.include_router(data.router)
app.include_router(cohorts.router)
app.include_router(analytics.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}
