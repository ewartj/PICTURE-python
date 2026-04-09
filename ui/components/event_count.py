"""UI page for EventCount analysis."""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from core.analytics.event_count import EventCount
from core.cohort.models import ResolvedCohort
from core.config.app_config import AnalysisMethod
from ui.components import evict_stale_cache, get_cohorted_rdv


def render(
    method: AnalysisMethod,
    resolved_cohorts: list[ResolvedCohort],
    rdvs: dict[str, pd.DataFrame],
) -> None:
    rdv_name = re.sub(r"^df_", "", method.rdv_params.get("df_rdv", "pde"))
    event_col = method.static_params.get("event_col")

    if rdv_name not in rdvs:
        st.warning(f"RDV '{rdv_name}' not loaded.")
        return
    if not event_col:
        st.warning("No `event_col` specified in method params.")
        return

    # Cache compute() result — re-runs only when data or cohorts change.
    cohort_key = ":".join(f"{c.label}={c.n_patients}" for c in resolved_cohorts)
    cache_key = f"_ec:{rdv_name}:{event_col}:{cohort_key}"
    evict_stale_cache(f"_ec:{rdv_name}:{event_col}:", cache_key)

    if cache_key not in st.session_state:
        df_rdv = get_cohorted_rdv(
            rdv_name, rdvs[rdv_name], resolved_cohorts, cohort_key
        )
        df_pde = rdvs.get("pde", pd.DataFrame())
        try:
            obj = (
                EventCount(df_rdv, df_pde, event_col=event_col)
                .compute()
                .free_input_data()
            )
        except Exception as exc:
            st.error(f"EventCount failed: {exc}")
            return
        st.session_state[cache_key] = obj

    obj: EventCount = st.session_state[cache_key]

    st.plotly_chart(obj.plot(), use_container_width=True)
    st.dataframe(obj._result, use_container_width=True, hide_index=True)
