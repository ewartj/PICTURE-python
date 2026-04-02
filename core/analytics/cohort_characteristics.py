"""Cohort demographic characteristics summary.

Produces a wide-format summary table with one column per cohort:

    Characteristic          | Female      | Male
    ────────────────────────┼─────────────┼────────────
    N
      Periods               | 1 234       | 987
      Patients              | 456         | 321
    Sex
      Female                | 95.20 %     | 5.10 %
      Male                  | 4.80 %      | 94.90 %
      Indeterminate/Unknown | 0.00 %      | 0.00 %
    Ethnic Category
      White                 | 60.20 %     | 58.30 %
      …
    Age at Cohort Entry (years)
      Minimum               | 0.50 yrs    | 0.30 yrs
      25th Percentile       | 3.20 yrs    | …
      Median                | 8.10 yrs    | …
      75th Percentile       | 14.50 yrs   | …
      Maximum               | 17.90 yrs   | …

Replaces: driveanalytics R/pde_cohort_characteristics.R
          driveanalytics R/utils_add_rdv_hierarchies.R  (ethnicity grouping)
"""

from __future__ import annotations

import re
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go

from core.analytics.base import AnalysisBase


# ---------------------------------------------------------------------------
# NHS ethnicity code → grouped category (mirrors R utils_add_rdv_hierarchies.R)
# ---------------------------------------------------------------------------

_ETHNICITY_PATTERNS: list[tuple[str, str]] = [
    (r"^[A-C]$",    "White"),
    (r"^[D-G]$",    "Mixed"),
    (r"^[HJKL]$",   "Asian or Asian British"),
    (r"^[MNP]$",    "Black or Black British"),
    (r"^[RS]$",     "Other Ethnic Groups"),
    (r"^Z$",        "Not Stated"),
]
_ETHNICITY_ORDER = [
    "White", "Mixed", "Asian or Asian British",
    "Black or Black British", "Other Ethnic Groups", "Not Stated", "Unknown",
]


def _add_ethnicity_group(df: pd.DataFrame) -> pd.DataFrame:
    """Add an ``ethnicity_group`` column derived from NHS ``ethnicity_nat_code``.

    Falls back to ``ethnicity_name`` if ``ethnicity_nat_code`` is absent.
    Rows that match no pattern are labelled ``"Unknown"``.
    """
    df = df.copy()

    if "ethnicity_nat_code" in df.columns:
        code = df["ethnicity_nat_code"].fillna("").astype(str).str.strip().str.upper()
        groups = pd.Series("Unknown", index=df.index)
        for pattern, label in _ETHNICITY_PATTERNS:
            groups = groups.where(~code.str.match(pattern), label)
        df["ethnicity_group"] = groups
    elif "ethnicity_name" in df.columns:
        df["ethnicity_group"] = df["ethnicity_name"].fillna("Unknown")
    else:
        df["ethnicity_group"] = "Unknown"

    return df


def _age_years(event_date: pd.Series, birth_date: pd.Series) -> pd.Series:
    """Return age in fractional years between two date-like Series."""
    delta = pd.to_datetime(event_date) - pd.to_datetime(birth_date)
    return delta.dt.total_seconds() / (365.25 * 24 * 3600)


# ---------------------------------------------------------------------------
# Analytics class
# ---------------------------------------------------------------------------

class CohortCharacteristics(AnalysisBase):
    """Demographic summary table for one or more cohorts.

    Args:
        df_rdv: The pde DataFrame *after* cohort labels have been applied
                (i.e. after ``apply_cohorts_to_rdv``).  Must have columns:
                ``project_id``, ``cohort``, ``birth_date``,
                and optionally ``sex_name``, ``ethnicity_nat_code``,
                ``ethnicity_name``, ``entry_date``.
        df_pde: Same pde DataFrame (passed through to ``AnalysisBase``).
    """

    label = "Cohort Characteristics"

    def compute(self) -> "CohortCharacteristics":
        df = _add_ethnicity_group(self.df_rdv)

        # Age at cohort entry — use entry_date if present, else skip
        entry_col = next(
            (c for c in df.columns if c in ("entry_date", "cohort_entry_date")),
            None,
        )
        if entry_col and "birth_date" in df.columns:
            df["_age_at_entry"] = _age_years(df[entry_col], df["birth_date"])
        else:
            df["_age_at_entry"] = float("nan")

        cohort_frames: list[pd.DataFrame] = []
        for cohort_label, grp in df.groupby(self.cohort_col, sort=True):
            section = _summarise_cohort(grp, cohort_label)
            cohort_frames.append(section)

        if not cohort_frames:
            self._result = pd.DataFrame(columns=["grouping", "Characteristic"])
            return self

        # Merge all cohorts into wide format
        merged = cohort_frames[0]
        for frame in cohort_frames[1:]:
            merged = merged.merge(
                frame, on=["grouping", "Characteristic"], how="outer"
            )

        self._result = merged.reset_index(drop=True)
        return self

    def plot(self) -> go.Figure:
        """Return a Plotly table — this analysis is table-only."""
        df = self._require_computed()

        # Build header + cell values for Plotly table
        display = self._display_df()
        header_vals = list(display.columns)
        cell_vals = [display[c].tolist() for c in display.columns]

        fig = go.Figure(go.Table(
            header=dict(
                values=[f"<b>{h}</b>" for h in header_vals],
                fill_color="#2c3e50",
                font=dict(color="white", size=12),
                align="left",
            ),
            cells=dict(
                values=cell_vals,
                fill_color=[
                    ["#ecf0f1" if i % 2 == 0 else "white" for i in range(len(display))]
                    for _ in display.columns
                ],
                align="left",
                font=dict(size=11),
            ),
        ))
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        return fig

    def to_dict(self) -> dict[str, Any]:
        df = self._require_computed()
        display = self._display_df()
        return {
            "meta": {
                "cohorts": self.cohorts,
                "n_rows": len(df),
            },
            "table": display.to_dict(orient="records"),
            "plot": self.plot().to_json(),
        }

    def _display_df(self) -> pd.DataFrame:
        """Return the result with the internal ``grouping`` column removed."""
        df = self._require_computed().copy()
        return df.drop(columns=["grouping"], errors="ignore")


# ---------------------------------------------------------------------------
# Per-cohort summary helper
# ---------------------------------------------------------------------------

def _fmt_pct(v: float) -> str:
    return f"{v:.2f} %"


def _fmt_yrs(v: float) -> str:
    return f"{v:.2f} yrs"


def _summarise_cohort(grp: pd.DataFrame, label: str) -> pd.DataFrame:
    """Build a single-cohort summary DataFrame."""
    rows: list[dict] = []

    # ── N ─────────────────────────────────────────────────────────────────
    rows.append({
        "grouping": "N",
        "Characteristic": "Periods",
        label: str(len(grp)),
    })
    rows.append({
        "grouping": "N",
        "Characteristic": "Patients",
        label: str(grp["project_id"].nunique()),
    })

    # ── Sex ───────────────────────────────────────────────────────────────
    if "sex_name" in grp.columns:
        total = len(grp)
        n_female = (grp["sex_name"] == "Female").sum()
        n_male   = (grp["sex_name"] == "Male").sum()
        n_other  = total - n_female - n_male
        for name, n in [
            ("Female", n_female),
            ("Male", n_male),
            ("Indeterminate / Unknown", n_other),
        ]:
            rows.append({
                "grouping": "Sex",
                "Characteristic": name,
                label: _fmt_pct(100 * n / total if total else 0),
            })

    # ── Ethnicity ─────────────────────────────────────────────────────────
    if "ethnicity_group" in grp.columns:
        eth_counts = grp["ethnicity_group"].fillna("Unknown").value_counts()
        total = eth_counts.sum()
        for eth in _ETHNICITY_ORDER:
            if eth in eth_counts or eth in ("White", "Unknown"):
                pct = 100 * eth_counts.get(eth, 0) / total if total else 0
                rows.append({
                    "grouping": "Ethnic Category",
                    "Characteristic": eth,
                    label: _fmt_pct(pct),
                })

    # ── Age at cohort entry ────────────────────────────────────────────────
    ages = grp["_age_at_entry"].dropna()
    if len(ages) > 0:
        for name, val in [
            ("Minimum",         ages.clip(lower=0).min()),
            ("25th Percentile", ages.quantile(0.25)),
            ("Median",          ages.median()),
            ("75th Percentile", ages.quantile(0.75)),
            ("Maximum",         ages.max()),
        ]:
            rows.append({
                "grouping": "Age at Cohort Entry (years)",
                "Characteristic": name,
                label: _fmt_yrs(val),
            })

    return pd.DataFrame(rows)
