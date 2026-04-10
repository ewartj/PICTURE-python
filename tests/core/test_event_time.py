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
    assert EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute() is not None


def test_compute_event_length_days(df_rdv, df_pde):
    obj = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute()
    # Asthma cohort A: P001 Jan 1→10 = 9 days; median for single record = 9
    asthma_a = obj._summary[(obj._summary["Event"] == "Asthma") & (obj._summary["Cohort"] == "A")]
    assert asthma_a["Median"].iloc[0] == 9.0


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

    obj = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name", plot_type="histogram").compute()
    assert isinstance(obj.plot(), go.Figure)


def test_log_scale(df_rdv, df_pde):
    import plotly.graph_objects as go

    obj = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name", log_scale=True).compute()
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
    # No end_datetime → duration = 0; median for the single record = 0
    assert obj._summary["Median"].iloc[0] == 0.0


def test_no_raw_df_attribute_after_compute(df_rdv, df_pde):
    """_df must not exist on EventTimeAnalysis — raw rows are not retained.

    Regression test: the old implementation stored all raw rows in self._df,
    causing high memory usage on large RDVs. The refactor replaced it with
    pre-aggregated self._summary and self._hist.
    """
    obj = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute()
    assert not hasattr(
        obj, "_df"
    ), "_df must not exist; use _summary / _hist for aggregated storage"


def test_hist_attribute_populated_after_compute(df_rdv, df_pde):
    """_hist must be populated after compute() for histogram plotting."""
    obj = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute()
    assert hasattr(obj, "_hist")
    assert len(obj._hist) > 0
    # Each value is a (counts, edges) tuple of numpy arrays
    for (event, cohort), (counts, edges) in obj._hist.items():
        assert isinstance(event, str)
        assert isinstance(cohort, str)
        assert len(edges) == len(counts) + 1


def test_top_n_limits_plot_events(df_pde):
    """top_n must limit the number of events shown in the plot."""
    df = pd.DataFrame(
        {
            "project_id": [f"P{i:03d}" for i in range(6)],
            "cohort": ["A"] * 6,
            "diag_name": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta"],
            "start_datetime": pd.to_datetime(["2021-01-01"] * 6),
            "end_datetime": pd.to_datetime(["2021-01-10"] * 6),
        }
    )
    obj = EventTimeAnalysis(df, df_pde, event_col="diag_name", top_n=3).compute()
    fig = obj.plot()
    # Each trace covers all top-N events on the x-axis; the x values
    # of any trace must not exceed top_n distinct events.
    plotted_events = set(fig.data[0].x) if fig.data else set()
    assert len(plotted_events) <= 3


def test_boxplot_uses_precomputed_stats(df_rdv, df_pde):
    """Boxplot traces must carry q1/median/q3 rather than raw data points.

    This confirms the pre-aggregated boxplot path (go.Box with lowerfence /
    q1 / median / q3 / upperfence) rather than the old approach that passed
    raw row values and required self._df.
    """
    import plotly.graph_objects as go

    obj = EventTimeAnalysis(df_rdv, df_pde, event_col="diag_name").compute()
    fig = obj.plot()
    assert isinstance(fig, go.Figure)
    assert len(fig.data) > 0
    trace = fig.data[0]
    assert isinstance(trace, go.Box)
    assert trace.q1 is not None
    assert trace.median is not None
    assert trace.q3 is not None
