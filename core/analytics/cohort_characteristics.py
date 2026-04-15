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
from plotly.subplots import make_subplots

from core.analytics.base import AnalysisBase

# ---------------------------------------------------------------------------
# NHS ethnicity code → grouped category (mirrors R utils_add_rdv_hierarchies.R)
# ---------------------------------------------------------------------------

_ETHNICITY_PATTERNS: list[tuple[str, str]] = [
    (r"^[A-C]$", "White"),
    (r"^[D-G]$", "Mixed"),
    (r"^[HJKL]$", "Asian or Asian British"),
    (r"^[MNP]$", "Black or Black British"),
    (r"^[RS]$", "Other Ethnic Groups"),
    (r"^Z$", "Not Stated"),
]
_ETHNICITY_ORDER = [
    "White",
    "Mixed",
    "Asian or Asian British",
    "Black or Black British",
    "Other Ethnic Groups",
    "Not Stated",
    "Unknown",
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

        # Keep the enriched frame so plot() can build charts from raw data.
        self._enriched_rdv = df

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
            merged = merged.merge(frame, on=["grouping", "Characteristic"], how="outer")

        self._result = merged.reset_index(drop=True)
        return self

    def plot(self) -> go.Figure:
        """Return a multi-panel demographic visualisation.

        Panels (shown only when data is available):
          - Sex distribution (grouped bar chart)
          - Ethnic category breakdown (grouped bar chart)
          - Age at cohort entry (box plot)
        """
        raw = self._enriched_rdv  # enriched by compute() — has ethnicity_group and _age_at_entry
        cohort_col = self.cohort_col
        cohort_labels = sorted(raw[cohort_col].unique()) if cohort_col in raw.columns else ["All"]

        # ── Decide which panels we can draw ─────────────────────────────────
        has_sex = "sex_name" in raw.columns
        has_eth = "ethnicity_group" in raw.columns  # always True after compute()
        has_age = "_age_at_entry" in raw.columns and raw["_age_at_entry"].notna().any()

        n_panels = int(sum([has_sex, has_eth, has_age]))
        if n_panels == 0:
            return self._table_plot()

        fig = make_subplots(
            rows=n_panels,
            cols=1,
            subplot_titles=[
                t
                for t, show in [
                    ("Sex Distribution", has_sex),
                    ("Ethnic Category", has_eth),
                    ("Age at Cohort Entry (years)", has_age),
                ]
                if show
            ],
            vertical_spacing=0.12,
        )

        row = 1
        colours = [
            "#4f80e1",
            "#e07c54",
            "#5aba8c",
            "#c678a0",
            "#e0c354",
        ]

        # ── Sex ──────────────────────────────────────────────────────────────
        if has_sex:
            sex_order = ["Female", "Male", "Indeterminate / Unknown"]
            for idx, label in enumerate(cohort_labels):
                grp = raw[raw[cohort_col] == label]
                total = len(grp)
                counts = {s: (grp["sex_name"] == s).sum() for s in ["Female", "Male"]}
                counts["Indeterminate / Unknown"] = total - counts["Female"] - counts["Male"]
                pcts = [100 * counts[s] / total if total else 0 for s in sex_order]
                fig.add_trace(
                    go.Bar(
                        name=label,
                        x=sex_order,
                        y=pcts,
                        marker_color=colours[idx % len(colours)],
                        showlegend=(row == 1),
                        legendgroup=label,
                    ),
                    row=row,
                    col=1,
                )
            fig.update_yaxes(title_text="% of patients", row=row, col=1)
            row += 1

        # ── Ethnicity ────────────────────────────────────────────────────────
        if has_eth:
            for idx, label in enumerate(cohort_labels):
                grp = raw[raw[cohort_col] == label]
                eth = grp["ethnicity_group"].fillna("Unknown")
                counts = eth.value_counts()
                total = len(grp)
                x_vals = [e for e in _ETHNICITY_ORDER if e in counts or e in ("White", "Unknown")]
                y_vals = [100 * counts.get(e, 0) / total if total else 0 for e in x_vals]
                fig.add_trace(
                    go.Bar(
                        name=label,
                        x=x_vals,
                        y=y_vals,
                        marker_color=colours[idx % len(colours)],
                        showlegend=False,
                        legendgroup=label,
                    ),
                    row=row,
                    col=1,
                )
            fig.update_yaxes(title_text="% of patients", row=row, col=1)
            row += 1

        # ── Age ──────────────────────────────────────────────────────────────
        if has_age:
            for idx, label in enumerate(cohort_labels):
                grp = raw[raw[cohort_col] == label]
                ages = grp["_age_at_entry"].dropna().clip(lower=0)
                fig.add_trace(
                    go.Box(
                        name=label,
                        y=ages,
                        marker_color=colours[idx % len(colours)],
                        showlegend=False,
                        legendgroup=label,
                        boxmean="sd",
                    ),
                    row=row,
                    col=1,
                )
            fig.update_yaxes(title_text="Years", row=row, col=1)

        fig.update_layout(
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(t=60, r=20, b=20, l=60),
            height=320 * n_panels,
        )
        return fig

    def _table_plot(self) -> go.Figure:
        """Fallback: render the summary as a Plotly table."""
        display = self._display_df()
        header_vals = list(display.columns)
        cell_vals = [display[c].tolist() for c in display.columns]
        fig = go.Figure(
            go.Table(
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
            )
        )
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        return fig

    def to_dict(self) -> dict[str, Any]:
        df = self._require_computed()
        return {
            "meta": {
                "cohorts": self.cohorts,
                "n_rows": len(df),
            },
            # Include grouping so the frontend can render section headers.
            "table": df.to_dict(orient="records"),
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
    rows.append(
        {
            "grouping": "N",
            "Characteristic": "Periods",
            label: str(len(grp)),
        }
    )
    rows.append(
        {
            "grouping": "N",
            "Characteristic": "Patients",
            label: str(grp["project_id"].nunique()),
        }
    )

    # ── Sex ───────────────────────────────────────────────────────────────
    if "sex_name" in grp.columns:
        total = len(grp)
        n_female = (grp["sex_name"] == "Female").sum()
        n_male = (grp["sex_name"] == "Male").sum()
        n_other = total - n_female - n_male
        for name, n in [
            ("Female", n_female),
            ("Male", n_male),
            ("Indeterminate / Unknown", n_other),
        ]:
            rows.append(
                {
                    "grouping": "Sex",
                    "Characteristic": name,
                    label: _fmt_pct(100 * n / total if total else 0),
                }
            )

    # ── Ethnicity ─────────────────────────────────────────────────────────
    if "ethnicity_group" in grp.columns:
        eth_counts = grp["ethnicity_group"].fillna("Unknown").value_counts()
        total = eth_counts.sum()
        for eth in _ETHNICITY_ORDER:
            if eth in eth_counts or eth in ("White", "Unknown"):
                pct = 100 * eth_counts.get(eth, 0) / total if total else 0
                rows.append(
                    {
                        "grouping": "Ethnic Category",
                        "Characteristic": eth,
                        label: _fmt_pct(pct),
                    }
                )

    # ── Age at cohort entry ────────────────────────────────────────────────
    ages = grp["_age_at_entry"].dropna()
    if len(ages) > 0:
        for name, val in [
            ("Minimum", ages.clip(lower=0).min()),
            ("25th Percentile", ages.quantile(0.25)),
            ("Median", ages.median()),
            ("75th Percentile", ages.quantile(0.75)),
            ("Maximum", ages.max()),
        ]:
            rows.append(
                {
                    "grouping": "Age at Cohort Entry (years)",
                    "Characteristic": name,
                    label: _fmt_yrs(val),
                }
            )

    return pd.DataFrame(rows)
