"""Tests for EventTimeAnalysis analytics module."""

from __future__ import annotations
import pandas as pd
import pytest
from core.analytics.event_time import EventTimeAnalysis


@pytest.fixture
def df_pde():
    return pd.DataFrame({"project_id": [f"P{i:03d}" for i in range(1, 5)]})


@pytest.fixture
def df_rdv():
    return pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003", "P004"],
            "cohort": ["A", "A", "B", "B"],
            "diag_name": ["Asthma", "COPD", "Asthma", "COPD"],
            "start_datetime": pd.to_datetime(
                ["2021-01-01", "2021-01-01", "2021-03-01", "2021-03-01"]
            ),
            "end_datetime": pd.to_datetime(
                ["2021-01-10", "2021-01-20", "2021-03-15", "2021-04-01"]
            ),
        }
    )


def test_compute_returns_self(df_rdv, df_pde):
    assert (
        EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute() is not None
    )


def test_compute_event_length_days(df_rdv, df_pde):
    obj = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute()
    # P001: Jan 1 to Jan 10 = 9 days
    assert (
        obj._df.loc[obj._df["project_id"] == "P001", "event_length_days"].iloc[0] == 9
    )


def test_summary_has_median(df_rdv, df_pde):
    obj = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute()
    assert "Median" in obj._summary.columns


def test_summary_contains_events(df_rdv, df_pde):
    obj = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute()
    assert set(obj._summary["Event"].unique()) == {"Asthma", "COPD"}


def test_boxplot_returns_figure(df_rdv, df_pde):
    import plotly.graph_objects as go

    obj = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute()
    assert isinstance(obj.plot(), go.Figure)


def test_histogram_returns_figure(df_rdv, df_pde):
    import plotly.graph_objects as go

    obj = EventTimeAnalysis(
        df_rdv, df_pde, event_col="diag_name", plot_type="histogram"
    ).compute()
    assert isinstance(obj.plot(), go.Figure)


def test_log_scale(df_rdv, df_pde):
    import plotly.graph_objects as go

    obj = EventTimeAnalysis(
        df_rdv, df_pde, event_col="diag_name", log_scale=True
    ).compute()
    assert isinstance(obj.plot(), go.Figure)


def test_raises_before_compute(df_rdv, df_pde):
    with pytest.raises(RuntimeError):
        EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").plot()


def test_to_dict_keys(df_rdv, df_pde):
    d = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute().to_dict()
    assert "summary" in d and "plot" in d and "meta" in d


def test_missing_end_datetime_defaults_to_zero_length(df_pde):
    df = pd.DataFrame(
        {
            "project_id": ["P001"],
            "cohort": ["A"],
            "diag_name": ["Asthma"],
            "start_datetime": pd.to_datetime(["2021-01-01"]),
        }
    )
    obj = EventTimeAnalysis(df, df_pde, event_col="diag_name").compute()
    assert obj._df["event_length_days"].iloc[0] == 0
