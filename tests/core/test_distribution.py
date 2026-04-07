"""Tests for DistributionPlots analytics module and helper functions."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.analytics.distribution import (
    DistributionPlots,
    _boot_median_ci,
    _get_event_length,
    _run_kw_test,
    _scaled_kde,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def df_pde():
    return pd.DataFrame({
        "project_id": [f"P{i:03d}" for i in range(1, 13)],
        "birth_date":  pd.to_datetime(["1980-01-01"] * 12),
    })


@pytest.fixture
def df_two_cohorts():
    """12 patients split evenly across two cohorts with numeric values."""
    rng = np.random.default_rng(42)
    return pd.DataFrame({
        "project_id":    [f"P{i:03d}" for i in range(1, 13)],
        "cohort":        ["A"] * 6 + ["B"] * 6,
        "value":         list(rng.integers(1, 20, 6)) + list(rng.integers(20, 40, 6)),
        "start_datetime": pd.to_datetime(["2021-01-01"] * 12),
        "end_datetime":   pd.to_datetime(["2021-01-10"] * 12),
    })


# ---------------------------------------------------------------------------
# _boot_median_ci
# ---------------------------------------------------------------------------

def test_boot_median_ci_returns_tuple():
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    median, ci = _boot_median_ci(values)
    assert isinstance(median, float)
    assert isinstance(ci, str)


def test_boot_median_ci_correct_median():
    values = np.array([10.0] * 10)
    median, _ = _boot_median_ci(values)
    assert median == 10.0


def test_boot_median_ci_empty_returns_nan():
    median, ci = _boot_median_ci(np.array([]))
    assert np.isnan(median)
    assert ci == "N/A"


def test_boot_median_ci_too_few_values_returns_na():
    _, ci = _boot_median_ci(np.array([1.0, 2.0]))
    assert ci == "N/A"


def test_boot_median_ci_ignores_nans():
    values = np.array([1.0, np.nan, 3.0, np.nan, 5.0, 6.0, 7.0, 8.0])
    median, ci = _boot_median_ci(values)
    assert not np.isnan(median)


# ---------------------------------------------------------------------------
# _scaled_kde
# ---------------------------------------------------------------------------

def test_scaled_kde_returns_arrays():
    values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    x, y = _scaled_kde(values)
    assert len(x) == len(y)
    assert len(x) > 0


def test_scaled_kde_y_bounded_zero_to_one():
    values = np.linspace(1, 100, 50)
    _, y = _scaled_kde(values)
    assert y.min() >= 0.0
    assert y.max() <= 1.0 + 1e-9


def test_scaled_kde_single_value():
    x, y = _scaled_kde(np.array([5.0]))
    assert len(x) == len(y)


# ---------------------------------------------------------------------------
# _get_event_length
# ---------------------------------------------------------------------------

def test_get_event_length_count_distinct_days():
    df = pd.DataFrame({
        "project_id":     ["P001", "P001", "P002"],
        "cohort":         ["A", "A", "A"],
        "start_datetime": pd.to_datetime(["2021-01-01", "2021-01-03", "2021-01-01"]),
    })
    result = _get_event_length(df, stratify_by="cohort", calc_diff=False)
    p001_len = result[result["project_id"] == "P001"]["length"].iloc[0]
    assert p001_len == 2  # two distinct start dates


def test_get_event_length_calc_diff_expands_range():
    df = pd.DataFrame({
        "project_id":     ["P001"],
        "cohort":         ["A"],
        "start_datetime": pd.to_datetime(["2021-01-01"]),
        "end_datetime":   pd.to_datetime(["2021-01-05"]),
    })
    result = _get_event_length(df, stratify_by="cohort", calc_diff=True)
    assert result["length"].iloc[0] == 5  # Jan 1–5 inclusive = 5 days


# ---------------------------------------------------------------------------
# _run_kw_test
# ---------------------------------------------------------------------------

def test_run_kw_test_runs_for_two_groups(df_two_cohorts):
    summary = pd.DataFrame({
        "cohort": ["A", "B"],
        "N Patients": [6, 6],
    })
    result = _run_kw_test(df_two_cohorts, "cohort", "value", summary)
    assert result is not None
    assert "Kruskal-Wallis" in result


def test_run_kw_test_skips_small_cohort():
    df = pd.DataFrame({
        "project_id": ["P001", "P002", "P003"],
        "cohort":     ["A", "A", "B"],
        "value":      [1.0, 2.0, 3.0],
    })
    summary = pd.DataFrame({"cohort": ["A", "B"], "N Patients": [2, 1]})
    result = _run_kw_test(df, "cohort", "value", summary)
    assert "fewer than 5" in result


def test_run_kw_test_skips_single_group():
    df = pd.DataFrame({
        "project_id": [f"P{i:03d}" for i in range(10)],
        "cohort":     ["A"] * 10,
        "value":      list(range(10)),
    })
    # N Patients >= 5 so the <5 guard doesn't fire first
    summary = pd.DataFrame({"cohort": ["A"], "N Patients": [10]})
    result = _run_kw_test(df, "cohort", "value", summary)
    assert "2 groups" in result


def test_run_kw_test_skips_overlapping_groups():
    df = pd.DataFrame({
        "project_id": ["P001", "P001", "P002", "P002", "P003", "P003",
                       "P004", "P004", "P005", "P005"],
        "cohort":     ["A", "B"] * 5,
        "value":      list(range(10)),
    })
    summary = pd.DataFrame({"cohort": ["A", "B"], "N Patients": [5, 5]})
    result = _run_kw_test(df, "cohort", "value", summary)
    assert "non-overlapping" in result


# ---------------------------------------------------------------------------
# DistributionPlots class
# ---------------------------------------------------------------------------

def test_distribution_compute_returns_self(df_two_cohorts, df_pde):
    obj = DistributionPlots(df_two_cohorts, df_pde, col="value").compute()
    assert obj is not None


def test_distribution_summary_has_both_cohorts(df_two_cohorts, df_pde):
    obj = DistributionPlots(df_two_cohorts, df_pde, col="value").compute()
    assert "A" in obj._summary["Cohort"].values
    assert "B" in obj._summary["Cohort"].values


def test_distribution_plot_returns_figure(df_two_cohorts, df_pde):
    import plotly.graph_objects as go
    obj = DistributionPlots(df_two_cohorts, df_pde, col="value").compute()
    fig = obj.plot()
    assert isinstance(fig, go.Figure)


def test_distribution_plot_side_by_side(df_two_cohorts, df_pde):
    import plotly.graph_objects as go
    obj = DistributionPlots(df_two_cohorts, df_pde, col="value").compute()
    fig = obj.plot(side_by_side=True)
    assert isinstance(fig, go.Figure)


def test_distribution_raises_before_compute(df_two_cohorts, df_pde):
    obj = DistributionPlots(df_two_cohorts, df_pde, col="value")
    with pytest.raises(RuntimeError):
        obj.plot()


def test_distribution_to_dict_keys(df_two_cohorts, df_pde):
    obj = DistributionPlots(df_two_cohorts, df_pde, col="value").compute()
    d = obj.to_dict()
    assert "summary" in d or "table" in d  # either key is acceptable
    assert "plot" in d


def test_distribution_filter_col(df_pde):
    df = pd.DataFrame({
        "project_id":    [f"P{i:03d}" for i in range(1, 13)],
        "cohort":        ["A"] * 6 + ["B"] * 6,
        "value":         list(range(1, 13)),
        "ward_code":     ["PICU"] * 6 + ["NICU"] * 6,
        "start_datetime": pd.to_datetime(["2021-01-01"] * 12),
        "end_datetime":   pd.to_datetime(["2021-01-10"] * 12),
    })
    obj = DistributionPlots(
        df, df_pde, col="value", filter_col="ward_code", filter_val="PICU"
    ).compute()
    # Only PICU rows should remain → only cohort A
    assert set(obj._summary["Cohort"].values) == {"A"}


def test_distribution_log_transform(df_two_cohorts, df_pde):
    obj = DistributionPlots(
        df_two_cohorts, df_pde, col="value", transform="log"
    ).compute()
    assert obj is not None
