"""Tests for EventCount analytics module."""

from __future__ import annotations
import pandas as pd
import pytest
from core.analytics.event_count import EventCount


@pytest.fixture
def df_pde():
    return pd.DataFrame(
        {
            "project_id": [f"P{i:03d}" for i in range(1, 7)],
            "cohort": ["A", "A", "A", "B", "B", "B"],
            "birth_date": pd.to_datetime(["1980-01-01"] * 6),
        }
    )


@pytest.fixture
def df_rdv():
    return pd.DataFrame(
        {
            "project_id": ["P001", "P001", "P002", "P003", "P004", "P005"],
            "cohort_id": [
                "P001-000001",
                "P001-000001",
                "P002-000001",
                "P003-000001",
                "P004-000001",
                "P005-000001",
            ],
            "cohort": ["A", "A", "A", "A", "B", "B"],
            "diag_name": ["Asthma", "COPD", "Asthma", "COPD", "Asthma", "COPD"],
        }
    )


def test_compute_returns_self(df_rdv, df_pde):
    obj = EventCount(df_rdv, df_pde, event_col="diag_name")
    assert obj.compute() is obj


def test_compute_includes_zero_count_patients(df_rdv, df_pde):
    obj = EventCount(df_rdv, df_pde, event_col="diag_name").compute()
    # P006 in cohort B has no events → should appear with event_count=0
    zero_rows = obj._counts[(obj._counts["cohort"] == "B") & (obj._counts["event_count"] == 0)]
    assert len(zero_rows) == 1
    assert zero_rows["patient_count"].iloc[0] == 1  # P006


def test_compute_result_has_cohort_columns(df_rdv, df_pde):
    obj = EventCount(df_rdv, df_pde, event_col="diag_name").compute()
    assert any("A." in c for c in obj._result.columns)
    assert any("B." in c for c in obj._result.columns)


def test_count_unique_deduplicates(df_rdv, df_pde):
    obj_unique = EventCount(df_rdv, df_pde, event_col="diag_name", count_unique=True).compute()
    obj_all = EventCount(df_rdv, df_pde, event_col="diag_name", count_unique=False).compute()
    # P001 has 2 rows in df_rdv but same cohort_id → unique=True collapses them
    a_counts_unique = obj_unique._counts[obj_unique._counts["cohort"] == "A"]
    a_counts_all = obj_all._counts[obj_all._counts["cohort"] == "A"]
    assert a_counts_unique["patient_count"].sum() <= a_counts_all["patient_count"].sum()


def test_plot_returns_figure(df_rdv, df_pde):
    import plotly.graph_objects as go

    obj = EventCount(df_rdv, df_pde, event_col="diag_name").compute()
    assert isinstance(obj.plot(), go.Figure)


def test_plot_raises_before_compute(df_rdv, df_pde):
    with pytest.raises(RuntimeError):
        EventCount(df_rdv, df_pde, event_col="diag_name").plot()


def test_to_dict_has_expected_keys(df_rdv, df_pde):
    d = EventCount(df_rdv, df_pde, event_col="diag_name").compute().to_dict()
    assert "table" in d
    assert "plot" in d
    assert "meta" in d


def test_pct_sums_to_one_per_cohort(df_rdv, df_pde):
    obj = EventCount(df_rdv, df_pde, event_col="diag_name").compute()
    for cohort, grp in obj._counts.groupby("cohort"):
        assert abs(grp["patient_pct"].sum() - 1.0) < 0.01
