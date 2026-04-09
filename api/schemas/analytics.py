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
    plot: str  # plotly figure serialised with fig.to_json()
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
# Event Count
# ---------------------------------------------------------------------------


class EventCountRequest(BaseModel):
    data_dir: str
    rdv: str
    event_col: str
    cohort_definitions: list[dict[str, Any]] = Field(default_factory=list)
    count_unique: bool = True


class EventCountResponse(AnalysisResponseBase):
    pass


# ---------------------------------------------------------------------------
# Event Time Analysis
# ---------------------------------------------------------------------------


class EventTimeRequest(BaseModel):
    data_dir: str
    rdv: str
    event_col: str
    cohort_definitions: list[dict[str, Any]] = Field(default_factory=list)
    plot_type: Literal["boxplot", "histogram"] = "boxplot"
    log_scale: bool = False


class EventTimeResponse(BaseModel):
    summary: list[dict[str, Any]]
    plot: str
    meta: dict[str, Any]


# ---------------------------------------------------------------------------
# Data endpoint schemas
# ---------------------------------------------------------------------------


class RdvListResponse(BaseModel):
    available: list[str]  # RDV names found in data_dir


class RdvInfoResponse(BaseModel):
    name: str
    label: str
    n_rows: int
    columns: list[str]
