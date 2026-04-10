"""
Tests for cohort resolution and RDV filtering.

Replaces: picture.platform R tests for utils_segment_cohorts.R
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.cohort.filters import apply_cohorts_to_rdv, resolve_cohort
from core.cohort.models import CohortDefinition, CohortFilterStep, ResolvedCohort


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def df_pde():
    return pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003", "P004"],
            "birth_date": pd.to_datetime(
                ["1980-01-01", "1990-06-15", "1975-03-20", "2000-11-05"]
            ),
            "sex_name": ["Female", "Male", "Female", "Male"],
            "death_date": [None, None, None, None],
        }
    )


@pytest.fixture
def df_dia():
    return pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003", "P004"],
            "diag_name": ["Asthma", "Asthma", "Hypertension", "Diabetes"],
            "start_datetime": pd.to_datetime(["2020-01-01"] * 4),
            "end_datetime": pd.to_datetime(["2020-06-01"] * 4),
        }
    )


@pytest.fixture
def rdvs(df_pde, df_dia):
    return {"pde": df_pde, "dia": df_dia}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_resolve_cohort_female_filter(rdvs):
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
    resolved = resolve_cohort(definition, rdvs)
    assert isinstance(resolved, ResolvedCohort)
    assert resolved.label == "Female"
    assert resolved.n_patients == 2  # P001, P003
    assert set(resolved.patient_list["project_id"]) == {"P001", "P003"}


def test_resolve_cohort_never_exclusion(rdvs):
    definition = CohortDefinition(
        label="Not Female",
        config=[
            CohortFilterStep(
                type="filter",
                rdv="pde",
                column="sex_name",
                val=["Female"],
                inclusion="never",
                query_type="str_matches",
            )
        ],
    )
    resolved = resolve_cohort(definition, rdvs)
    assert resolved.n_patients == 2  # P002, P004


def test_apply_cohorts_to_rdv_labels_rows(rdvs):
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
    resolved = resolve_cohort(definition, rdvs)
    df_out = apply_cohorts_to_rdv(rdvs["dia"], [resolved])
    assert "cohort" in df_out.columns
    assert set(df_out["cohort"].unique()) == {"Female"}
    assert set(df_out["project_id"].unique()).issubset({"P001", "P003"})


def test_apply_multiple_cohorts(rdvs):
    female_def = CohortDefinition(
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
    male_def = CohortDefinition(
        label="Male",
        config=[
            CohortFilterStep(
                type="filter",
                rdv="pde",
                column="sex_name",
                val=["Male"],
                inclusion="ever",
                query_type="str_matches",
            )
        ],
    )
    cohorts = [resolve_cohort(female_def, rdvs), resolve_cohort(male_def, rdvs)]
    df_out = apply_cohorts_to_rdv(rdvs["dia"], cohorts)
    assert set(df_out["cohort"].unique()) == {"Female", "Male"}
    assert len(df_out) == 4  # all 4 patients covered
