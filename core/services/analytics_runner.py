"""Analytics service layer.

Owns the pipeline: resolve cohorts → apply to RDV → compute analytics.

Both the API routes and the Streamlit UI components delegate to these
functions so the wiring logic lives in exactly one place.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from core.analytics.event_count import EventCount
from core.analytics.event_time import EventTimeAnalysis
from core.analytics.frequency import FrequencyAnalysis
from core.cohort.filters import apply_cohorts_to_rdv, resolve_cohort
from core.cohort.models import CohortDefinition, ResolvedCohort, cohort_definition_from_yaml
from core.constants import COHORT_COL, COHORT_ID_COL, DEFAULT_COHORT_LABEL, PROJECT_ID_COL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------


def require_rdv(rdv_name: str, rdvs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Return the named RDV DataFrame, raising ValueError if not present.

    Args:
        rdv_name: Key into *rdvs*.
        rdvs:     All loaded RDV DataFrames.

    Raises:
        ValueError: If *rdv_name* is not in *rdvs*.
    """
    if rdv_name not in rdvs:
        raise ValueError(f"RDV '{rdv_name}' not available. Loaded RDVs: {sorted(rdvs.keys())}")
    return rdvs[rdv_name]


# ---------------------------------------------------------------------------
# Cohort helpers
# ---------------------------------------------------------------------------


def resolve_cohorts(
    cohort_definitions: list[dict[str, Any]],
    rdvs: dict[str, pd.DataFrame],
) -> list[ResolvedCohort]:
    """Parse and resolve a list of raw cohort definition dicts.

    Args:
        cohort_definitions: Raw dicts from the API request or YAML config.
        rdvs:               All loaded RDV DataFrames.

    Returns:
        List of resolved cohorts (may be empty).
    """
    logger.debug("Resolving %d cohort definition(s).", len(cohort_definitions))
    return [resolve_cohort(cohort_definition_from_yaml(raw), rdvs) for raw in cohort_definitions]


def cohorted_rdv(
    rdv_df: pd.DataFrame,
    resolved_cohorts: list[ResolvedCohort],
) -> pd.DataFrame:
    """Return a cohort-labelled copy of *rdv_df*.

    If no cohorts are provided every row is labelled with the default label.
    This is the single canonical implementation — both the API service
    functions and the Streamlit UI cache helper delegate here.
    """
    if resolved_cohorts:
        logger.debug(
            "Applying %d cohort(s) to RDV (%d rows).",
            len(resolved_cohorts),
            len(rdv_df),
        )
        return apply_cohorts_to_rdv(rdv_df, resolved_cohorts)
    df = rdv_df.assign(**{COHORT_COL: DEFAULT_COHORT_LABEL})
    if COHORT_ID_COL not in df.columns:
        df = df.assign(**{COHORT_ID_COL: df[PROJECT_ID_COL].astype(str)})
    return df


# ---------------------------------------------------------------------------
# Per-analysis runners
# ---------------------------------------------------------------------------


def run_frequency(
    rdvs: dict[str, pd.DataFrame],
    rdv_name: str,
    event_col: str,
    resolved_cohorts: list[ResolvedCohort],
) -> FrequencyAnalysis:
    """Build, compute, and return a :class:`FrequencyAnalysis`."""
    logger.info("run_frequency: rdv=%s event_col=%s", rdv_name, event_col)
    df = cohorted_rdv(require_rdv(rdv_name, rdvs), resolved_cohorts)
    return FrequencyAnalysis(
        df_rdv=df,
        df_pde=rdvs.get("pde", df),
        event_col=event_col,
    ).compute()


def run_event_count(
    rdvs: dict[str, pd.DataFrame],
    rdv_name: str,
    event_col: str,
    resolved_cohorts: list[ResolvedCohort],
    count_unique: bool = True,
) -> EventCount:
    """Build, compute, and return an :class:`EventCount`."""
    logger.info("run_event_count: rdv=%s event_col=%s", rdv_name, event_col)
    df = cohorted_rdv(require_rdv(rdv_name, rdvs), resolved_cohorts)
    return EventCount(
        df_rdv=df,
        df_pde=rdvs.get("pde", pd.DataFrame()),
        event_col=event_col,
        count_unique=count_unique,
    ).compute()


def run_event_time(
    rdvs: dict[str, pd.DataFrame],
    rdv_name: str,
    event_col: str,
    resolved_cohorts: list[ResolvedCohort],
    plot_type: str = "boxplot",
    log_scale: bool = False,
) -> EventTimeAnalysis:
    """Build, compute, and return an :class:`EventTimeAnalysis`."""
    logger.info("run_event_time: rdv=%s event_col=%s", rdv_name, event_col)
    df = cohorted_rdv(require_rdv(rdv_name, rdvs), resolved_cohorts)
    return EventTimeAnalysis(
        df_rdv=df,
        df_pde=rdvs.get("pde", pd.DataFrame()),
        event_col=event_col,
        plot_type=plot_type,  # type: ignore[arg-type]
        log_scale=log_scale,
    ).compute()
