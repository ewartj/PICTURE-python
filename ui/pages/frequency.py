"""
Frequency Analysis page — Streamlit UI.

This page is intentionally thin:
  - It reads analysis params from the YAML-provided AnalysisMethod
  - Resolves cohorts (passed in from app.py — already computed)
  - Applies cohorts to the target RDV
  - Calls FrequencyAnalysis and displays results

No business logic lives here. When React replaces this, it will call
POST /analytics/frequency instead of importing FrequencyAnalysis directly.
"""

from __future__ import annotations

import re

import streamlit as st

from core.analytics.frequency import FrequencyAnalysis
from core.cohort.filters import apply_cohorts_to_rdv
from core.cohort.models import ResolvedCohort
from core.config.app_config import AnalysisMethod


def render(
    method: AnalysisMethod,
    resolved_cohorts: list[ResolvedCohort],
    rdvs: dict,
) -> None:
    """Render the frequency analysis for one YAML method entry.

    Args:
        method:            The ``gen_frequency_analysis`` method entry from the
                           app YAML, carrying ``df_rdv`` and ``event_col``
                           params.
        resolved_cohorts:  Cohorts already resolved against the loaded data.
                           Each cohort becomes a separate series in the chart.
        rdvs:              All loaded RDV DataFrames, keyed by RDV code.
    """
    # ------------------------------------------------------------------
    # Resolve which RDV and column to use from the YAML params.
    # The YAML carries e.g. { df_rdv: "df_dia", event_col: "diag_name" }.
    # ------------------------------------------------------------------
    rdv_param = method.rdv_params.get("df_rdv")
    if not rdv_param:
        st.error("This method's YAML params do not include a `df_rdv` key.")
        return

    # Strip the leading "df_" to get the RDV code used as a dict key
    rdv_name = re.sub(r"^df_", "", rdv_param)

    if rdv_name not in rdvs:
        st.error(
            f"RDV `{rdv_name}` is referenced in the app YAML but was not "
            f"found in the data directory. Available: {list(rdvs.keys())}"
        )
        return

    # event_col comes from static params; fall back to a selectbox if absent
    event_col: str | None = method.static_params.get("event_col")

    df_rdv = rdvs[rdv_name]

    if not event_col:
        categorical_cols = [
            c for c in df_rdv.columns
            if df_rdv[c].dtype == object or str(df_rdv[c].dtype) == "category"
        ]
        if not categorical_cols:
            st.error(f"No categorical columns found in RDV `{rdv_name}`.")
            return
        event_col = st.selectbox(
            "Column to analyse",
            categorical_cols,
            help="The app YAML did not specify an `event_col` — select one manually.",
        )

    # ------------------------------------------------------------------
    # Info row — show what this analysis is running
    # ------------------------------------------------------------------
    col_info, col_type = st.columns([4, 1])
    with col_info:
        cohort_labels = [c.label for c in resolved_cohorts] or ["All"]
        st.caption(
            f"RDV: **{rdv_name}** · Column: **{event_col}** · "
            f"Cohorts: {', '.join(f'**{l}**' for l in cohort_labels)}"
        )
    with col_type:
        value_type = st.radio("Show as", ["frequency", "count"], horizontal=True, key=f"vtype_{method.fn}_{rdv_name}")

    # ------------------------------------------------------------------
    # Apply cohorts — produces a DataFrame with a `cohort` column
    # ------------------------------------------------------------------
    if resolved_cohorts:
        df_analysis = apply_cohorts_to_rdv(df_rdv, resolved_cohorts)
    else:
        # No cohorts defined — treat all patients as a single "All" cohort
        df_analysis = df_rdv.copy()
        df_analysis["cohort"] = "All"
        if "cohort_id" not in df_analysis.columns:
            df_analysis["cohort_id"] = df_analysis["project_id"].astype(str)

    # ------------------------------------------------------------------
    # Run analysis
    # ------------------------------------------------------------------
    if "pde" not in rdvs:
        st.warning("Demographics RDV (`pde`) not found — patient counts may be inaccurate.")

    with st.spinner("Computing..."):
        try:
            analysis = FrequencyAnalysis(
                df_rdv=df_analysis,
                df_pde=rdvs.get("pde", df_analysis),
                event_col=event_col,
            )
            analysis.compute()
        except Exception as exc:
            st.error(f"Analysis failed: {exc}")
            return

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    tab_chart, tab_table = st.tabs(["Chart", "Table"])

    with tab_chart:
        st.plotly_chart(analysis.plot(value=value_type), width='stretch')

    with tab_table:
        st.dataframe(analysis.tabulate(), width='stretch')

    with st.expander("API-equivalent JSON (what React will receive)"):
        import json
        result = analysis.to_dict()
        st.json({"meta": result["meta"], "table_preview": result["table"][:5]})
