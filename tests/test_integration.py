"""Integration tests — full pipeline from YAML cohort definition to to_dict().

These tests exercise the entire stack in one shot:
  YAML-style cohort dict → resolve_cohorts → cohorted_rdv → analytics → to_dict()

They catch wiring bugs that unit tests miss (e.g. a column dropped between
cohort resolution and analytics, or a schema mismatch in to_dict()).
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.cohort.filters import resolve_cohort
from core.cohort.models import CohortDefinition, CohortFilterStep
from core.services.analytics_runner import (
    cohorted_rdv,
    require_rdv,
    resolve_cohorts,
    run_event_count,
    run_event_time,
    run_frequency,
)

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pde():
    """Minimal patient demographics table with 6 patients across 2 sexes."""
    return pd.DataFrame(
        {
            "project_id": [f"P{i:03d}" for i in range(1, 7)],
            "birth_date": pd.to_datetime(
                ["1975-03-01", "1982-07-14", "1990-11-22", "1968-05-05", "2001-01-30", "1955-09-17"]
            ),
            "sex_name": ["Female", "Male", "Female", "Male", "Female", "Male"],
            "death_date": [None] * 6,
        }
    )


@pytest.fixture
def dia():
    """Minimal diagnoses RDV: 2 diagnoses × 6 patients."""
    return pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003", "P004", "P005", "P006"],
            "diag_name": ["Asthma", "COPD", "Asthma", "COPD", "Asthma", "COPD"],
            "start_datetime": pd.to_datetime(["2020-01-01"] * 6),
            "end_datetime": pd.to_datetime(["2020-06-01"] * 6),
        }
    )


@pytest.fixture
def rdvs(pde, dia):
    return {"pde": pde, "dia": dia}


@pytest.fixture
def two_cohort_defs():
    """Raw dicts matching the API / YAML format for Female + Male cohorts."""
    return [
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
        },
        {
            "label": "Male",
            "config": [
                {
                    "type": "filter",
                    "rdv": "pde",
                    "column": "sex_name",
                    "val": ["Male"],
                    "inclusion": "ever",
                    "query_type": "str_matches",
                }
            ],
        },
    ]


# ---------------------------------------------------------------------------
# Frequency pipeline
# ---------------------------------------------------------------------------


def test_frequency_pipeline_end_to_end(rdvs, two_cohort_defs):
    cohorts = resolve_cohorts(two_cohort_defs, rdvs)
    analysis = run_frequency(rdvs, "dia", "diag_name", cohorts)
    d = analysis.to_dict()

    assert "table" in d
    assert "plot" in d
    assert "meta" in d
    assert "diag_name" in d["meta"]["event_col"]
    assert len(d["table"]) > 0


def test_frequency_pipeline_no_cohorts(rdvs):
    """No cohorts → single 'All' cohort, still produces a valid result."""
    analysis = run_frequency(rdvs, "dia", "diag_name", [])
    d = analysis.to_dict()
    assert "table" in d
    cohorts_in_meta = d["meta"].get("cohorts", [])
    assert cohorts_in_meta == ["All"]


# ---------------------------------------------------------------------------
# Event count pipeline
# ---------------------------------------------------------------------------


def test_event_count_pipeline_end_to_end(rdvs, two_cohort_defs):
    cohorts = resolve_cohorts(two_cohort_defs, rdvs)
    analysis = run_event_count(rdvs, "dia", "diag_name", cohorts)
    d = analysis.to_dict()

    assert "table" in d
    assert "plot" in d
    assert "meta" in d
    assert len(d["table"]) > 0


# ---------------------------------------------------------------------------
# Event time pipeline
# ---------------------------------------------------------------------------


def test_event_time_pipeline_end_to_end(rdvs, two_cohort_defs):
    cohorts = resolve_cohorts(two_cohort_defs, rdvs)
    analysis = run_event_time(rdvs, "dia", "diag_name", cohorts)
    d = analysis.to_dict()

    assert "summary" in d
    assert "plot" in d
    assert "meta" in d
    assert len(d["summary"]) > 0


def test_event_time_pipeline_entry_date_available(rdvs, two_cohort_defs):
    """entry_date must be present on the cohorted RDV so demographics can
    compute age-at-entry.  Regression: it was previously dropped post-merge."""
    cohorts = resolve_cohorts(two_cohort_defs, rdvs)
    df_out = cohorted_rdv(require_rdv("dia", rdvs), cohorts)
    assert "entry_date" in df_out.columns


# ---------------------------------------------------------------------------
# require_rdv used by routes
# ---------------------------------------------------------------------------


def test_require_rdv_raises_with_informative_message(rdvs):
    with pytest.raises(ValueError) as exc_info:
        require_rdv("missing_rdv", rdvs)
    assert "missing_rdv" in str(exc_info.value)
    assert "dia" in str(exc_info.value)  # lists available RDVs
