"""Tests for CategoricalRatios analytics module."""

from __future__ import annotations

import pandas as pd
import pytest

from core.analytics.categorical_ratios import CategoricalRatios

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def df_pde():
    return pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003", "P004", "P005", "P006"],
            "birth_date": pd.to_datetime(["1980-01-01"] * 6),
            "sex_name": ["Female", "Male", "Female", "Male", "Female", "Male"],
        }
    )


@pytest.fixture
def df_two_cohorts():
    """RDV already labelled with two non-overlapping cohorts."""
    return pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003", "P004", "P005", "P006"],
            "cohort": ["Female", "Male", "Female", "Male", "Female", "Male"],
            "ward_code": ["PICU", "NICU", "PICU", "PICU", "NICU", "NICU"],
        }
    )


@pytest.fixture
def df_single_cohort():
    return pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003"],
            "cohort": ["All", "All", "All"],
            "ward_code": ["PICU", "NICU", "PICU"],
        }
    )


@pytest.fixture
def df_overlapping_cohorts():
    """P001 appears in both cohorts — chi-square should be skipped."""
    return pd.DataFrame(
        {
            "project_id": ["P001", "P001", "P002", "P003"],
            "cohort": ["Female", "Male", "Male", "Female"],
            "ward_code": ["PICU", "PICU", "NICU", "NICU"],
        }
    )


# ---------------------------------------------------------------------------
# compute()
# ---------------------------------------------------------------------------


def test_compute_returns_self(df_two_cohorts, df_pde):
    obj = CategoricalRatios(df_two_cohorts, df_pde, col="ward_code")
    result = obj.compute()
    assert result is obj


def test_compute_pcts_sum_to_100(df_two_cohorts, df_pde):
    obj = CategoricalRatios(df_two_cohorts, df_pde, col="ward_code").compute()
    # Each cohort column in _pcts sums to 100%
    for cohort in obj._pcts.columns:
        assert abs(obj._pcts[cohort].sum() - 100.0) < 0.01


def test_compute_result_has_category_column(df_two_cohorts, df_pde):
    obj = CategoricalRatios(df_two_cohorts, df_pde, col="ward_code").compute()
    assert "ward_code" in obj._result.columns


def test_compute_result_has_cohort_columns(df_two_cohorts, df_pde):
    obj = CategoricalRatios(df_two_cohorts, df_pde, col="ward_code").compute()
    assert "Female" in obj._result.columns
    assert "Male" in obj._result.columns


def test_compute_fills_na_with_unknown(df_pde):
    df = pd.DataFrame(
        {
            "project_id": ["P001", "P002"],
            "cohort": ["A", "B"],
            "ward_code": [None, "PICU"],
        }
    )
    obj = CategoricalRatios(df, df_pde, col="ward_code").compute()
    categories = obj._result["ward_code"].tolist()
    assert "Unknown" in categories


def test_compute_categorical_dtype_fills_unknown(df_pde):
    """Categorical dtype columns must not raise when filling missing values.

    Regression test: sex_name is loaded as pd.Categorical from parquet.
    The old fillna("Unknown") raised:
        ValueError: Cannot setitem on a Categorical with a new category (Unknown)
    The fix casts to str first then replaces "nan"/"None" strings.
    """
    df = pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003"],
            "cohort": ["A", "A", "B"],
            "sex_name": pd.Categorical([None, "Female", "Male"], categories=["Female", "Male"]),
        }
    )
    # Must not raise
    obj = CategoricalRatios(df, df_pde, col="sex_name").compute()
    categories = obj._result["sex_name"].tolist()
    assert "Unknown" in categories
    assert "Female" in categories


# ---------------------------------------------------------------------------
# Chi-square test
# ---------------------------------------------------------------------------


def test_chi_square_run_for_two_independent_cohorts(df_pde):
    # All cells must be >= 5 to trigger the test.
    # 5 per cell × 2 wards × 2 cohorts = 20 patients.
    df = pd.DataFrame(
        {
            "project_id": [f"P{i:03d}" for i in range(20)],
            "cohort": ["Female"] * 10 + ["Male"] * 10,
            "ward_code": (["PICU"] * 5 + ["NICU"] * 5) + (["PICU"] * 5 + ["NICU"] * 5),
        }
    )
    pde = pd.DataFrame({"project_id": df["project_id"].unique()})
    obj = CategoricalRatios(df, pde, col="ward_code").compute()
    assert obj._test_result is not None
    assert "Chi-square" in obj._test_result


def test_chi_square_skipped_for_overlapping_cohorts(df_overlapping_cohorts, df_pde):
    obj = CategoricalRatios(df_overlapping_cohorts, df_pde, col="ward_code").compute()
    assert obj._test_result is None


def test_chi_square_skipped_for_single_cohort(df_single_cohort, df_pde):
    obj = CategoricalRatios(df_single_cohort, df_pde, col="ward_code").compute()
    assert obj._test_result is None


def test_chi_square_skipped_when_cell_below_5(df_pde):
    df = pd.DataFrame(
        {
            "project_id": ["P001", "P002", "P003", "P004"],
            "cohort": ["Female", "Female", "Male", "Male"],
            "ward_code": ["PICU", "NICU", "PICU", "NICU"],
        }
    )
    obj = CategoricalRatios(df, df_pde, col="ward_code").compute()
    assert obj._test_result is None


# ---------------------------------------------------------------------------
# plot()
# ---------------------------------------------------------------------------


def test_plot_returns_figure(df_two_cohorts, df_pde):
    import plotly.graph_objects as go

    obj = CategoricalRatios(df_two_cohorts, df_pde, col="ward_code").compute()
    fig = obj.plot()
    assert isinstance(fig, go.Figure)


def test_plot_raises_before_compute(df_two_cohorts, df_pde):
    obj = CategoricalRatios(df_two_cohorts, df_pde, col="ward_code")
    with pytest.raises(RuntimeError):
        obj.plot()


def test_plot_barmode_is_stack(df_two_cohorts, df_pde):
    obj = CategoricalRatios(df_two_cohorts, df_pde, col="ward_code").compute()
    fig = obj.plot()
    assert fig.layout.barmode == "stack"


# ---------------------------------------------------------------------------
# to_dict()
# ---------------------------------------------------------------------------


def test_to_dict_has_expected_keys(df_two_cohorts, df_pde):
    obj = CategoricalRatios(df_two_cohorts, df_pde, col="ward_code").compute()
    d = obj.to_dict()
    assert "meta" in d
    assert "table" in d
    assert "plot" in d


def test_to_dict_meta_contains_col(df_two_cohorts, df_pde):
    obj = CategoricalRatios(df_two_cohorts, df_pde, col="ward_code").compute()
    assert obj.to_dict()["meta"]["col"] == "ward_code"
