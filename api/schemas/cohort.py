"""Pydantic schemas for cohort-related API requests and responses."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class CohortFilterStepSchema(BaseModel):
    type: Literal["base", "filter", "and"] = "filter"
    rdv: Optional[str] = None
    column: Optional[str] = None
    val: Optional[list[Any]] = None
    inclusion: str = "ever"
    query_type: str = "str_matches"
    window: Optional[list[int]] = None


class CohortDefinitionSchema(BaseModel):
    label: str
    config: list[CohortFilterStepSchema] = Field(default_factory=list)


class ResolvedCohortSchema(BaseModel):
    label: str
    n_patients: int
    n_periods: int


class CohortResolveRequest(BaseModel):
    cohorts: list[CohortDefinitionSchema]
    data_dir: str = ""  # unused — data is loaded from platform config


class CohortResolveResponse(BaseModel):
    cohorts: list[ResolvedCohortSchema]
