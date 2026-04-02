"""
Frequency analysis.

Calculates event frequencies (counts and proportions) per cohort for any
categorical column in an RDV.

Replaces: driveanalytics R/gen_frequency_analysis.R
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from core.analytics.base import AnalysisBase

logger = logging.getLogger(__name__)


class FrequencyAnalysis(AnalysisBase):
    """Frequency analysis for a selected category column.

    Usage::

        analysis = FrequencyAnalysis(df_rdv, df_pde, event_col="diag_name")
        analysis.compute()
        fig = analysis.plot()
        data = analysis.to_dict()   # JSON-safe — consumed by API / React
    """

    label = "Frequency Analysis"

    def __init__(
        self,
        df_rdv: pd.DataFrame,
        df_pde: pd.DataFrame,
        event_col: str,
        cohort_col: Optional[str] = None,
    ) -> None:
        """
        Args:
            df_rdv:     RDV DataFrame (already cohort-filtered and labelled).
            df_pde:     Demographics DataFrame.
            event_col:  Column name to compute frequencies over.
            cohort_col: Column carrying cohort labels (default: "cohort").
        """
        super().__init__(df_rdv, df_pde, cohort_col)
        self.event_col = event_col

    # ------------------------------------------------------------------
    # Core computation
    # ------------------------------------------------------------------

    def compute(self) -> "FrequencyAnalysis":
        logger.info("FrequencyAnalysis.compute — event_col=%s", self.event_col)

        df = self.df_rdv.copy()

        # Drop rows without an event value
        df = df.dropna(subset=[self.event_col])

        # Deduplicate: one row per (cohort_id, event) — mirrors R's distinct()
        df["_event"] = df[self.event_col].astype(str)
        df["_cohort"] = df[self.cohort_col].astype(str)
        df = df[["cohort_id", "_event", "_cohort"]].drop_duplicates()

        # Cohort sizes (denominator)
        sizes = self.cohort_sizes()

        # Count per (cohort, event)
        counts = (
            df.groupby(["_cohort", "_event"])
            .size()
            .reset_index(name="count")
        )
        counts = counts.merge(
            sizes.reset_index().rename(columns={self.cohort_col: "_cohort"}),
            on="_cohort",
            how="left",
        )
        counts["frequency"] = counts["count"] / counts["n_patients"]

        # Pivot wide: one column pair per cohort  ({cohort}.count, {cohort}.frequency)
        wide = counts.pivot_table(
            index="_event",
            columns="_cohort",
            values=["count", "frequency"],
            fill_value=0,
        )
        # Flatten MultiIndex columns to "{cohort}.{metric}"
        wide.columns = [f"{cohort}.{metric}" for metric, cohort in wide.columns]
        wide = wide.reset_index().rename(columns={"_event": "event"})

        self._result = wide
        self._cohort_sizes = sizes
        logger.info("FrequencyAnalysis.compute done — %d events", len(wide))
        return self

    # ------------------------------------------------------------------
    # Plot
    # ------------------------------------------------------------------

    def plot(self, value: str = "frequency") -> go.Figure:
        """Bar chart of frequencies or counts per cohort.

        Args:
            value: ``"frequency"`` (default) or ``"count"``.

        Returns:
            Plotly Figure.
        """
        df = self._require_computed()

        col_suffix = f".{value}"
        value_cols = [c for c in df.columns if c.endswith(col_suffix)]
        cohort_labels = [c.removesuffix(col_suffix) for c in value_cols]

        plot_df = df[["event"] + value_cols].copy()
        plot_df["event"] = plot_df["event"].str[:60]  # truncate long labels

        # Melt to long form for plotly
        melted = plot_df.melt(id_vars="event", value_vars=value_cols,
                              var_name="cohort", value_name=value)
        melted["cohort"] = melted["cohort"].str.removesuffix(col_suffix)

        scale = 100 if value == "frequency" else 1
        melted[value] = melted[value] * scale
        ylabel = f"{'Frequency (%)' if value == 'frequency' else 'Count'} in Cohort"

        fig = px.bar(
            melted,
            x="event",
            y=value,
            color="cohort",
            barmode="group",
            labels={"event": "", "cohort": "Cohort", value: ylabel},
            title=f"{self.label} — {self.event_col}",
        )
        fig.update_layout(xaxis_tickangle=-70)
        return fig

    # ------------------------------------------------------------------
    # Serialisation (API / React layer)
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        df = self._require_computed()
        return {
            "table": df.to_dict(orient="records"),
            "plot": self.plot().to_json(),
            "meta": {
                "event_col": self.event_col,
                "cohorts": self.cohorts,
                "cohort_sizes": self._cohort_sizes.to_dict(),
                "n_events": len(df),
            },
        }
