"""
Base class for all analytics modules.

Every analytics module (frequency, distribution, correlation, etc.) inherits
from AnalysisBase and must implement:
  - compute()  → stores results internally
  - plot()     → returns a plotly Figure
  - to_dict()  → returns a JSON-serialisable dict (consumed by the API layer)

This clean interface means:
  - The API layer calls compute() then to_dict() and returns JSON to React.
  - The Streamlit UI calls compute() then plot() / tabulate().
  - Switching UI layers requires no changes to this code.

Replaces: the S3 class system in R (gen_frequency_analysis, etc.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go


class AnalysisBase(ABC):
    """Abstract base class for PICTURE analytics modules."""

    #: Human-readable name shown in the UI
    label: str = ""

    def __init__(
        self,
        df_rdv: pd.DataFrame,
        df_pde: pd.DataFrame,
        cohort_col: Optional[str] = None,
    ) -> None:
        """
        Args:
            df_rdv:     The RDV DataFrame to analyse (already filtered to the
                        selected cohort by ``apply_cohorts_to_rdv``).
            df_pde:     Patient demographics RDV (used for cohort sizes).
            cohort_col: Name of the column carrying the cohort label.
                        Defaults to ``"cohort"`` if present, otherwise ``None``
                        (single-cohort mode labelled "All").
        """
        self.df_rdv = df_rdv.copy()
        self.df_pde = df_pde.copy()
        self.cohort_col = cohort_col or ("cohort" if "cohort" in df_rdv.columns else None)
        self._result: Optional[pd.DataFrame] = None

        # Add a default "All" cohort column if none is present
        if self.cohort_col is None:
            self.df_rdv["cohort"] = "All"
            self.cohort_col = "cohort"

        # Always ensure df_pde has the cohort column (it may be a raw RDV
        # without cohort labels when running in single-cohort mode)
        if self.cohort_col not in self.df_pde.columns:
            self.df_pde[self.cohort_col] = "All"

    # ------------------------------------------------------------------
    # Interface — subclasses MUST implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def compute(self) -> "AnalysisBase":
        """Run the analysis and store results in ``self._result``.

        Returns:
            self  (for method chaining: ``analysis.compute().plot()``)
        """

    @abstractmethod
    def plot(self) -> go.Figure:
        """Return a Plotly Figure of the analysis results.

        Raises:
            RuntimeError: If called before ``compute()``.
        """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the results.

        This is what the FastAPI layer returns to the React frontend.
        Must include at minimum:
            - ``"table"``: list of row dicts
            - ``"plot"``:  plotly figure as JSON (fig.to_json())
            - ``"meta"``:  dict of metadata (cohorts, row counts, etc.)

        Raises:
            RuntimeError: If called before ``compute()``.
        """

    # ------------------------------------------------------------------
    # Shared helpers available to all subclasses
    # ------------------------------------------------------------------

    def _require_computed(self) -> pd.DataFrame:
        if self._result is None:
            raise RuntimeError(
                f"{self.__class__.__name__}.compute() must be called before "
                "accessing results."
            )
        return self._result

    @property
    def cohorts(self) -> list[str]:
        """Sorted list of cohort labels present in the data."""
        return sorted(self.df_rdv[self.cohort_col].dropna().unique().tolist())

    def cohort_sizes(self) -> pd.Series:
        """Number of unique patients per cohort (from df_rdv)."""
        return (
            self.df_rdv.groupby(self.cohort_col)["project_id"]
            .nunique()
            .rename("n_patients")
        )

    def head(self, n: int = 20, by: Optional[str] = None) -> pd.DataFrame:
        """Return the top-n rows ordered by count descending.

        Args:
            n:   Number of rows to return.
            by:  Cohort label to sort by.  Uses first cohort if omitted.
        """
        df = self._require_computed()
        sort_col = self._count_col(by)
        return df.nlargest(n, sort_col)

    def tabulate(self) -> pd.DataFrame:
        """Return the result table as a plain DataFrame."""
        return self._require_computed().copy()

    def _count_col(self, cohort: Optional[str] = None) -> str:
        """Return the count column name for *cohort* (or the first cohort)."""
        df = self._require_computed()
        target = cohort or self.cohorts[0]
        candidates = [c for c in df.columns if c.startswith(target) and c.endswith(".count")]
        if not candidates:
            candidates = [c for c in df.columns if "count" in c]
        return candidates[0] if candidates else df.columns[-1]
