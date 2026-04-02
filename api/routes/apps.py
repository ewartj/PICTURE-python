"""App config endpoints.

GET /apps          — list all loaded app configs (summary)
GET /apps/{app_id} — full config for a single app

These endpoints expose the parsed YAML app definitions to the frontend so it
can build navigation tabs, load the right RDVs, and pre-populate cohort
definitions without the user having to specify everything in every request.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_app_configs
from api.schemas.apps import AppConfigDetail, AppConfigSummary, AnalysisTabSchema, AnalysisMethodSchema, CohortSummary, CohortFilterStepSummary, OutputConfigSchema
from core.config.app_config import AppConfig

router = APIRouter(prefix="/apps", tags=["apps"])


def _to_summary(app: AppConfig) -> AppConfigSummary:
    return AppConfigSummary(
        id=app.id,
        title=app.title,
        description=app.description,
        creator=app.creator,
        img=app.img,
        dataset=app.dataset,
    )


def _to_detail(app: AppConfig) -> AppConfigDetail:
    cohorts = [
        CohortSummary(
            label=c.label,
            config=[
                CohortFilterStepSummary(
                    type=step.type,
                    rdv=step.rdv,
                    column=step.column,
                    query_type=step.query_type,
                    inclusion=step.inclusion,
                    val=step.val,
                    window=step.window,
                )
                for step in c.config
            ],
        )
        for c in app.initial_cohorts
    ]

    tabs = [
        AnalysisTabSchema(
            tab=t.tab,
            method_list=[
                AnalysisMethodSchema(
                    fn=m.fn,
                    params=m.params,
                    tab_lbl=m.tab_lbl,
                    output=m.output,
                    rpkg=m.rpkg,
                )
                for m in t.method_list
            ],
        )
        for t in app.analysis
    ]

    return AppConfigDetail(
        id=app.id,
        title=app.title,
        description=app.description,
        creator=app.creator,
        img=app.img,
        dataset=app.dataset,
        offer_cohort_builder=app.offer_cohort_builder,
        initial_cohorts=cohorts,
        analysis=tabs,
        outputs=OutputConfigSchema(
            interactive=app.outputs.interactive,
            pdf=app.outputs.pdf,
        ),
        all_rdv_names=sorted(app.all_rdv_names),
    )


@router.get("", response_model=list[AppConfigSummary])
def list_apps(apps: list[AppConfig] = Depends(get_app_configs)):
    """Return a summary list of all loaded app configs."""
    return [_to_summary(a) for a in apps]


@router.get("/{app_id}", response_model=AppConfigDetail)
def get_app(app_id: int, apps: list[AppConfig] = Depends(get_app_configs)):
    """Return the full config for a single app by its integer ID."""
    for app in apps:
        if app.id == app_id:
            return _to_detail(app)
    raise HTTPException(status_code=404, detail=f"App '{app_id}' not found.")
