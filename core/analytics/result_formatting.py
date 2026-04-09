"""
Analysis result formatting.

Mirrors driveanalytics R/utils_result_formatting.R.

Provides helpers to truncate result DataFrames to the top-N rows and to
render them in different output formats (plain DataFrame, Streamlit
st.dataframe-ready, or a dict for the API).

The R version also targets kable (LaTeX PDF) and DT (interactive HTML).
The Python equivalents are:
  - plain  → pd.DataFrame (suitable for st.dataframe)
  - dict   → list[dict]   (suitable for JSON API responses)

Usage::

    from core.analytics.result_formatting import head_df_cohort, tabulate_df_cohort

    top10 = head_df_cohort(df, n=10, col="count")
    display_df = tabulate_df_cohort(top10, cols_percent=["percent"])
"""

from __future__ import annotations

from typing import Optional

import pandas as pd


def head_df_cohort(
    df: pd.DataFrame,
    n: Optional[int] = None,
    col: Optional[str] = None,
    by: Optional[str] = None,
) -> pd.DataFrame:
    """Return the top *n* rows of a cohort result DataFrame, sorted descending.

    Mirrors R ``head_df_cohort(df, n, col, by)``.

    Args:
        df:  Result DataFrame (one row per event/category, one column per cohort).
        n:   Number of rows to return.  None / ≤0 returns all rows.
        col: Column name to sort by.  Defaults to the first non-index column.
        by:  Deprecated alias for *col* (kept for API compatibility).

    Returns:
        Sorted DataFrame with at most *n* rows.
    """
    if df.empty:
        return df

    sort_col = col or by
    if sort_col is None:
        # Pick the first numeric column
        numeric_cols = df.select_dtypes(include="number").columns.tolist()
        sort_col = numeric_cols[0] if numeric_cols else df.columns[0]

    if sort_col not in df.columns:
        sort_col = df.columns[0]

    df_sorted = df.sort_values(sort_col, ascending=False)

    if n and n > 0 and n < len(df_sorted):
        df_sorted = df_sorted.head(n)

    return df_sorted.reset_index(drop=True)


def tabulate_df_cohort(
    df: pd.DataFrame,
    cols_percent: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Format a result DataFrame for display.

    Mirrors R ``tabulate_df_cohort(df, format=NULL, cols_percent)``.

    - Percent columns are formatted as "##.##%".
    - Column names have underscores replaced with spaces and are title-cased
      (e.g. ``event_count`` → ``Event Count``).

    Args:
        df:            Input DataFrame.
        cols_percent:  Column names to format as percentage strings.

    Returns:
        Formatted DataFrame suitable for ``st.dataframe`` or JSON serialisation.
    """
    df = df.copy()

    # Format percent columns
    for col in cols_percent or []:
        if col in df.columns:
            df[col] = df[col].apply(lambda v: f"{v:.2f}%" if pd.notna(v) else "")

    # Prettify column names
    df.columns = [c.replace("_", " ").replace(".", " ").title() for c in df.columns]

    return df


def format_percent(value: float, decimals: int = 1) -> str:
    """Format a fraction (0–1) or percentage (0–100) as '##.#%'.

    Values ≤1 are assumed to be fractions and multiplied by 100.
    """
    if pd.isna(value):
        return ""
    if 0.0 <= value <= 1.0:
        value = value * 100
    return f"{value:.{decimals}f}%"
