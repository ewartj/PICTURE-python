"""Pydantic schemas for analytics API requests and responses.

These are the stable contracts between the backend and the React frontend.
Adding a new analytics method = add a new Request/Response pair here.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Error response
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Standard error envelope returned by all endpoints on 4xx/5xx."""

    detail: str


# ---------------------------------------------------------------------------
# Shared response base
# ---------------------------------------------------------------------------


class AnalysisResponseBase(BaseModel):
    """Every analytics response includes a table, a Plotly figure JSON, and meta.

    ``meta`` is typed as ``dict[str, Any]`` because each analysis adds its own
    fields (event_col, cohorts, etc.) on top of the common ones.
    """

    table: list[dict[str, Any]]
    plot: str  # Plotly figure serialised with fig.to_json()
    meta: dict[str, Any]


# ---------------------------------------------------------------------------
# Frequency Analysis
# ---------------------------------------------------------------------------


class FrequencyRequest(BaseModel):
    rdv: str = Field("dia", min_length=1)
    event_col: str = Field(..., min_length=1)
    cohort_definitions: list[dict[str, Any]] = Field(default_factory=list)
    n_max: Optional[int] = Field(None, gt=0)
    value: Literal["frequency", "count"] = "frequency"

    @field_validator("rdv", "event_col")
    @classmethod
    def no_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class FrequencyResponse(AnalysisResponseBase):
    pass


# ---------------------------------------------------------------------------
# Event Count
# ---------------------------------------------------------------------------


class EventCountRequest(BaseModel):
    rdv: str = Field(..., min_length=1)
    event_col: str = Field(..., min_length=1)
    cohort_definitions: list[dict[str, Any]] = Field(default_factory=list)
    count_unique: bool = True
    n_max: Optional[int] = Field(None, gt=0)

    @field_validator("rdv", "event_col")
    @classmethod
    def no_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class EventCountResponse(AnalysisResponseBase):
    pass


# ---------------------------------------------------------------------------
# Event Time Analysis
# ---------------------------------------------------------------------------


class EventTimeRequest(BaseModel):
    rdv: str = Field(..., min_length=1)
    event_col: str = Field(..., min_length=1)
    cohort_definitions: list[dict[str, Any]] = Field(default_factory=list)
    plot_type: Literal["boxplot", "histogram"] = "boxplot"
    log_scale: bool = False
    n_max: Optional[int] = Field(None, gt=0)

    @field_validator("rdv", "event_col")
    @classmethod
    def no_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class EventTimeResponse(BaseModel):
    """EventTime returns ``summary`` (not ``table``) to match to_dict()."""

    summary: list[dict[str, Any]]
    plot: str
    meta: dict[str, Any]


# ---------------------------------------------------------------------------
# Categorical Ratios
# ---------------------------------------------------------------------------


class CategoricalRatiosRequest(BaseModel):
    rdv: str = Field(..., min_length=1)
    col: str = Field(..., min_length=1)
    cohort_definitions: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("rdv", "col")
    @classmethod
    def no_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("must not be blank")
        return v


class CategoricalRatiosResponse(AnalysisResponseBase):
    pass


# ---------------------------------------------------------------------------
# Cohort Characteristics
# ---------------------------------------------------------------------------


class CohortCharacteristicsRequest(BaseModel):
    cohort_definitions: list[dict[str, Any]] = Field(default_factory=list)


class CohortCharacteristicsResponse(AnalysisResponseBase):
    pass


# ---------------------------------------------------------------------------
# Data endpoint schemas
# ---------------------------------------------------------------------------


class RdvListResponse(BaseModel):
    available: list[str]


class RdvInfoResponse(BaseModel):
    name: str
    label: str
    n_rows: int
    columns: list[str]
