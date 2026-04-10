"""
Event count analysis.

Counts how many events each patient has per cohort, including patients
with zero events, and plots the distribution as an overlapping histogram.

Replaces: driveanalytics R/gen_event_count.R
"""

from __future__ import annotations

from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go

from core.analytics._colours import cohort_colour
from core.analytics.base import AnalysisBase


class EventCount(AnalysisBase):
    """Distribution of event counts per patient by cohort.

    Includes patients with zero events so the full denominator is shown.

    Args:
        df_rdv:       RDV DataFrame (already cohort-labelled).
        df_pde:       Patient demographics RDV (used for zero-count denominator).
        event_col:    Column carrying the event name / category.
        cohort_col:   Column carrying cohort labels (default ``"cohort"``).
        count_unique: If True (default), deduplicate (cohort_id, event) rows
                      before counting so repeat records are collapsed.
    """

    label = "Event Count"

    def __init__(
        self,
        df_rdv: pd.DataFrame,
        df_pde: pd.DataFrame,
        event_col: str,
        cohort_col: str = "cohort",
        count_unique: bool = True,
    ) -> None:
        super().__init__(df_rdv=df_rdv, df_pde=df_pde, cohort_col=cohort_col)
        self.event_col = event_col
        self.count_unique = count_unique

    def compute(self) -> "EventCount":
        # Select only needed columns before copying — avoids holding the full RDV.
        id_col = "cohort_id" if "cohort_id" in self.df_rdv.columns else "project_id"
        df = (
            self.df_rdv[[id_col, self.event_col, self.cohort_col]]
            .dropna(subset=[self.event_col])
            .copy()
        )

        if self.count_unique:
            df = df.drop_duplicates()

        # Non-zero counts: events per patient-period per cohort
        nonzero = (
            df.groupby([id_col, self.cohort_col])
            .size()
            .reset_index(name="event_count")
            .groupby([self.cohort_col, "event_count"])
            .size()
            .reset_index(name="patient_count")
        )

        # Total patients per cohort: use df_pde as denominator so patients
        # with zero events (absent from df_rdv) are still counted.
        n_patients = (
            self.df_pde.groupby(self.cohort_col)["project_id"]
            .nunique()
            .reset_index(name="n_proj_ids")
        )

        n_nonzero = (
            nonzero.groupby(self.cohort_col)["patient_count"].sum().reset_index(name="n_nonzero")
        )
        zero = n_patients.merge(n_nonzero, on=self.cohort_col, how="left")
        zero["n_nonzero"] = zero["n_nonzero"].fillna(0)
        zero["event_count"] = 0
        zero["patient_count"] = (zero["n_proj_ids"] - zero["n_nonzero"]).clip(lower=0).astype(int)
        zero = zero[[self.cohort_col, "event_count", "patient_count"]]

        counts = pd.concat([nonzero, zero], ignore_index=True).sort_values(
            [self.cohort_col, "event_count"]
        )
        counts["patient_pct"] = counts.groupby(self.cohort_col)["patient_count"].transform(
            lambda x: x / x.sum() if x.sum() > 0 else x
        )

        self._counts = counts
        # Wide summary: event_count, {cohort}.count, {cohort}.frequency
        wide = counts.rename(columns={"patient_count": "count", "patient_pct": "frequency"})
        wide = wide.pivot_table(
            index="event_count",
            columns=self.cohort_col,
            values=["count", "frequency"],
            fill_value=0,
        )
        wide.columns = [f"{cohort}.{metric}" for metric, cohort in wide.columns]
        self._result = wide.reset_index().rename(columns={"event_count": "Number of events"})
        return self

    def plot(self) -> go.Figure:
        """Return an overlapping histogram of event counts per patient."""
        self._require_computed()
        fig = go.Figure()
        for i, cohort in enumerate(self.cohorts):
            grp = self._counts[self._counts[self.cohort_col] == cohort]
            hex_c = cohort_colour(i)
            r, g, b = int(hex_c[1:3], 16), int(hex_c[3:5], 16), int(hex_c[5:7], 16)
            fig.add_trace(
                go.Bar(
                    x=grp["event_count"],
                    y=grp["patient_count"],
                    name=str(cohort),
                    marker_color=f"rgba({r},{g},{b},0.6)",
                    marker_line_color=hex_c,
                    marker_line_width=1,
                )
            )
        fig.update_layout(
            barmode="overlay",
            title=f"Event count — {self.event_col}",
            xaxis_title="Number of events per patient",
            yaxis_title="Number of patients",
            xaxis=dict(dtick=1),
            legend_title="Cohort",
        )
        return fig

    def to_dict(self) -> dict[str, Any]:
        self._require_computed()
        return {
            "table": self._result.to_dict(orient="records"),
            "plot": self.plot().to_json(),
            "meta": {
                "event_col": self.event_col,
                "cohorts": self.cohorts,
            },
        }
