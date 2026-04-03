"""
Tests for cohort window-cropping filter functions.

Covers the three inclusion types that narrow the patient window:
  - fully_concurrent  (_ff_crop_entry_exit)
  - after_first       (_ff_crop_entry)
  - on_first          (_ff_crop_first)

Also covers the remaining query-type branches in resolve_cohort:
  str_contains, str_starts, date_between, numeric_between, age_between.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.cohort.filters import resolve_cohort
from core.cohort.models import CohortDefinition, CohortFilterStep, ResolvedCohort


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def df_pde():
    return pd.DataFrame({
        "project_id": ["P001", "P002", "P003", "P004", "P005"],
        "birth_date":  pd.to_datetime([
            "1980-01-01", "1990-06-15", "1975-03-20", "2000-11-05", "1985-07-01"
        ]),
        "sex_name":    ["Female", "Male", "Female", "Male", "Female"],
        "death_date":  [None, None, None, None, None],
    })


@pytest.fixture
def df_dia():
    """Diagnoses with explicit start/end datetimes for window tests."""
    return pd.DataFrame({
        "project_id":     ["P001", "P002", "P003", "P004"],
        "diag_name":      ["Asthma", "Asthma", "Hypertension", "Diabetes"],
        "start_datetime": pd.to_datetime([
            "2021-03-01", "2021-06-01", "2021-01-15", "2021-09-01"
        ]),
        "end_datetime": pd.to_datetime([
            "2021-06-30", "2021-08-31", "2021-04-15", "2021-12-01"
        ]),
    })


@pytest.fixture
def df_wst():
    """Ward stays with numeric column for numeric_between tests."""
    return pd.DataFrame({
        "project_id":      ["P001", "P002", "P003", "P004"],
        "ward_stay_days":  [3, 15, 7, 45],
        "start_datetime":  pd.to_datetime(["2021-01-01"] * 4),
        "end_datetime":    pd.to_datetime(["2021-01-10"] * 4),
    })


@pytest.fixture
def rdvs(df_pde, df_dia, df_wst):
    return {"pde": df_pde, "dia": df_dia, "wst": df_wst}


# ---------------------------------------------------------------------------
# Query type branches
# ---------------------------------------------------------------------------

def test_str_contains(rdvs):
    defn = CohortDefinition(label="Asthma-like", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Asthm"], inclusion="ever", query_type="str_contains"),
    ])
    result = resolve_cohort(defn, rdvs)
    assert set(result.patient_list["project_id"]) == {"P001", "P002"}


def test_str_starts(rdvs):
    defn = CohortDefinition(label="H-diagnoses", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Hyper"], inclusion="ever", query_type="str_starts"),
    ])
    result = resolve_cohort(defn, rdvs)
    assert set(result.patient_list["project_id"]) == {"P003"}


def test_date_between(rdvs):
    defn = CohortDefinition(label="Mid-year admits", config=[
        CohortFilterStep(type="filter", rdv="dia", column="start_datetime",
                         val=["2021-05-01", "2021-12-31"],
                         inclusion="ever", query_type="date_between"),
    ])
    result = resolve_cohort(defn, rdvs)
    # P002 (Jun), P004 (Sep) have start_datetime in range
    assert set(result.patient_list["project_id"]) == {"P002", "P004"}


def test_numeric_between(rdvs):
    defn = CohortDefinition(label="Long stays", config=[
        CohortFilterStep(type="filter", rdv="wst", column="ward_stay_days",
                         val=[10, 50], inclusion="ever", query_type="numeric_between"),
    ])
    result = resolve_cohort(defn, rdvs)
    assert set(result.patient_list["project_id"]) == {"P002", "P004"}


def test_age_between(rdvs):
    # age_between uses birth_date from pde to crop the cohort window to an
    # age range. P001 born 1980, P002 born 1990, P004 born 2000.
    # Range 30–45 means the window must overlap [birth+30y, birth+45y].
    # Today (2026) is within that window for P001 (1980, age 46) — but only
    # the overlap period counts. For P004 (born 2000, age 26 today) the
    # window starts at 2030, which is in the future → window is empty → excluded.
    defn = CohortDefinition(label="30-45", config=[
        CohortFilterStep(type="filter", rdv="pde", column="birth_date",
                         val=[30, 45], inclusion="ever", query_type="age_between"),
    ])
    result = resolve_cohort(defn, rdvs)
    # P001 (born 1980) and P002 (born 1990) are currently in the 30-45 age window
    assert "P001" in set(result.patient_list["project_id"])
    assert "P002" in set(result.patient_list["project_id"])
    # P004 born 2000 → age 26 today — not yet 30, so the window hasn't opened
    assert "P004" not in set(result.patient_list["project_id"])


# ---------------------------------------------------------------------------
# fully_concurrent — entry/exit cropped to event window
# ---------------------------------------------------------------------------

def test_fully_concurrent_filters_patients(rdvs):
    """Patients with no overlapping event are excluded."""
    defn = CohortDefinition(label="Concurrent asthma", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Asthma"], inclusion="fully_concurrent",
                         query_type="str_matches"),
    ])
    result = resolve_cohort(defn, rdvs)
    # Only P001 and P002 have Asthma
    assert set(result.patient_list["project_id"]) == {"P001", "P002"}


def test_fully_concurrent_crops_entry(rdvs):
    """entry_date is pushed forward to event start_datetime."""
    defn = CohortDefinition(label="Concurrent asthma", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Asthma"], inclusion="fully_concurrent",
                         query_type="str_matches"),
    ])
    result = resolve_cohort(defn, rdvs)
    p001 = result.patient_list[result.patient_list["project_id"] == "P001"].iloc[0]
    # P001 event starts 2021-03-01 — entry_date must be at least that
    assert pd.Timestamp(p001["entry_date"]) >= pd.Timestamp("2021-03-01")


def test_fully_concurrent_crops_exit(rdvs):
    """exit_date is pulled back to event end_datetime."""
    defn = CohortDefinition(label="Concurrent asthma", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Asthma"], inclusion="fully_concurrent",
                         query_type="str_matches"),
    ])
    result = resolve_cohort(defn, rdvs)
    p001 = result.patient_list[result.patient_list["project_id"] == "P001"].iloc[0]
    # P001 event ends 2021-06-30
    assert pd.Timestamp(p001["exit_date"]) <= pd.Timestamp("2021-06-30")


def test_fully_concurrent_with_window_offset(rdvs):
    """Window offsets shift entry/exit by the specified days."""
    defn = CohortDefinition(label="Concurrent+window", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Asthma"], inclusion="fully_concurrent",
                         query_type="str_matches", window=[-7, 7]),
    ])
    result = resolve_cohort(defn, rdvs)
    p001 = result.patient_list[result.patient_list["project_id"] == "P001"].iloc[0]
    # entry_date should be >= 2021-03-01 minus 7 days = 2021-02-22
    assert pd.Timestamp(p001["entry_date"]) >= pd.Timestamp("2021-02-22")


# ---------------------------------------------------------------------------
# after_first — entry cropped to first event
# ---------------------------------------------------------------------------

def test_after_first_crops_entry_only(rdvs):
    """after_first advances entry_date but does not shorten exit_date."""
    defn = CohortDefinition(label="After first asthma", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Asthma"], inclusion="after_first",
                         query_type="str_matches"),
    ])
    result = resolve_cohort(defn, rdvs)
    p001 = result.patient_list[result.patient_list["project_id"] == "P001"].iloc[0]
    # entry_date >= first event (2021-03-01)
    assert pd.Timestamp(p001["entry_date"]) >= pd.Timestamp("2021-03-01")
    # exit_date should be the patient's natural exit (not cropped to event end)
    # P001 has no death_date so exit ~ today — well after 2021-06-30
    assert pd.Timestamp(p001["exit_date"]) > pd.Timestamp("2021-06-30")


def test_after_first_excludes_non_matching_patients(rdvs):
    defn = CohortDefinition(label="After first asthma", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Asthma"], inclusion="after_first",
                         query_type="str_matches"),
    ])
    result = resolve_cohort(defn, rdvs)
    assert "P003" not in set(result.patient_list["project_id"])
    assert "P004" not in set(result.patient_list["project_id"])


# ---------------------------------------------------------------------------
# on_first — both entry and exit pinned to first event
# ---------------------------------------------------------------------------

def test_on_first_pins_entry_and_exit(rdvs):
    """on_first sets both entry_date and exit_date around the first event."""
    defn = CohortDefinition(label="On first asthma", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Asthma"], inclusion="on_first",
                         query_type="str_matches"),
    ])
    result = resolve_cohort(defn, rdvs)
    p001 = result.patient_list[result.patient_list["project_id"] == "P001"].iloc[0]
    # With [0,0] window: entry = exit = first start_datetime (2021-03-01)
    assert pd.Timestamp(p001["entry_date"]) == pd.Timestamp("2021-03-01")
    assert pd.Timestamp(p001["exit_date"]) == pd.Timestamp("2021-03-01")


def test_on_first_with_window_offset(rdvs):
    """Window offsets expand the pinned window around first event."""
    defn = CohortDefinition(label="On first ±30", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Asthma"], inclusion="on_first",
                         query_type="str_matches", window=[-30, 30]),
    ])
    result = resolve_cohort(defn, rdvs)
    p001 = result.patient_list[result.patient_list["project_id"] == "P001"].iloc[0]
    # P001 first event 2021-03-01 → entry = 2021-01-30, exit = 2021-03-31
    assert pd.Timestamp(p001["entry_date"]) == pd.Timestamp("2021-01-30")
    assert pd.Timestamp(p001["exit_date"]) == pd.Timestamp("2021-03-31")


def test_on_first_excludes_non_matching(rdvs):
    defn = CohortDefinition(label="On first asthma", config=[
        CohortFilterStep(type="filter", rdv="dia", column="diag_name",
                         val=["Asthma"], inclusion="on_first",
                         query_type="str_matches"),
    ])
    result = resolve_cohort(defn, rdvs)
    assert set(result.patient_list["project_id"]) == {"P001", "P002"}
