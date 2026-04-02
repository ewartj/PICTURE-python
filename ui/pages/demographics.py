"""
Demographics (tpl_pde_all) page — Streamlit UI.

Renders the standard 5-sub-tab demographics template:
  1. Overview     — cohort characteristics summary table
  2. Patient List — searchable patient-level table
  3. Sex          — 100%-stacked bar by sex_name
  4. Ethnicity    — 100%-stacked bar by ethnicity group
  5. Age at Entry — boxplot of age at cohort entry

Replaces: driveanalytics R/tpl_pde_all-shiny.R

No business logic lives here — all computation is delegated to
core/analytics/cohort_characteristics.py and
core/analytics/categorical_ratios.py.
"""

from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.analytics.categorical_ratios import CategoricalRatios
from core.analytics.cohort_characteristics import (
    CohortCharacteristics,
    _add_ethnicity_group,
    _age_years,
)
from core.cohort.filters import apply_cohorts_to_rdv
from core.cohort.models import ResolvedCohort
from core.config.app_config import AnalysisMethod


def render(
    method: AnalysisMethod,
    resolved_cohorts: list[ResolvedCohort],
    rdvs: dict,
) -> None:
    """Render the full demographics template for one YAML method entry.

    Args:
        method:           The ``tpl_pde_all`` method entry from the app YAML.
        resolved_cohorts: Cohorts already resolved against the loaded data.
        rdvs:             All loaded RDV DataFrames.
    """
    # ------------------------------------------------------------------
    # Resolve which pde RDV to use (default: "pde")
    # ------------------------------------------------------------------
    pde_param = method.rdv_params.get("df_pde", "df_pde")
    pde_name = re.sub(r"^df_", "", pde_param)

    if pde_name not in rdvs:
        st.error(
            f"Demographics RDV `{pde_name}` not found. "
            f"Available RDVs: {list(rdvs.keys())}"
        )
        return

    df_pde_raw = rdvs[pde_name]

    # ------------------------------------------------------------------
    # Apply cohorts to pde
    # ------------------------------------------------------------------
    if resolved_cohorts:
        df_pde = apply_cohorts_to_rdv(df_pde_raw, resolved_cohorts)
    else:
        df_pde = df_pde_raw.copy()
        df_pde["cohort"] = "All"
        if "cohort_id" not in df_pde.columns:
            df_pde["cohort_id"] = df_pde["project_id"].astype(str)

    if df_pde.empty:
        st.warning("No patients matched the cohort criteria in the demographics RDV.")
        return

    # ------------------------------------------------------------------
    # 5 sub-tabs
    # ------------------------------------------------------------------
    tab_overview, tab_patients, tab_sex, tab_ethnicity, tab_age = st.tabs([
        "Overview", "Patient List", "Sex", "Ethnicity", "Age at Entry",
    ])

    # ── 1. Overview ───────────────────────────────────────────────────
    with tab_overview:
        with st.spinner("Computing cohort characteristics…"):
            try:
                chars = CohortCharacteristics(df_rdv=df_pde, df_pde=df_pde)
                chars.compute()
            except Exception as exc:
                st.error(f"Failed to compute cohort characteristics: {exc}")
                return

        display = chars._display_df()

        # Bold the section-header rows (rows where cohort columns are empty)
        cohort_cols = [c for c in display.columns if c != "Characteristic"]

        # Render as a Plotly table so we can style section headers
        header_mask = display[cohort_cols].apply(
            lambda col: col == "", axis=0
        ).all(axis=1) if cohort_cols else pd.Series(False, index=display.index)

        row_colours = []
        for is_header in header_mask:
            row_colours.append("#2c3e50" if is_header else None)

        font_colours = ["white" if h else "black" for h in header_mask]

        fig = go.Figure(go.Table(
            header=dict(
                values=[f"<b>{c}</b>" for c in display.columns],
                fill_color="#2c3e50",
                font=dict(color="white", size=12),
                align="left",
            ),
            cells=dict(
                values=[display[c].tolist() for c in display.columns],
                fill_color=[
                    ["#2c3e50" if h else ("#ecf0f1" if i % 2 == 0 else "white")
                     for i, h in enumerate(header_mask)]
                    for _ in display.columns
                ],
                font=dict(
                    color=[font_colours for _ in display.columns],
                    size=11,
                ),
                align="left",
            ),
        ))
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), height=600)
        st.plotly_chart(fig, width='stretch')

    # ── 2. Patient List ───────────────────────────────────────────────
    with tab_patients:
        show_cols = [c for c in [
            "project_id", "birth_date", "death_date",
            "entry_date", "exit_date", "cohort",
        ] if c in df_pde.columns]

        # Deduplicate to one row per patient per cohort period
        df_list = df_pde[show_cols].drop_duplicates()

        # Prettify column names
        df_list.columns = [
            c.replace("_", " ").title() for c in df_list.columns
        ]

        st.caption(f"{len(df_list):,} rows · {df_list['Project Id'].nunique() if 'Project Id' in df_list.columns else '?'} unique patients")
        st.dataframe(df_list, width='stretch')

    # ── 3. Sex ────────────────────────────────────────────────────────
    with tab_sex:
        if "sex_name" not in df_pde.columns:
            st.info("`sex_name` column not found in the demographics RDV.")
        else:
            with st.spinner("Computing sex breakdown…"):
                try:
                    sex_analysis = CategoricalRatios(
                        df_rdv=df_pde,
                        df_pde=df_pde,
                        col="sex_name",
                    )
                    sex_analysis.compute()
                    st.plotly_chart(sex_analysis.plot(), width='stretch')
                    if sex_analysis._test_result:
                        st.caption(sex_analysis._test_result)
                    with st.expander("Table"):
                        st.dataframe(sex_analysis.tabulate(), width='stretch')
                except Exception as exc:
                    st.error(f"Sex analysis failed: {exc}")

    # ── 4. Ethnicity ──────────────────────────────────────────────────
    with tab_ethnicity:
        df_pde_eth = _add_ethnicity_group(df_pde)
        if "ethnicity_group" not in df_pde_eth.columns:
            st.info("No ethnicity column found in the demographics RDV.")
        else:
            with st.spinner("Computing ethnicity breakdown…"):
                try:
                    eth_analysis = CategoricalRatios(
                        df_rdv=df_pde_eth,
                        df_pde=df_pde_eth,
                        col="ethnicity_group",
                    )
                    eth_analysis.compute()
                    st.plotly_chart(eth_analysis.plot(), width='stretch')
                    if eth_analysis._test_result:
                        st.caption(eth_analysis._test_result)
                    with st.expander("Table"):
                        st.dataframe(eth_analysis.tabulate(), width='stretch')
                except Exception as exc:
                    st.error(f"Ethnicity analysis failed: {exc}")

    # ── 5. Age at Cohort Entry ────────────────────────────────────────
    with tab_age:
        entry_col = next(
            (c for c in df_pde.columns if c in ("entry_date", "cohort_entry_date")),
            None,
        )
        if not entry_col or "birth_date" not in df_pde.columns:
            st.info(
                "Age at cohort entry requires `birth_date` and `entry_date` "
                "columns in the demographics RDV."
            )
        else:
            with st.spinner("Computing age distribution…"):
                try:
                    df_age = df_pde.copy()
                    df_age["age_at_entry"] = _age_years(
                        df_age[entry_col], df_age["birth_date"]
                    ).clip(lower=0)

                    fig = go.Figure()
                    for cohort_label in sorted(df_age["cohort"].unique()):
                        ages = df_age[df_age["cohort"] == cohort_label]["age_at_entry"].dropna()
                        fig.add_trace(go.Box(
                            y=ages,
                            name=str(cohort_label),
                            boxpoints="outliers",
                        ))

                    fig.update_layout(
                        title="Age at Cohort Entry",
                        yaxis_title="Age (years)",
                        xaxis_title="Cohort",
                    )
                    st.plotly_chart(fig, width='stretch')
                except Exception as exc:
                    st.error(f"Age distribution failed: {exc}")
