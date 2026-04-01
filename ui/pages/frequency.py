"""
Frequency Analysis page — Streamlit UI.

This page is intentionally thin:
  - It collects user inputs
  - Calls core analytics directly (via the same functions the API uses)
  - Displays the results

No business logic lives here. When React replaces this, it will call
POST /analytics/frequency instead of importing FrequencyAnalysis directly.
"""

from __future__ import annotations

import streamlit as st

from core.cohort.filters import apply_cohorts_to_rdv
from core.data.loader import load_all_rdvs
from core.analytics.frequency import FrequencyAnalysis


def render(data_dir: str) -> None:
    st.header("Frequency Analysis")
    st.markdown(
        "Counts how often each value of a chosen column appears across cohorts. "
        "Equivalent to `gen_frequency_analysis()` in driveanalytics."
    )

    # ------------------------------------------------------------------
    # Load data
    # ------------------------------------------------------------------
    with st.spinner("Loading RDVs..."):
        try:
            rdvs = load_all_rdvs(data_dir)
        except Exception as exc:
            st.error(f"Failed to load data: {exc}")
            return

    available_rdvs = list(rdvs.keys())
    if not available_rdvs:
        st.warning("No RDV files found in the specified data directory.")
        return

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    col1, col2, col3 = st.columns(3)

    with col1:
        rdv_name = st.selectbox("RDV", available_rdvs, index=0)

    df_selected = rdvs[rdv_name]
    categorical_cols = [
        c for c in df_selected.columns
        if df_selected[c].dtype == object or str(df_selected[c].dtype) == "category"
    ]

    with col2:
        event_col = st.selectbox("Column to analyse", categorical_cols)

    with col3:
        value_type = st.radio("Show as", ["frequency", "count"], horizontal=True)

    # ------------------------------------------------------------------
    # Run analysis (calls core directly — same path the API uses)
    # ------------------------------------------------------------------
    if st.button("Run Analysis", type="primary"):
        with st.spinner("Computing..."):
            df_rdv = df_selected.copy()
            df_rdv["cohort"] = "All"
            if "cohort_id" not in df_rdv.columns:
                df_rdv["cohort_id"] = df_rdv["project_id"].astype(str)

            try:
                analysis = FrequencyAnalysis(
                    df_rdv=df_rdv,
                    df_pde=rdvs.get("pde", df_rdv),
                    event_col=event_col,
                )
                analysis.compute()
            except Exception as exc:
                st.error(f"Analysis failed: {exc}")
                return

        # Results
        tab_chart, tab_table = st.tabs(["Chart", "Table"])

        with tab_chart:
            st.plotly_chart(analysis.plot(value=value_type), use_container_width=True)

        with tab_table:
            st.dataframe(analysis.tabulate(), use_container_width=True)

        with st.expander("API-equivalent JSON (what React will receive)"):
            import json
            result = analysis.to_dict()
            # Show meta and table only — plot JSON is too large to display usefully
            st.json({"meta": result["meta"], "table_preview": result["table"][:5]})
