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

from core.analytics._colours import cohort_colour
from core.analytics.base import AnalysisBase

PlotType = Literal["boxplot", "histogram"]


class EventTimeAnalysis(AnalysisBase):
    """Duration analysis for each event category.

    Computes ``event_length_days = end_datetime - start_datetime`` for every
    row, then summarises and plots the distribution per event and cohort.

    Args:
        df_rdv:      RDV DataFrame (already cohort-labelled, must have
                     ``start_datetime`` and optionally ``end_datetime``).
        df_pde:      Patient demographics RDV.
        event_col:   Column carrying the event category (e.g. ``"diag_name"``).
        cohort_col:  Column carrying cohort labels (default ``"cohort"``).
        plot_type:   ``"boxplot"`` (default) or ``"histogram"``.
        log_scale:   If True, apply log10 to durations before plotting.
        top_n:       Maximum number of events to show in the plot (ranked by
                     record count across all cohorts). Default 20.
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
        top_n: int = 10,
    ) -> None:
        super().__init__(df_rdv=df_rdv, df_pde=df_pde, cohort_col=cohort_col)
        self.event_col = event_col
        self.plot_type = plot_type
        self.log_scale = log_scale
        self.top_n = top_n

    def compute(self) -> "EventTimeAnalysis":
        df_rdv = self._require_rdv()
        cols = list(
            dict.fromkeys(
                ["project_id", self.event_col, self.cohort_col, "start_datetime"]
                + (["end_datetime"] if "end_datetime" in df_rdv.columns else [])
            )
        )
        df = df_rdv[cols].dropna(subset=[self.event_col]).copy()

        df["start_dt"] = pd.to_datetime(df["start_datetime"]).dt.normalize()
        df["end_dt"] = (
            pd.to_datetime(df["end_datetime"]).dt.normalize()
            if "end_datetime" in df.columns
            else df["start_dt"]
        )
        df["event_length_days"] = (df["end_dt"] - df["start_dt"]).dt.days.clip(lower=0)
        df["_event"] = df[self.event_col].astype(str)
        df["_cohort"] = df[self.cohort_col].astype(str)

        valid = df[["_event", "_cohort", "event_length_days"]].dropna(subset=["event_length_days"])

        # Pre-aggregate to quantile stats — avoids storing all raw rows.
        # Plotly can draw boxplots directly from summary statistics.
        stats = (
            valid.groupby(["_event", "_cohort"])["event_length_days"]
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
            if col in stats.columns:
                stats[col] = stats[col].round(1)

        self._summary = stats
        self._result = stats

        # For the histogram we still need raw counts per (event, cohort, bucket).
        # Bin into 50 buckets once here and store the histogram data compactly.
        self._hist: dict[tuple[str, str], tuple[np.ndarray, np.ndarray]] = {}
        for (event, cohort), grp in valid.groupby(["_event", "_cohort"]):
            vals = grp["event_length_days"].values
            if self.log_scale:
                vals = np.log10(np.clip(vals, 0.1, None))
            counts, edges = np.histogram(vals, bins=50)
            self._hist[(str(event), str(cohort))] = (counts, edges)

        return self

    def plot(self) -> go.Figure:
        """Return boxplot or histogram for the top-N most common events."""
        self._require_computed()

        # Rank events by total record count across all cohorts; take top_n.
        event_counts = self._summary.groupby("Event")["N"].sum().nlargest(self.top_n)
        top_events = event_counts.index.tolist()
        summary = self._summary[self._summary["Event"].isin(top_events)]
        cohorts = sorted(summary["Cohort"].unique())

        y_label = "log₁₀(Duration in days)" if self.log_scale else "Duration (days)"

        if self.plot_type == "boxplot":
            return self._boxplot(summary, top_events, cohorts, y_label)
        return self._histogram(top_events, cohorts, y_label)

    def _boxplot(
        self,
        summary: pd.DataFrame,
        events: list[str],
        cohorts: list[str],
        y_label: str,
    ) -> go.Figure:
        """Grouped boxplot driven by pre-aggregated summary statistics.

        Uses Plotly's lowerfence/q1/median/q3/upperfence interface so no
        raw data needs to be passed — one trace per cohort, all events on
        the same x-axis.
        """
        fig = go.Figure()
        for i, cohort in enumerate(cohorts):
            sub = summary[summary["Cohort"] == cohort].set_index("Event").reindex(events)
            hex_c = cohort_colour(i)

            def _apply_log(col: str) -> list:
                vals = sub[col].fillna(0).values
                if self.log_scale:
                    vals = np.log10(np.clip(vals, 0.1, None))
                return vals.tolist()

            fig.add_trace(
                go.Box(
                    name=cohort,
                    x=events,
                    lowerfence=_apply_log("Min"),
                    q1=_apply_log("Q1"),
                    median=_apply_log("Median"),
                    q3=_apply_log("Q3"),
                    upperfence=_apply_log("Max"),
                    marker_color=hex_c,
                    boxpoints=False,
                )
            )

        fig.update_layout(
            boxmode="group",
            title=f"Event duration — {self.event_col} (top {len(events)})",
            xaxis_title=self.event_col,
            yaxis_title=y_label,
            xaxis_tickangle=-70,
            height=500,
            legend_title="Cohort",
        )
        return fig

    def _histogram(
        self,
        events: list[str],
        cohorts: list[str],
        y_label: str,
    ) -> go.Figure:
        """Histogram using pre-binned data stored in self._hist."""
        fig = go.Figure()
        for i, cohort in enumerate(cohorts):
            # Sum pre-binned counts across selected events for this cohort.
            combined_counts: Optional[np.ndarray] = None
            combined_edges: Optional[np.ndarray] = None
            for event in events:
                key = (event, cohort)
                if key not in self._hist:
                    continue
                counts, edges = self._hist[key]
                if combined_counts is None:
                    combined_counts = counts.copy()
                    combined_edges = edges
                else:
                    combined_counts = combined_counts + counts

            if combined_counts is None or combined_edges is None:
                continue

            hex_c = cohort_colour(i)
            r, g, b = int(hex_c[1:3], 16), int(hex_c[3:5], 16), int(hex_c[5:7], 16)
            centres = (combined_edges[:-1] + combined_edges[1:]) / 2
            fig.add_trace(
                go.Bar(
                    x=centres.tolist(),
                    y=combined_counts.tolist(),
                    name=cohort,
                    marker_color=f"rgba({r},{g},{b},0.6)",
                    marker_line_color=hex_c,
                    marker_line_width=1,
                    opacity=0.75,
                )
            )

        fig.update_layout(
            barmode="overlay",
            title=f"Event duration — {self.event_col} (top {len(events)})",
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
                "top_n": self.top_n,
            },
        }
