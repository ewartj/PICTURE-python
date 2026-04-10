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

from core.constants import COHORT_COL, DEFAULT_COHORT_LABEL, PROJECT_ID_COL


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
        cohort_col = cohort_col or (COHORT_COL if COHORT_COL in df_rdv.columns else None)
        self._result: Optional[pd.DataFrame] = None
        # Cached after free_input_data() is called.
        self._cohorts_cache: Optional[list[str]] = None
        self._cohort_sizes_cache: Optional[pd.Series] = None
        # Typed as Optional so free_input_data() can set them to None safely.
        self.df_rdv: Optional[pd.DataFrame] = None
        self.df_pde: Optional[pd.DataFrame] = None

        # Only copy when we need to add a missing cohort column; otherwise
        # store a reference to avoid doubling memory on every analytics call.
        if cohort_col is None or cohort_col not in df_rdv.columns:
            self.df_rdv = df_rdv.assign(**{COHORT_COL: DEFAULT_COHORT_LABEL})
            self.cohort_col: str = COHORT_COL
        else:
            self.df_rdv = df_rdv
            self.cohort_col = cohort_col

        if self.cohort_col not in df_pde.columns:
            self.df_pde = df_pde.assign(**{self.cohort_col: DEFAULT_COHORT_LABEL})
        else:
            self.df_pde = df_pde

    # ------------------------------------------------------------------
    # Interface — subclasses MUST implement these
    # ------------------------------------------------------------------

    @abstractmethod
    def compute(self) -> "AnalysisBase":
        """Run the analysis and store results in ``self._result``."""

    @abstractmethod
    def plot(self) -> go.Figure:
        """Return a Plotly Figure of the analysis results."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable representation of the results."""

    # ------------------------------------------------------------------
    # Shared helpers available to all subclasses
    # ------------------------------------------------------------------

    def _require_computed(self) -> pd.DataFrame:
        if self._result is None:
            raise RuntimeError(
                f"{self.__class__.__name__}.compute() must be called before accessing results."
            )
        return self._result

    @property
    def cohorts(self) -> list[str]:
        """Sorted list of cohort labels present in the data."""
        if self._cohorts_cache is not None:
            return self._cohorts_cache
        if self.df_rdv is None:
            raise RuntimeError("Input data has been freed; cohorts cache was not populated.")
        return sorted(self.df_rdv[self.cohort_col].dropna().unique().tolist())

    def cohort_sizes(self) -> pd.Series:
        """Number of unique patients per cohort (from df_rdv)."""
        if self._cohort_sizes_cache is not None:
            return self._cohort_sizes_cache
        if self.df_rdv is None:
            raise RuntimeError("Input data has been freed; cohort_sizes cache was not populated.")
        return self.df_rdv.groupby(self.cohort_col)[PROJECT_ID_COL].nunique().rename("n_patients")

    def free_input_data(self) -> "AnalysisBase":
        """Release input DataFrames after compute() to free memory.

        Caches cohort names and sizes first so ``cohorts`` and
        ``cohort_sizes()`` remain usable.  Call this after ``compute()``
        before storing the object in session state.

        Returns self for chaining::

            obj = MyAnalysis(...).compute().free_input_data()
        """
        if self._result is None:
            raise RuntimeError("Call compute() before free_input_data().")
        # Snapshot the values that depend on df_rdv / df_pde.
        self._cohorts_cache = self.cohorts
        self._cohort_sizes_cache = self.cohort_sizes()
        # Release the large input DataFrames.
        self.df_rdv = None
        self.df_pde = None
        return self

    def head(self, n: int = 20, by: Optional[str] = None) -> pd.DataFrame:
        df = self._require_computed()
        sort_col = self._count_col(by)
        return df.nlargest(n, sort_col)

    def tabulate(self) -> pd.DataFrame:
        return self._require_computed().copy()

    def _count_col(self, cohort: Optional[str] = None) -> str:
        df = self._require_computed()
        cohort_list = self.cohorts
        if not cohort_list:
            return df.columns[-1]
        target = cohort or cohort_list[0]
        candidates = [c for c in df.columns if c.startswith(target) and c.endswith(".count")]
        if not candidates:
            candidates = [c for c in df.columns if "count" in c]
        return candidates[0] if candidates else df.columns[-1]
