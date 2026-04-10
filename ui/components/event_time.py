"""UI page for EventTimeAnalysis."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.analytics.event_time import EventTimeAnalysis
from core.cohort.models import ResolvedCohort
from core.config.app_config import AnalysisMethod
from ui.components import evict_stale_cache, get_cohorted_rdv, handle_analysis_errors


def render(
    method: AnalysisMethod, resolved_cohorts: list[ResolvedCohort], rdvs: dict[str, pd.DataFrame]
) -> None:
    rdv_name = method.rdv_name
    event_col = method.event_col

    if rdv_name not in rdvs:
        st.warning(f"RDV '{rdv_name}' not loaded.")
        return
    if not event_col:
        st.warning("No `event_col` specified in method params.")
        return

    # These widgets only affect plot() — not compute() — so they must come
    # before the cache check so their current values are used when plotting.
    col1, col2, col3 = st.columns(3)
    with col1:
        plot_type = st.selectbox("Plot type", ["boxplot", "histogram"], key=f"et_type_{method.fn}")
    with col2:
        log_scale = st.checkbox("Log scale", value=False, key=f"et_log_{method.fn}")
    with col3:
        top_n = st.slider("Top N events", 5, 30, 20, key=f"et_topn_{method.fn}")

    cohort_key = ":".join(f"{c.label}={c.n_patients}" for c in resolved_cohorts)
    cache_key = f"_et:{rdv_name}:{event_col}:{cohort_key}"
    evict_stale_cache(f"_et:{rdv_name}:{event_col}:", cache_key)

    if cache_key not in st.session_state:
        df_rdv = get_cohorted_rdv(rdv_name, rdvs[rdv_name], resolved_cohorts, cohort_key)
        df_pde = rdvs.get("pde", pd.DataFrame())
        with handle_analysis_errors("Event time analysis"):
            obj = EventTimeAnalysis(df_rdv, df_pde, event_col=event_col).compute().free_input_data()
            st.session_state[cache_key] = obj

    obj: EventTimeAnalysis = st.session_state[cache_key]
    # Apply display-only settings before plotting.
    obj.plot_type = plot_type
    obj.log_scale = log_scale
    obj.top_n = top_n

    st.plotly_chart(obj.plot(), use_container_width=True)
    st.dataframe(obj._summary, use_container_width=True, hide_index=True)
