"""Distribution plots analysis.

For a numeric column, produces:
  - A scaled kernel-density estimate (density plot) per cohort
  - A boxplot per cohort
  - A summary table with median + 95% bootstrap CI per cohort
  - A Kruskal-Wallis test when 2+ independent cohorts are present

Key behaviours that mirror the R implementation:
  - If ``calc_length=True``, the column is replaced by a computed event-length
    (distinct event days per patient per cohort).
  - Repeated measurements are reduced to one value per patient per cohort
    by taking the median before any test or plot.
  - Single-patient cohorts are handled gracefully (CI shown as N/A).
  - Optional ``filter_col`` / ``filter_val`` pre-filters the RDV before analysis.
  - Optional log transform is applied after length calculation and before
    aggregation.

Replaces: driveanalytics R/gen_distribution_plots.R
          driveanalytics R/utils_plots.R  (get_boot_ci, run_kw_test,
                                           get_event_length)
"""

from __future__ import annotations

from typing import Any, Literal, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

from core.analytics.base import AnalysisBase


Transform = Literal["none", "log"]


# ---------------------------------------------------------------------------
# Helpers (mirror R utils_plots.R)
# ---------------------------------------------------------------------------

def _get_event_length(
    df: pd.DataFrame,
    stratify_by: str,
    calc_diff: bool,
) -> pd.DataFrame:
    """Compute event length (distinct days) per patient per cohort.

    Replaces R ``get_event_length()``.

    Args:
        df:           RDV DataFrame with ``start_datetime`` column.
        stratify_by:  Cohort column name.
        calc_diff:    If True, expand start→end date range and count distinct
                      days.  If False, count distinct start dates.
    """
    df = df.copy()
    df["_start_date"] = pd.to_datetime(df["start_datetime"]).dt.normalize()

    if calc_diff and "end_datetime" in df.columns:
        df["_end_date"] = pd.to_datetime(df["end_datetime"]).dt.normalize()
        # Where end <= start or end is null, use start
        df["_end_date"] = df["_end_date"].where(
            df["_end_date"] > df["_start_date"], df["_start_date"]
        )
        rows = []
        for _, row in df.iterrows():
            for d in pd.date_range(row["_start_date"], row["_end_date"], freq="D"):
                rows.append({
                    "project_id": row["project_id"],
                    stratify_by: row[stratify_by],
                    "_date": d,
                })
        expanded = pd.DataFrame(rows)
        result = (
            expanded.groupby(["project_id", stratify_by])["_date"]
            .nunique()
            .reset_index()
            .rename(columns={"_date": "length"})
        )
    else:
        result = (
            df.groupby(["project_id", stratify_by])["_start_date"]
            .nunique()
            .reset_index()
            .rename(columns={"_start_date": "length"})
        )

    return result


def _boot_median_ci(values: np.ndarray, n_bootstrap: int = 1000) -> tuple[float, str]:
    """Return (median, '95% CI string') for an array of values."""
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return float("nan"), "N/A"
    median = float(np.median(values))
    if len(values) < 5:
        return median, "N/A"
    try:
        res = stats.bootstrap(
            (values,),
            statistic=np.median,
            n_resamples=n_bootstrap,
            confidence_level=0.95,
            method="basic",
        )
        lo = round(float(res.confidence_interval.low), 2)
        hi = round(float(res.confidence_interval.high), 2)
        return median, f"[{lo:.2f}, {hi:.2f}]"
    except Exception:
        return median, "N/A"


def _run_kw_test(
    df: pd.DataFrame,
    stratify_by: str,
    col: str,
    summary: pd.DataFrame,
) -> Optional[str]:
    """Run Kruskal-Wallis test; return result string or explanation of skip.

    Replaces R ``run_kw_test()``.  Conditions mirror the R implementation:
      - Skip if any cohort has < 5 patients
      - Skip if < 2 groups
      - Skip if cohorts share any patients
    """
    if (summary["N Patients"] < 5).any():
        return "No test run — at least one cohort has fewer than 5 patients"
    groups = df[stratify_by].unique()
    if len(groups) < 2:
        return "Test requires at least 2 groups"
    patient_sets = [
        set(df[df[stratify_by] == g]["project_id"].unique())
        for g in groups
        if "project_id" in df.columns
    ]
    if patient_sets and len(set.intersection(*patient_sets)) > 0:
        return "Test requires independent (non-overlapping) groups"

    group_arrays = [
        df[df[stratify_by] == g][col].dropna().values for g in groups
    ]
    stat, p = stats.kruskal(*group_arrays)
    if p < 0.01:
        p_str = "<0.01"
    elif p > 0.9:
        p_str = ">0.90"
    else:
        p_str = f"={p:.2f}"
    return f"Kruskal-Wallis test: p-value{p_str}"


def _scaled_kde(values: np.ndarray, bw_adjust: float = 1.0) -> tuple[np.ndarray, np.ndarray]:
    """Return (x, y_scaled) for a KDE scaled to [0, 1].

    Mirrors R ``geom_density(aes(y = after_stat(scaled)))``.
    """
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return np.array([values[0]] * 2 if len(values) else []), np.array([0.0, 1.0])
    kde = stats.gaussian_kde(values, bw_method=bw_adjust * values.std(ddof=1) / values.std())
    x = np.linspace(values.min(), values.max(), 200)
    y = kde(x)
    return x, y / y.max()  # scale to [0, 1]


# ---------------------------------------------------------------------------
# Analytics class
# ---------------------------------------------------------------------------

class DistributionPlots(AnalysisBase):
    """Distribution analysis: scaled density + boxplot with KW test.

    Args:
        df_rdv:       RDV DataFrame (already cohort-labelled).
        df_pde:       Patient demographics RDV.
        col:          Numeric column to analyse.
        stratify_by:  Column carrying cohort labels (default ``"cohort"``).
        filter_col:   Column to pre-filter on (e.g. ``"ward_code"``).
        filter_val:   Value to keep in ``filter_col`` (e.g. ``"PICU"``).
        calc_length:  Replace ``col`` with computed event-length (days).
        calc_diff:    When ``calc_length=True``, use start→end range vs
                      distinct start dates.
        transform:    ``"log"`` applies log transform; ``"none"`` leaves as-is.
        description:  x-axis label override.
    """

    label = "Distribution"

    def __init__(
        self,
        df_rdv: pd.DataFrame,
        df_pde: pd.DataFrame,
        col: str,
        stratify_by: str = "cohort",
        filter_col: Optional[str] = None,
        filter_val: Optional[str] = None,
        calc_length: bool = False,
        calc_diff: bool = False,
        transform: Transform = "none",
        description: Optional[str] = None,
    ) -> None:
        super().__init__(df_rdv=df_rdv, df_pde=df_pde, cohort_col=stratify_by)
        self.col = col
        self.filter_col = filter_col
        self.filter_val = filter_val
        self.calc_length = calc_length
        self.calc_diff = calc_diff
        self.transform = transform
        self.xlab = description or col.replace("_", " ").capitalize()
        self._summary: Optional[pd.DataFrame] = None
        self._test_result: Optional[str] = None
        self._plot_df: Optional[pd.DataFrame] = None

    def compute(self) -> "DistributionPlots":
        df = self.df_rdv.copy()

        # 1 — optional column filter
        if self.filter_col and self.filter_val is not None:
            df = df[df[self.filter_col].astype(str) == str(self.filter_val)]

        if df.empty:
            self._result = pd.DataFrame()
            self._summary = pd.DataFrame()
            return self

        # 2 — compute event length if requested
        if self.calc_length:
            df = _get_event_length(df, self.cohort_col, self.calc_diff)
            self.col = "length"

        # 3 — ensure numeric
        df[self.col] = pd.to_numeric(df[self.col], errors="coerce")

        # 4 — log transform
        if self.transform == "log":
            positive = df[self.col] > 0
            if positive.all():
                df[self.col] = np.log(df[self.col])
            else:
                df = df[positive]

        # 5 — reduce to one value per patient per cohort (median)
        df = (
            df.groupby(["project_id", self.cohort_col], as_index=False)[self.col]
            .median()
        )

        # 6 — bootstrap CI + summary table
        summary_rows = []
        for cohort_label, grp in df.groupby(self.cohort_col):
            values = grp[self.col].dropna().values
            median, ci = _boot_median_ci(values)
            summary_rows.append({
                "Cohort": cohort_label,
                "N Patients": grp["project_id"].nunique(),
                "Median": round(median, 2),
                "95% Bootstrap CI": ci,
            })
        self._summary = pd.DataFrame(summary_rows)

        # 7 — KW test
        self._test_result = _run_kw_test(df, self.cohort_col, self.col, self._summary)

        self._plot_df = df
        self._result = self._summary
        return self

    def plot(self, side_by_side: bool = True) -> go.Figure:
        """Return a Plotly figure: density (top/left) + boxplot (bottom/right)."""
        self._require_computed()

        if self._plot_df is None or self._plot_df.empty:
            fig = go.Figure()
            fig.add_annotation(text="No data to display", showarrow=False)
            return fig

        df = self._plot_df
        cohort_labels = sorted(df[self.cohort_col].unique())
        # Hex colours — converted to rgba for fill (Plotly requires rgba for opacity)
        colours = [
            "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
            "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
        ]

        if side_by_side:
            fig = make_subplots(rows=1, cols=2, shared_yaxes=False)
            density_pos = (1, 1)
            box_pos = (1, 2)
        else:
            fig = make_subplots(rows=2, cols=1, shared_xaxes=False, row_heights=[0.7, 0.3])
            density_pos = (1, 1)
            box_pos = (2, 1)

        for i, label in enumerate(cohort_labels):
            hex_colour = colours[i % len(colours)]
            r, g, b = int(hex_colour[1:3], 16), int(hex_colour[3:5], 16), int(hex_colour[5:7], 16)
            fill_colour = f"rgba({r},{g},{b},0.3)"
            values = df[df[self.cohort_col] == label][self.col].dropna().values

            # Density
            if len(values) >= 2:
                x_kde, y_kde = _scaled_kde(values)
                fig.add_trace(
                    go.Scatter(
                        x=x_kde, y=y_kde,
                        mode="lines",
                        fill="tozeroy",
                        fillcolor=fill_colour,
                        line=dict(color=hex_colour),
                        name=str(label),
                        legendgroup=str(label),
                        showlegend=True,
                    ),
                    row=density_pos[0], col=density_pos[1],
                )

            # Boxplot
            fig.add_trace(
                go.Box(
                    x=values,
                    name=str(label),
                    marker_color=hex_colour,
                    legendgroup=str(label),
                    showlegend=False,
                    boxpoints="outliers",
                ),
                row=box_pos[0], col=box_pos[1],
            )

        xlab = self.xlab
        if self.transform == "log":
            xlab = f"log({xlab})"
        if self._test_result:
            fig.update_layout(title=self._test_result)

        fig.update_xaxes(title_text=xlab, row=density_pos[0], col=density_pos[1])
        fig.update_yaxes(title_text="Scaled density", row=density_pos[0], col=density_pos[1])
        fig.update_xaxes(title_text=xlab, row=box_pos[0], col=box_pos[1])
        fig.update_layout(legend_title="Cohort")
        return fig

    def to_dict(self) -> dict[str, Any]:
        self._require_computed()
        return {
            "meta": {
                "col": self.col,
                "cohorts": self.cohorts,
                "transform": self.transform,
                "test_result": self._test_result,
            },
            "table": self._summary.to_dict(orient="records") if self._summary is not None else [],
            "plot": self.plot().to_json(),
        }
