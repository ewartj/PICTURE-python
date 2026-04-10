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

import streamlit as st

from core.analytics.frequency import FrequencyAnalysis
from core.cohort.models import ResolvedCohort
from core.config.app_config import AnalysisMethod
from ui.components import evict_stale_cache, get_cohorted_rdv, handle_analysis_errors


def render(
    method: AnalysisMethod,
    resolved_cohorts: list[ResolvedCohort],
    rdvs: dict,
) -> None:
    rdv_name = method.rdv_name
    event_col = method.event_col

    if rdv_name not in rdvs:
        st.error(
            f"RDV `{rdv_name}` is referenced in the app YAML but was not "
            f"found in the data directory. Available: {list(rdvs.keys())}"
        )
        return

    df_rdv = rdvs[rdv_name]

    if not event_col:
        categorical_cols = [
            c
            for c in df_rdv.columns
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
    # Info row
    # ------------------------------------------------------------------
    col_info, col_type = st.columns([4, 1])
    with col_info:
        cohort_labels = [c.label for c in resolved_cohorts] or ["All"]
        st.caption(
            f"RDV: **{rdv_name}** · Column: **{event_col}** · "
            f"Cohorts: {', '.join(f'**{lbl}**' for lbl in cohort_labels)}"
        )
    with col_type:
        value_type = st.radio(
            "Show as", ["frequency", "count"], horizontal=True, key=f"vtype_{method.fn}_{rdv_name}"
        )

    # ------------------------------------------------------------------
    # Cache compute() — re-runs only when data or cohorts change.
    # ------------------------------------------------------------------
    cohort_key = ":".join(f"{c.label}={c.n_patients}" for c in resolved_cohorts)
    cache_key = f"_freq:{rdv_name}:{event_col}:{cohort_key}"
    evict_stale_cache(f"_freq:{rdv_name}:{event_col}:", cache_key)

    if cache_key not in st.session_state:
        if "pde" not in rdvs:
            st.warning("Demographics RDV (`pde`) not found — patient counts may be inaccurate.")

        df_analysis = get_cohorted_rdv(rdv_name, df_rdv, resolved_cohorts, cohort_key)

        with handle_analysis_errors("Frequency analysis"):
            with st.spinner("Computing..."):
                analysis = (
                    FrequencyAnalysis(
                        df_rdv=df_analysis,
                        df_pde=rdvs.get("pde", df_analysis),
                        event_col=event_col,
                    )
                    .compute()
                    .free_input_data()
                )
            st.session_state[cache_key] = analysis

    analysis: FrequencyAnalysis = st.session_state[cache_key]

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    tab_chart, tab_table = st.tabs(["Chart", "Table"])

    with tab_chart:
        st.plotly_chart(analysis.plot(value=value_type), width="stretch")

    with tab_table:
        st.dataframe(analysis.tabulate(), width="stretch")

    with st.expander("API-equivalent JSON (what React will receive)"):
        result = analysis.to_dict()
        st.json({"meta": result["meta"], "table_preview": result["table"][:5]})
