"""
Distribution Plots page — Streamlit UI.

Renders a density plot + boxplot for a numeric column, split by cohort.
Mirrors the R ``gen_distribution_plots_server()``:
  - Optional filter on a categorical column (e.g. ward_code = PICU)
  - Optional log transform
  - Summary table: median + 95% bootstrap CI per cohort
  - Kruskal-Wallis test result

No business logic lives here — all computation is in
core/analytics/distribution.py.
"""

from __future__ import annotations

import re

import streamlit as st

from core.analytics.distribution import DistributionPlots
from core.cohort.filters import apply_cohorts_to_rdv
from core.cohort.models import ResolvedCohort
from core.config.app_config import AnalysisMethod


def render(
    method: AnalysisMethod,
    resolved_cohorts: list[ResolvedCohort],
    rdvs: dict,
) -> None:
    """Render the distribution analysis for one YAML method entry.

    Args:
        method:           The ``gen_distribution_plots`` method from the YAML.
        resolved_cohorts: Pre-resolved cohorts.
        rdvs:             All loaded RDV DataFrames.
    """
    # ------------------------------------------------------------------
    # Resolve RDV from YAML params
    # ------------------------------------------------------------------
    rdv_param = method.rdv_params.get("df_rdv")
    if not rdv_param:
        st.error("This method's YAML params do not include a `df_rdv` key.")
        return

    rdv_name = re.sub(r"^df_", "", rdv_param)
    if rdv_name not in rdvs:
        st.error(
            f"RDV `{rdv_name}` not found in the data directory. "
            f"Available: {list(rdvs.keys())}"
        )
        return

    static = method.static_params

    col: str | None = static.get("col")
    if not col:
        # Fall back to a selectbox for numeric columns
        df_raw = rdvs[rdv_name]
        num_cols = [c for c in df_raw.columns if pd.api.types.is_numeric_dtype(df_raw[c])]
        if not num_cols:
            st.error(f"No numeric columns found in RDV `{rdv_name}`.")
            return
        col = st.selectbox("Column to analyse", num_cols, key=f"dist_col_{rdv_name}")

    calc_length: bool = bool(static.get("calc_length", False))
    calc_diff: bool = bool(static.get("calc_diff", False))
    filter_col: str | None = static.get("filter_col")
    filter_val_default: str | None = static.get("filter_val")
    description: str | None = static.get("description")
    side_by_side: bool = bool(static.get("side_by_side", True))

    # ------------------------------------------------------------------
    # Apply cohorts to the RDV
    # ------------------------------------------------------------------
    if resolved_cohorts:
        df_rdv = apply_cohorts_to_rdv(rdvs[rdv_name], resolved_cohorts)
    else:
        df_rdv = rdvs[rdv_name].copy()
        df_rdv["cohort"] = "All"
        if "cohort_id" not in df_rdv.columns:
            df_rdv["cohort_id"] = df_rdv["project_id"].astype(str)

    if df_rdv.empty:
        st.warning("No data matched the cohort criteria.")
        return

    # ------------------------------------------------------------------
    # Controls
    # ------------------------------------------------------------------
    ctrl_cols = st.columns(3)

    # Filter selector — if filter_col is specified, show a selectbox
    filter_val: str | None = filter_val_default
    if filter_col and filter_col in df_rdv.columns:
        options = sorted(df_rdv[filter_col].dropna().astype(str).unique())
        default_idx = options.index(str(filter_val_default)) \
            if filter_val_default and str(filter_val_default) in options else 0
        with ctrl_cols[0]:
            filter_val = st.selectbox(
                filter_col.replace("_", " ").title(),
                options,
                index=default_idx,
                key=f"dist_filter_{rdv_name}_{filter_col}",
            )

    with ctrl_cols[1]:
        transform = st.selectbox(
            "Transform",
            ["none", "log"],
            format_func=lambda x: "No transformation" if x == "none" else "Log",
            key=f"dist_transform_{rdv_name}_{col}",
        )

    with ctrl_cols[2]:
        layout = st.radio(
            "Layout",
            ["side by side", "stacked"],
            index=0 if side_by_side else 1,
            horizontal=True,
            key=f"dist_layout_{rdv_name}_{col}",
        )

    # ------------------------------------------------------------------
    # Run analysis
    # ------------------------------------------------------------------
    with st.spinner("Computing distribution…"):
        try:
            analysis = DistributionPlots(
                df_rdv=df_rdv,
                df_pde=rdvs.get("pde", df_rdv),
                col=col,
                filter_col=filter_col,
                filter_val=filter_val,
                calc_length=calc_length,
                calc_diff=calc_diff,
                transform=transform,
                description=description,
            )
            analysis.compute()
        except Exception as exc:
            st.error(f"Distribution analysis failed: {exc}")
            return

    if analysis._result is None or analysis._result.empty:
        st.warning("No data to display after filtering.")
        return

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    if analysis._test_result:
        st.caption(analysis._test_result)

    tab_chart, tab_table = st.tabs(["Chart", "Summary Table"])

    with tab_chart:
        st.plotly_chart(
            analysis.plot(side_by_side=(layout == "side by side")),
            width='stretch',
        )

    with tab_table:
        st.dataframe(analysis.tabulate(), width='stretch')


# Inline import needed here because this module is loaded lazily
import pandas as pd
