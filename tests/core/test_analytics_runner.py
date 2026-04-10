"""Tests for core/services/analytics_runner.py."""

from __future__ import annotations

import pandas as pd
import pytest

from core.analytics.event_count import EventCount
from core.analytics.event_time import EventTimeAnalysis
from core.analytics.frequency import FrequencyAnalysis
from core.cohort.models import CohortDefinition, CohortFilterStep, ResolvedCohort
from core.services.analytics_runner import (
    cohorted_rdv,
    require_rdv,
    resolve_cohorts,
    run_event_count,
    run_event_time,
    run_frequency,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def df_pde():
    return pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003", "P004"],
            "birth_date": pd.to_datetime(["1980-01-01"] * 4),
            "sex_name": ["Female", "Male", "Female", "Male"],
            "death_date": [None, None, None, None],
        }
    )


@pytest.fixture
def df_dia():
    return pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003", "P004"],
            "diag_name": ["Asthma", "COPD", "Asthma", "COPD"],
            "start_datetime": pd.to_datetime(["2020-01-01"] * 4),
            "end_datetime": pd.to_datetime(["2020-06-01"] * 4),
        }
    )


@pytest.fixture
def rdvs(df_pde, df_dia):
    return {"pde": df_pde, "dia": df_dia}


@pytest.fixture
def female_cohort(rdvs):
    definition = CohortDefinition(
        label="Female",
        config=[
            CohortFilterStep(
                type="filter",
                rdv="pde",
                column="sex_name",
                val=["Female"],
                inclusion="ever",
                query_type="str_matches",
            )
        ],
    )
    from core.cohort.filters import resolve_cohort

    return resolve_cohort(definition, rdvs)


# ---------------------------------------------------------------------------
# require_rdv
# ---------------------------------------------------------------------------


def test_require_rdv_returns_dataframe(rdvs):
    df = require_rdv("dia", rdvs)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 4


def test_require_rdv_raises_for_missing(rdvs):
    with pytest.raises(ValueError, match="'nonexistent'"):
        require_rdv("nonexistent", rdvs)


def test_require_rdv_error_lists_available(rdvs):
    with pytest.raises(ValueError, match="dia"):
        require_rdv("nonexistent", rdvs)


# ---------------------------------------------------------------------------
# resolve_cohorts
# ---------------------------------------------------------------------------


def test_resolve_cohorts_returns_list(rdvs):
    raw = [
        {
            "label": "Female",
            "config": [
                {
                    "type": "filter",
                    "rdv": "pde",
                    "column": "sex_name",
                    "val": ["Female"],
                    "inclusion": "ever",
                    "query_type": "str_matches",
                }
            ],
        }
    ]
    cohorts = resolve_cohorts(raw, rdvs)
    assert len(cohorts) == 1
    assert cohorts[0].label == "Female"


def test_resolve_cohorts_empty_returns_empty(rdvs):
    assert resolve_cohorts([], rdvs) == []


# ---------------------------------------------------------------------------
# cohorted_rdv
# ---------------------------------------------------------------------------


def test_cohorted_rdv_no_cohorts_labels_all(df_dia):
    result = cohorted_rdv(df_dia, [])
    assert "cohort" in result.columns
    assert (result["cohort"] == "All").all()


def test_cohorted_rdv_no_cohorts_adds_cohort_id(df_dia):
    result = cohorted_rdv(df_dia, [])
    assert "cohort_id" in result.columns


def test_cohorted_rdv_with_cohorts_applies_filter(df_dia, female_cohort):
    result = cohorted_rdv(df_dia, [female_cohort])
    assert "cohort" in result.columns
    assert set(result["cohort"].unique()) == {"Female"}
    assert set(result["project_id"].unique()).issubset({"P001", "P003"})


# ---------------------------------------------------------------------------
# run_frequency
# ---------------------------------------------------------------------------


def test_run_frequency_returns_analysis(rdvs, female_cohort):
    result = run_frequency(rdvs, "dia", "diag_name", [female_cohort])
    assert isinstance(result, FrequencyAnalysis)
    assert result._result is not None


def test_run_frequency_missing_rdv_raises(rdvs):
    with pytest.raises(ValueError):
        run_frequency(rdvs, "nonexistent", "diag_name", [])


# ---------------------------------------------------------------------------
# run_event_count
# ---------------------------------------------------------------------------


def test_run_event_count_returns_analysis(rdvs, female_cohort):
    result = run_event_count(rdvs, "dia", "diag_name", [female_cohort])
    assert isinstance(result, EventCount)
    assert result._result is not None


def test_run_event_count_missing_rdv_raises(rdvs):
    with pytest.raises(ValueError):
        run_event_count(rdvs, "nonexistent", "diag_name", [])


# ---------------------------------------------------------------------------
# run_event_time
# ---------------------------------------------------------------------------


def test_run_event_time_returns_analysis(rdvs, female_cohort):
    result = run_event_time(rdvs, "dia", "diag_name", [female_cohort])
    assert isinstance(result, EventTimeAnalysis)
    assert result._result is not None


def test_run_event_time_missing_rdv_raises(rdvs):
    with pytest.raises(ValueError):
        run_event_time(rdvs, "nonexistent", "diag_name", [])


def test_run_event_time_histogram(rdvs):
    result = run_event_time(rdvs, "dia", "diag_name", [], plot_type="histogram")
    assert isinstance(result, EventTimeAnalysis)
    assert result.plot_type == "histogram"
