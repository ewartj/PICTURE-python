"""Analytics endpoints.

Each endpoint delegates entirely to core/services/analytics_runner.py —
no cohort resolution or analytics logic lives here.

Adding a new analytics method = add a runner in the service layer,
add a route here, add schemas in api/schemas/analytics.py.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_rdvs
from api.schemas.analytics import (
    EventCountRequest,
    EventCountResponse,
    EventTimeRequest,
    EventTimeResponse,
    FrequencyRequest,
    FrequencyResponse,
)
from core.services.analytics_runner import (
    require_rdv,
    resolve_cohorts,
    run_event_count,
    run_event_time,
    run_frequency,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/frequency", response_model=FrequencyResponse)
def frequency_analysis(
    request: FrequencyRequest, rdvs: dict[str, object] = Depends(get_rdvs)
) -> FrequencyResponse:
    """Run a frequency analysis on any categorical RDV column."""
    try:
        require_rdv(request.rdv, rdvs)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if "pde" not in rdvs:
        raise HTTPException(status_code=404, detail="Demographics RDV (pde) is required.")

    logger.info("POST /analytics/frequency rdv=%s event_col=%s", request.rdv, request.event_col)
    try:
        cohorts = resolve_cohorts(request.cohort_definitions, rdvs)  # type: ignore[arg-type]
        result = run_frequency(rdvs, request.rdv, request.event_col, cohorts).to_dict()  # type: ignore[arg-type]
    except Exception as exc:
        logger.exception("frequency_analysis failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FrequencyResponse(**result)


@router.post("/event-count", response_model=EventCountResponse)
def event_count_analysis(
    request: EventCountRequest, rdvs: dict[str, object] = Depends(get_rdvs)
) -> EventCountResponse:
    """Distribution of event counts per patient."""
    try:
        require_rdv(request.rdv, rdvs)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    logger.info("POST /analytics/event-count rdv=%s event_col=%s", request.rdv, request.event_col)
    try:
        cohorts = resolve_cohorts(request.cohort_definitions, rdvs)  # type: ignore[arg-type]
        result = run_event_count(
            rdvs, request.rdv, request.event_col, cohorts, count_unique=request.count_unique  # type: ignore[arg-type]
        ).to_dict()
    except Exception as exc:
        logger.exception("event_count_analysis failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return EventCountResponse(**result)


@router.post("/event-time", response_model=EventTimeResponse)
def event_time_analysis(
    request: EventTimeRequest, rdvs: dict[str, object] = Depends(get_rdvs)
) -> EventTimeResponse:
    """Duration of events per event category."""
    try:
        require_rdv(request.rdv, rdvs)  # type: ignore[arg-type]
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    logger.info("POST /analytics/event-time rdv=%s event_col=%s", request.rdv, request.event_col)
    try:
        cohorts = resolve_cohorts(request.cohort_definitions, rdvs)  # type: ignore[arg-type]
        result = run_event_time(
            rdvs,  # type: ignore[arg-type]
            request.rdv,
            request.event_col,
            cohorts,
            plot_type=request.plot_type,
            log_scale=request.log_scale,
        ).to_dict()
    except Exception as exc:
        logger.exception("event_time_analysis failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return EventTimeResponse(**result)
