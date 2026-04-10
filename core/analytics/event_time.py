"""
Event time analysis.

Computes the duration of each event (end_datetime − start_datetime in days)
and produces descriptive statistics and a boxplot or histogram per event,
faceted by cohort.

Replaces: driveanalytics R/gen_event_time_analysis.R
"""

from __future__ import annotations

from typing import Any, Literal, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from core.analytics.base import AnalysisBase

PlotType = Literal["boxplot", "histogram"]

_COLOURS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
]


class EventTimeAnalysis(AnalysisBase):
    """Duration analysis for each event category.

    Computes ``event_length_days = end_datetime - start_datetime`` for every
    row, then summarises and plots the distribution per event and cohort.

    Args:
        df_rdv:      RDV DataFrame (already cohort-labelled, must have
                     ``start_datetime`` and ``end_datetime`` columns).
        df_pde:      Patient demographics RDV.
        event_col:   Column carrying the event category (e.g. ``"diag_name"``).
        cohort_col:  Column carrying cohort labels (default ``"cohort"``).
        plot_type:   ``"boxplot"`` (default) or ``"histogram"``.
        log_scale:   If True, apply log10 to durations before plotting.
    """

    label = "Event Time Analysis"

    def __init__(
        self,
        df_rdv: pd.DataFrame,
        df_pde: pd.DataFrame,
        event_col: str,
        cohort_col: str = "cohort",
        plot_type: PlotType = "boxplot",
        log_scale: bool = False,
    ) -> None:
        super().__init__(df_rdv=df_rdv, df_pde=df_pde, cohort_col=cohort_col)
        self.event_col = event_col
        self.plot_type = plot_type
        self.log_scale = log_scale

    def compute(self) -> "EventTimeAnalysis":
        # Select only the columns we need upfront.
        cols = list(
            dict.fromkeys(
                ["project_id", self.event_col, self.cohort_col, "start_datetime"]
                + (["end_datetime"] if "end_datetime" in self.df_rdv.columns else [])
            )
        )
        df = self.df_rdv[cols].dropna(subset=[self.event_col]).copy()

        df["start_dt"] = pd.to_datetime(df["start_datetime"]).dt.normalize()
        if "end_datetime" in df.columns:
            df["end_dt"] = pd.to_datetime(df["end_datetime"]).dt.normalize()
        else:
            df["end_dt"] = df["start_dt"]

        df["event_length_days"] = (df["end_dt"] - df["start_dt"]).dt.days.clip(lower=0)
        df["_event"] = df[self.event_col].astype(str)
        df["_cohort"] = df[self.cohort_col].astype(str)

        # Store only columns needed for plotting (drop raw datetime columns).
        self._df = df[
            ["project_id", "_event", "_cohort", "event_length_days"]
        ].reset_index(drop=True)

        summary = (
            self._df.dropna(subset=["event_length_days"])
            .groupby(["_event", "_cohort"])["event_length_days"]
            .describe(percentiles=[0.25, 0.5, 0.75])
            .reset_index()
            .rename(
                columns={
                    "_event": "Event",
                    "_cohort": "Cohort",
                    "count": "N",
                    "mean": "Mean",
                    "std": "SD",
                    "min": "Min",
                    "25%": "Q1",
                    "50%": "Median",
                    "75%": "Q3",
                    "max": "Max",
                }
            )
        )
        for col in ["Mean", "SD", "Min", "Q1", "Median", "Q3", "Max"]:
            if col in summary.columns:
                summary[col] = summary[col].round(1)

        self._summary = summary
        self._result = summary
        return self

    def plot(self) -> go.Figure:
        """Return boxplot or histogram faceted by event and cohort."""
        self._require_computed()
        df = self._df.dropna(subset=["event_length_days"])
        events = sorted(df["_event"].unique())
        cohorts = df["_cohort"].unique().tolist()

        y_label = "log₁₀(Duration in days)" if self.log_scale else "Duration (days)"

        if self.plot_type == "boxplot":
            n_cols = len(cohorts)
            n_rows = len(events)
            if n_rows == 0 or n_cols == 0:
                return go.Figure()

            fig = make_subplots(
                rows=n_rows,
                cols=n_cols,
                row_titles=events,
                column_titles=cohorts,
                shared_yaxes=True,
            )
            for ri, event in enumerate(events, start=1):
                for ci, cohort in enumerate(cohorts, start=1):
                    mask = (df["_event"] == event) & (df["_cohort"] == cohort)
                    vals = (
                        np.log10(df.loc[mask, "event_length_days"].clip(lower=0.1))
                        if self.log_scale
                        else df.loc[mask, "event_length_days"]
                    ).dropna()
                    hex_c = _COLOURS[(ci - 1) % len(_COLOURS)]
                    fig.add_trace(
                        go.Box(
                            x=vals,
                            name=cohort,
                            marker_color=hex_c,
                            showlegend=(ri == 1),
                        ),
                        row=ri,
                        col=ci,
                    )
            fig.update_layout(
                title=f"Event duration — {self.event_col}",
                xaxis_title=y_label,
                height=max(300, 200 * n_rows),
            )

        else:  # histogram
            fig = go.Figure()
            for i, cohort in enumerate(cohorts):
                mask = df["_cohort"] == cohort
                vals = (
                    np.log10(df.loc[mask, "event_length_days"].clip(lower=0.1))
                    if self.log_scale
                    else df.loc[mask, "event_length_days"]
                ).dropna()
                hex_c = _COLOURS[i % len(_COLOURS)]
                r, g, b = int(hex_c[1:3], 16), int(hex_c[3:5], 16), int(hex_c[5:7], 16)
                fig.add_trace(
                    go.Histogram(
                        x=vals,
                        name=cohort,
                        marker_color=f"rgba({r},{g},{b},0.6)",
                        marker_line_color=hex_c,
                        marker_line_width=1,
                        opacity=0.75,
                    )
                )
            fig.update_layout(
                barmode="overlay",
                title=f"Event duration — {self.event_col}",
                xaxis_title=y_label,
                yaxis_title="Count",
                legend_title="Cohort",
            )

        return fig

    def to_dict(self) -> dict[str, Any]:
        self._require_computed()
        return {
            "summary": self._summary.to_dict(orient="records"),
            "plot": self.plot().to_json(),
            "meta": {
                "event_col": self.event_col,
                "cohorts": self.cohorts,
                "plot_type": self.plot_type,
                "log_scale": self.log_scale,
            },
        }
