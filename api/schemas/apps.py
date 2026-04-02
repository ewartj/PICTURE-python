"""Pydantic response schemas for app config endpoints."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class AnalysisMethodSchema(BaseModel):
    fn: str
    params: dict[str, Any] = {}
    tab_lbl: Optional[str] = None
    output: Optional[str] = None
    rpkg: Optional[str] = None


class AnalysisTabSchema(BaseModel):
    tab: str
    method_list: list[AnalysisMethodSchema] = []


class OutputConfigSchema(BaseModel):
    interactive: bool = True
    pdf: bool = False


class CohortFilterStepSummary(BaseModel):
    type: str
    rdv: Optional[str] = None
    column: Optional[str] = None
    query_type: str = "str_matches"
    inclusion: str = "ever"
    val: Optional[list[Any]] = None
    window: Optional[list[int]] = None


class CohortSummary(BaseModel):
    label: str
    config: list[CohortFilterStepSummary] = []


class AppConfigSummary(BaseModel):
    """Lightweight listing returned by GET /apps."""
    id: int
    title: str
    description: str = ""
    creator: str = ""
    img: Optional[str] = None
    dataset: Optional[str] = None


class AppConfigDetail(AppConfigSummary):
    """Full config returned by GET /apps/{app_id}."""
    offer_cohort_builder: bool = True
    initial_cohorts: list[CohortSummary] = []
    analysis: list[AnalysisTabSchema] = []
    outputs: OutputConfigSchema = OutputConfigSchema()
    all_rdv_names: list[str] = []
