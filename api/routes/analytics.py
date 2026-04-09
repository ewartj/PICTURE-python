"""Analytics endpoints.

Each endpoint:
  1. Loads the requested RDV(s)
  2. Resolves cohorts and applies them to the RDV
  3. Runs the analytics module
  4. Returns to_dict() as JSON

Adding a new analytics method = add a new route here + a class in core/analytics/.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_rdvs
from typing import cast

from api.schemas.analytics import (
    EventCountRequest,
    EventCountResponse,
    EventTimeRequest,
    EventTimeResponse,
    FrequencyRequest,
    FrequencyResponse,
)
from core.analytics.event_count import EventCount
from core.analytics.event_time import EventTimeAnalysis
from core.analytics.frequency import FrequencyAnalysis
from core.cohort.filters import apply_cohorts_to_rdv, resolve_cohort
from core.cohort.models import cohort_definition_from_yaml

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _resolve_cohorts(cohort_definitions: list[dict], rdvs: dict):
    """Helper: parse and resolve a list of cohort definition dicts."""
    if not cohort_definitions:
        return None  # single-cohort mode

    resolved = []
    for raw in cohort_definitions:
        definition = cohort_definition_from_yaml(raw)
        resolved.append(resolve_cohort(definition, rdvs))
    return resolved


@router.post("/frequency", response_model=FrequencyResponse)
def frequency_analysis(
    request: FrequencyRequest,
    rdvs: dict = Depends(get_rdvs),
):
    """Run a frequency analysis on any categorical RDV column."""
    if request.rdv not in rdvs:
        raise HTTPException(
            status_code=404, detail=f"RDV '{request.rdv}' not available."
        )
    if "pde" not in rdvs:
        raise HTTPException(
            status_code=404, detail="Demographics RDV (pde) is required."
        )

    cohorts = _resolve_cohorts(request.cohort_definitions, rdvs)

    if cohorts:
        df_rdv = apply_cohorts_to_rdv(rdvs[request.rdv], cohorts)
    else:
        df_rdv = rdvs[request.rdv].copy()
        df_rdv["cohort"] = "All"
        if "cohort_id" not in df_rdv.columns:
            df_rdv["cohort_id"] = df_rdv["project_id"].astype(str)

    analysis = FrequencyAnalysis(
        df_rdv=df_rdv,
        df_pde=rdvs["pde"],
        event_col=request.event_col,
    )
    result = analysis.compute().to_dict()
    return FrequencyResponse(**result)


def _apply_cohorts_or_all(rdv_name: str, cohort_definitions: list[dict], rdvs: dict):
    """Resolve and apply cohorts, or label everything 'All' if no cohorts given."""
    if rdv_name not in rdvs:
        raise HTTPException(status_code=404, detail=f"RDV '{rdv_name}' not available.")
    df_rdv = rdvs[rdv_name]
    cohorts = _resolve_cohorts(cohort_definitions, rdvs)
    if cohorts:
        return apply_cohorts_to_rdv(df_rdv, cohorts)
    df_rdv = df_rdv.copy()
    df_rdv["cohort"] = "All"
    if "cohort_id" not in df_rdv.columns:
        df_rdv["cohort_id"] = df_rdv["project_id"].astype(str)
    return df_rdv


@router.post("/event-count", response_model=EventCountResponse)
def event_count_analysis(request: EventCountRequest, rdvs: dict = Depends(get_rdvs)):
    """Distribution of event counts per patient."""
    if request.rdv not in rdvs:
        raise HTTPException(
            status_code=404, detail=f"RDV '{request.rdv}' not available."
        )
    cohorts = _resolve_cohorts(request.cohort_definitions, rdvs)
    df_rdv = (
        apply_cohorts_to_rdv(rdvs[request.rdv], cohorts)
        if cohorts
        else rdvs[request.rdv].copy()
    )
    result = (
        EventCount(
            df_rdv,
            rdvs.get("pde", df_rdv),
            event_col=request.event_col,
            count_unique=request.count_unique,
        )
        .compute()
        .to_dict()
    )
    return EventCountResponse(**result)


@router.post("/event-time", response_model=EventTimeResponse)
def event_time_analysis(request: EventTimeRequest, rdvs: dict = Depends(get_rdvs)):
    """Duration of events per event category."""
    if request.rdv not in rdvs:
        raise HTTPException(
            status_code=404, detail=f"RDV '{request.rdv}' not available."
        )
    cohorts = _resolve_cohorts(request.cohort_definitions, rdvs)
    df_rdv = (
        apply_cohorts_to_rdv(rdvs[request.rdv], cohorts)
        if cohorts
        else rdvs[request.rdv].copy()
    )
    result = (
        EventTimeAnalysis(
            df_rdv,
            rdvs.get("pde", df_rdv),
            event_col=request.event_col,
            plot_type=request.plot_type,
            log_scale=request.log_scale,
        )
        .compute()
        .to_dict()
    )
    return EventTimeResponse(**result)


# ---------------------------------------------------------------------------
# Remaining stubs (location not yet ported — requires shapefiles)
# ---------------------------------------------------------------------------


@router.post("/location")
def location_analysis():
    raise HTTPException(
        status_code=501, detail="Location analysis not yet implemented."
    )
