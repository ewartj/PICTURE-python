"""Pydantic schemas for analytics API requests and responses.

These are the stable contracts between the backend and the React frontend.
Adding a new analytics method = add a new Request/Response pair here.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

class AnalysisMetaSchema(BaseModel):
    cohorts: list[str]
    cohort_sizes: dict[str, int]
    n_events: int


class AnalysisResponseBase(BaseModel):
    """Every analytics response includes a table, a plotly figure JSON, and meta."""
    table: list[dict[str, Any]]
    plot: str                   # plotly figure serialised with fig.to_json()
    meta: dict[str, Any]


# ---------------------------------------------------------------------------
# Frequency Analysis
# ---------------------------------------------------------------------------

class FrequencyRequest(BaseModel):
    data_dir: str
    rdv: str = "dia"
    event_col: str
    cohort_definitions: list[dict[str, Any]] = Field(default_factory=list)
    n_max: Optional[int] = None
    value: Literal["frequency", "count"] = "frequency"


class FrequencyResponse(AnalysisResponseBase):
    pass


# ---------------------------------------------------------------------------
# Distribution Analysis  (stub — implement in core/analytics/distribution.py)
# ---------------------------------------------------------------------------

class DistributionRequest(BaseModel):
    data_dir: str
    rdv: str
    col: str
    cohort_definitions: list[dict[str, Any]] = Field(default_factory=list)
    n_max: Optional[int] = None


class DistributionResponse(AnalysisResponseBase):
    pass


# ---------------------------------------------------------------------------
# Data endpoint schemas
# ---------------------------------------------------------------------------

class RdvListResponse(BaseModel):
    available: list[str]   # RDV names found in data_dir


class RdvInfoResponse(BaseModel):
    name: str
    label: str
    n_rows: int
    columns: list[str]
