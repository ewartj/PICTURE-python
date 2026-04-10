"""Shared UI component utilities."""

from __future__ import annotations

import logging
import traceback
from contextlib import contextmanager
from typing import Generator

import pandas as pd
import streamlit as st

from core.cohort.models import ResolvedCohort
from core.services.analytics_runner import cohorted_rdv

logger = logging.getLogger(__name__)


@contextmanager
def handle_analysis_errors(label: str) -> Generator[None, None, None]:
    """Context manager that catches exceptions, logs them, and shows an st.error.

    Replaces the repeated try/except pattern in every UI component so that
    error handling is consistent and stack traces are preserved in logs.

    Usage::

        with handle_analysis_errors("Sex analysis"):
            obj = CategoricalRatios(...).compute()
            st.plotly_chart(obj.plot())

    Args:
        label: Human-readable name shown in the error message.
    """
    try:
        yield
    except Exception as exc:
        logger.exception("%s failed", label)
        st.error(f"{label} failed: {exc}")
        st.caption(
            "Stack trace logged. Expand below for details.",
            help=traceback.format_exc(),
        )


def evict_stale_cache(prefix: str, current_key: str) -> None:
    """Delete session-state cache entries that share the same prefix but have
    a different (outdated) cohort key.

    Called whenever a new analytics result is stored so that old cohort
    versions of the same analysis don't accumulate in memory.

    Args:
        prefix:      Everything in the cache key up to (but not including)
                     the cohort portion, e.g. ``"_et:dia:diag_name:"``.
        current_key: The full key just written — this one is kept.
    """
    stale = [k for k in st.session_state if k.startswith(prefix) and k != current_key]
    for k in stale:
        del st.session_state[k]


def get_cohorted_rdv(
    rdv_name: str,
    rdv_df: pd.DataFrame,
    resolved_cohorts: list[ResolvedCohort],
    cohort_key: str,
) -> pd.DataFrame:
    """Return a cohort-labelled RDV, computing and caching it on first call.

    All analysis components on the same tab share one copy of the cohorted
    DataFrame instead of each building their own.

    Delegates to :func:`core.services.analytics_runner.cohorted_rdv` so the
    cohort-application logic lives in exactly one place.

    Args:
        rdv_name:         RDV identifier used as part of the cache key.
        rdv_df:           The raw (un-cohorted) RDV DataFrame.
        resolved_cohorts: Cohorts to apply; if empty, all rows labelled "All".
        cohort_key:       Pre-computed cohort fingerprint string.

    Returns:
        Cohort-labelled DataFrame (may be served from cache).
    """
    cache_key = f"_cohorted:{rdv_name}:{cohort_key}"
    evict_stale_cache(f"_cohorted:{rdv_name}:", cache_key)

    if cache_key not in st.session_state:
        st.session_state[cache_key] = cohorted_rdv(rdv_df, resolved_cohorts)

    return st.session_state[cache_key]
