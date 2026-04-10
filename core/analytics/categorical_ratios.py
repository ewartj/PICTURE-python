"""Categorical ratios analysis.

Produces a 100%-stacked bar chart showing the breakdown of a categorical
column per cohort, plus a chi-square test of independence when exactly two
non-overlapping cohorts are present.

Replaces: driveanalytics R/gen_categorical_ratios.R
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go
from scipy.stats import chi2_contingency

from core.analytics.base import AnalysisBase
from core.constants import UNKNOWN_CATEGORY


class CategoricalRatios(AnalysisBase):
    """100%-stacked bar of a categorical column split by cohort.

    Args:
        df_rdv:      RDV DataFrame with cohort labels applied.
        df_pde:      Patient demographics RDV.
        col:         Column to analyse (e.g. ``"sex_name"``).
        stratify_by: Column carrying cohort labels (default ``"cohort"``).
    """

    label = "Categorical Ratios"

    def __init__(
        self,
        df_rdv: pd.DataFrame,
        df_pde: pd.DataFrame,
        col: str,
        stratify_by: str = "cohort",
    ) -> None:
        super().__init__(df_rdv=df_rdv, df_pde=df_pde, cohort_col=stratify_by)
        self.col = col
        self._test_result: Optional[str] = None

    def compute(self) -> "CategoricalRatios":
        df = self.df_rdv[[self.cohort_col, self.col]].copy()
        # Cast to str first so Categorical columns accept the "Unknown" fill value.
        # astype(str) turns NaN → "nan" and None → "None"; normalise both to "Unknown".
        df[self.col] = (
            df[self.col].astype(str).replace({"nan": UNKNOWN_CATEGORY, "None": UNKNOWN_CATEGORY})
        )

        # Counts: rows = category values, columns = cohort labels
        counts = df.groupby([self.cohort_col, self.col]).size().unstack(fill_value=0)

        # Percentages (each cohort column sums to 100)
        pcts = counts.div(counts.sum(axis=1), axis=0) * 100

        self._counts = counts.T  # categories as rows, cohorts as columns
        self._pcts = pcts.T

        # Chi-square test — only for exactly 2 non-overlapping cohorts with
        # all cells >= 5 (mirrors the R guard conditions)
        cohort_labels = self.cohorts
        if len(cohort_labels) == 2:
            grp0 = (
                set(df[df[self.cohort_col] == cohort_labels[0]]["project_id"].unique())
                if "project_id" in df.columns
                else set()
            )
            grp1 = (
                set(df[df[self.cohort_col] == cohort_labels[1]]["project_id"].unique())
                if "project_id" in df.columns
                else set()
            )
            no_overlap = len(grp0 & grp1) == 0
            all_cells_ok = (self._counts.values >= 5).all()

            if no_overlap and all_cells_ok:
                contingency = self._counts.values
                _, p, _, _ = chi2_contingency(contingency)
                if p < 0.01:
                    p_str = "<0.01"
                elif p > 0.9:
                    p_str = ">0.90"
                else:
                    p_str = f"={p:.2f}"
                self._test_result = f"Chi-square test p-value{p_str}"

        self._result = self._pcts.reset_index().rename(columns={"index": self.col})
        return self

    def plot(self) -> go.Figure:
        """Return a 100%-stacked Plotly bar chart."""
        self._require_computed()

        fig = go.Figure()
        for category in self._pcts.index:
            fig.add_trace(
                go.Bar(
                    name=str(category),
                    x=self._pcts.columns.tolist(),
                    y=self._pcts.loc[category].tolist(),
                )
            )

        title = self.col.replace("_", " ").title()
        if self._test_result:
            title += f"  ({self._test_result})"

        fig.update_layout(
            barmode="stack",
            title=title,
            xaxis_title="Cohort",
            yaxis_title="Fraction of Cohort (%)",
            yaxis=dict(range=[0, 100]),
            legend_title=self.col.replace("_", " ").title(),
        )
        return fig

    def to_dict(self) -> dict[str, Any]:
        self._require_computed()
        table = self._result.copy()
        # Round percentages for the API response
        for col in table.columns:
            if col != self.col:
                table[col] = table[col].round(2)
        return {
            "meta": {
                "col": self.col,
                "cohorts": self.cohorts,
                "test_result": self._test_result,
            },
            "table": table.to_dict(orient="records"),
            "plot": self.plot().to_json(),
        }
