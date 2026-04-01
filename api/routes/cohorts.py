"""Cohort resolution endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from api.deps import get_rdvs
from api.schemas.cohort import (
    CohortResolveRequest,
    CohortResolveResponse,
    ResolvedCohortSchema,
)
from core.cohort.filters import resolve_cohort
from core.cohort.models import cohort_definition_from_yaml

router = APIRouter(prefix="/cohorts", tags=["cohorts"])


@router.post("/resolve", response_model=CohortResolveResponse)
def resolve_cohorts(
    request: CohortResolveRequest,
    rdvs: dict = Depends(get_rdvs),
):
    """Resolve a list of cohort definitions against loaded RDV data.

    Returns patient counts for each cohort — used by the UI to show cohort
    sizes before running analytics.
    """
    results = []
    for cohort_schema in request.cohorts:
        definition = cohort_definition_from_yaml(cohort_schema.model_dump())
        resolved = resolve_cohort(definition, rdvs)
        results.append(
            ResolvedCohortSchema(
                label=resolved.label,
                n_patients=resolved.n_patients,
                n_periods=resolved.n_periods,
            )
        )
    return CohortResolveResponse(cohorts=results)
