"""
Tests for FrequencyAnalysis.

These tests use the same dummy CSV data as the R package tests.
Run with: pytest tests/core/test_frequency.py
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.analytics.frequency import FrequencyAnalysis


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
            "cohort": ["All", "All", "All", "All"],
        }
    )


@pytest.fixture
def df_dia(df_pde):
    return pd.DataFrame(
        {
            "project_id": ["P001", "P001", "P002", "P003", "P004", "P004"],
            "diag_name": [
                "Asthma",
                "Diabetes",
                "Asthma",
                "Hypertension",
                "Asthma",
                "Diabetes",
            ],
            "start_datetime": pd.to_datetime(
                [
                    "2020-01-01",
                    "2020-03-01",
                    "2020-02-01",
                    "2021-01-01",
                    "2021-06-01",
                    "2021-07-01",
                ]
            ),
            "end_datetime": pd.to_datetime(
                [
                    "2020-01-02",
                    "2020-03-02",
                    "2020-02-02",
                    "2021-01-02",
                    "2021-06-02",
                    "2021-07-02",
                ]
            ),
            "cohort_id": [
                "P001-000001",
                "P001-000001",
                "P002-000001",
                "P003-000001",
                "P004-000001",
                "P004-000001",
            ],
            "cohort": ["All", "All", "All", "All", "All", "All"],
        }
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_compute_returns_self(df_dia, df_pde):
    analysis = FrequencyAnalysis(df_dia, df_pde, event_col="diag_name")
    result = analysis.compute()
    assert result is analysis


def test_result_has_event_column(df_dia, df_pde):
    analysis = FrequencyAnalysis(df_dia, df_pde, event_col="diag_name").compute()
    df = analysis.tabulate()
    assert "event" in df.columns


def test_result_has_count_and_frequency_columns(df_dia, df_pde):
    analysis = FrequencyAnalysis(df_dia, df_pde, event_col="diag_name").compute()
    df = analysis.tabulate()
    count_cols = [c for c in df.columns if c.endswith(".count")]
    freq_cols = [c for c in df.columns if c.endswith(".frequency")]
    assert len(count_cols) > 0
    assert len(freq_cols) > 0


def test_correct_event_counts(df_dia, df_pde):
    analysis = FrequencyAnalysis(df_dia, df_pde, event_col="diag_name").compute()
    df = analysis.tabulate().set_index("event")
    # Asthma appears in P001, P002, P004 → count = 3
    assert df.loc["Asthma", "All.count"] == 3
    # Diabetes appears in P001, P004 → count = 2
    assert df.loc["Diabetes", "All.count"] == 2
    # Hypertension appears in P003 only → count = 1
    assert df.loc["Hypertension", "All.count"] == 1


def test_frequency_is_proportion_of_cohort(df_dia, df_pde):
    analysis = FrequencyAnalysis(df_dia, df_pde, event_col="diag_name").compute()
    df = analysis.tabulate().set_index("event")
    # 4 patients in cohort, Asthma in 3 → frequency = 0.75
    assert df.loc["Asthma", "All.frequency"] == pytest.approx(0.75)


def test_plot_returns_figure(df_dia, df_pde):
    import plotly.graph_objects as go

    analysis = FrequencyAnalysis(df_dia, df_pde, event_col="diag_name").compute()
    fig = analysis.plot()
    assert isinstance(fig, go.Figure)


def test_to_dict_is_json_serialisable(df_dia, df_pde):
    import json

    analysis = FrequencyAnalysis(df_dia, df_pde, event_col="diag_name").compute()
    result = analysis.to_dict()
    # Should not raise
    json.dumps({"table": result["table"], "meta": result["meta"]})


def test_head_returns_top_n(df_dia, df_pde):
    analysis = FrequencyAnalysis(df_dia, df_pde, event_col="diag_name").compute()
    top2 = analysis.head(n=2)
    assert len(top2) == 2


def test_requires_compute_before_plot(df_dia, df_pde):
    analysis = FrequencyAnalysis(df_dia, df_pde, event_col="diag_name")
    with pytest.raises(RuntimeError):
        analysis.plot()


def test_empty_dataframe_returns_empty_result(df_pde):
    df_empty = pd.DataFrame(columns=["project_id", "diag_name", "cohort_id", "cohort"])
    analysis = FrequencyAnalysis(df_empty, df_pde, event_col="diag_name").compute()
    assert len(analysis.tabulate()) == 0
