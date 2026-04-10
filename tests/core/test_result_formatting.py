"""Tests for analytics result formatting utilities."""

from __future__ import annotations

import pandas as pd
import pytest

from core.analytics.result_formatting import (
    format_percent,
    head_df_cohort,
    tabulate_df_cohort,
)

# ---------------------------------------------------------------------------
# head_df_cohort
# ---------------------------------------------------------------------------


@pytest.fixture
def df_results():
    return pd.DataFrame(
        {
            "event": ["Asthma", "Diabetes", "Hypertension", "COPD", "Pneumonia"],
            "Female": [50.0, 30.0, 20.0, 10.0, 5.0],
            "Male": [40.0, 35.0, 25.0, 15.0, 8.0],
        }
    )


def test_head_df_cohort_returns_top_n(df_results):
    result = head_df_cohort(df_results, n=3, col="Female")
    assert len(result) == 3


def test_head_df_cohort_sorted_descending(df_results):
    result = head_df_cohort(df_results, n=3, col="Female")
    assert result["Female"].iloc[0] >= result["Female"].iloc[1]


def test_head_df_cohort_n_larger_than_rows_returns_all(df_results):
    result = head_df_cohort(df_results, n=100, col="Female")
    assert len(result) == len(df_results)


def test_head_df_cohort_n_none_returns_all(df_results):
    result = head_df_cohort(df_results, n=None, col="Female")
    assert len(result) == len(df_results)


def test_head_df_cohort_n_zero_returns_all(df_results):
    result = head_df_cohort(df_results, n=0, col="Female")
    assert len(result) == len(df_results)


def test_head_df_cohort_default_col_picks_first_numeric(df_results):
    # No col specified — should pick first numeric column (Female)
    result = head_df_cohort(df_results, n=2)
    assert len(result) == 2
    assert result["Female"].iloc[0] >= result["Female"].iloc[1]


def test_head_df_cohort_empty_df():
    df = pd.DataFrame({"event": [], "count": []})
    result = head_df_cohort(df, n=5, col="count")
    assert result.empty


def test_head_df_cohort_unknown_col_falls_back(df_results):
    # Unknown col should not raise
    result = head_df_cohort(df_results, n=3, col="nonexistent_col")
    assert len(result) == 3


# ---------------------------------------------------------------------------
# tabulate_df_cohort
# ---------------------------------------------------------------------------


def test_tabulate_prettifies_column_names():
    df = pd.DataFrame({"event_count": [1, 2], "cohort_label": ["A", "B"]})
    result = tabulate_df_cohort(df)
    assert "Event Count" in result.columns
    assert "Cohort Label" in result.columns


def test_tabulate_formats_percent_columns():
    df = pd.DataFrame({"event": ["A", "B"], "pct": [12.5678, 87.4322]})
    result = tabulate_df_cohort(df, cols_percent=["pct"])
    assert result["Pct"].iloc[0] == "12.57%"
    assert result["Pct"].iloc[1] == "87.43%"


def test_tabulate_handles_nan_in_percent():
    import numpy as np

    df = pd.DataFrame({"event": ["A"], "pct": [float("nan")]})
    result = tabulate_df_cohort(df, cols_percent=["pct"])
    assert result["Pct"].iloc[0] == ""


def test_tabulate_no_percent_cols_leaves_values():
    df = pd.DataFrame({"count": [10, 20]})
    result = tabulate_df_cohort(df)
    assert result["Count"].iloc[0] == 10


def test_tabulate_returns_dataframe():
    df = pd.DataFrame({"a": [1], "b": [2]})
    assert isinstance(tabulate_df_cohort(df), pd.DataFrame)


# ---------------------------------------------------------------------------
# format_percent
# ---------------------------------------------------------------------------


def test_format_percent_fraction():
    assert format_percent(0.753) == "75.3%"


def test_format_percent_percentage():
    assert format_percent(75.3) == "75.3%"


def test_format_percent_zero():
    assert format_percent(0.0) == "0.0%"


def test_format_percent_nan_returns_empty():
    import numpy as np

    assert format_percent(float("nan")) == ""


def test_format_percent_custom_decimals():
    assert format_percent(0.5, decimals=2) == "50.00%"
