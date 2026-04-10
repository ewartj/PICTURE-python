"""
Patient selection UI component.

Mirrors picture.platform R/ui_select_patient-shiny.R.

Renders a searchable patient selector in the Streamlit sidebar (or main
area).  When a patient is selected, cohort definitions that contain the
placeholder ``SELECT_PROJECT_ID`` have it substituted with the chosen ID,
enabling single-patient analysis.

Usage::

    from ui.components.patient_selector import render

    updated_cohorts = render(rdvs=rdvs, initial_cohorts=app.initial_cohorts)
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from core.cohort.models import CohortDefinition, CohortFilterStep
from core.report.formatting import report_patient_info_table

_PLACEHOLDER = "SELECT_PROJECT_ID"


def render(
    rdvs: dict[str, pd.DataFrame],
    initial_cohorts: list[CohortDefinition],
    key_prefix: str = "patient_selector",
) -> list[CohortDefinition]:
    """Render the patient selector and return (possibly updated) cohort definitions.

    If a patient is selected and any cohort step contains the placeholder
    ``SELECT_PROJECT_ID`` as a filter value, those values are replaced with
    the selected patient's ID.

    Args:
        rdvs:            Loaded RDV DataFrames.  ``pde`` is used for the
                         patient list and demographics table.
        initial_cohorts: Cohort definitions from the app YAML.
        key_prefix:      Streamlit widget key prefix (allows multiple instances).

    Returns:
        Updated cohort definitions (deep copy with placeholder substituted,
        or originals unchanged if no patient is selected).
    """
    pde = rdvs.get("pde", pd.DataFrame())

    st.subheader("Patient Selection")

    if pde.empty or "project_id" not in pde.columns:
        st.warning("Demographics RDV (pde) not loaded — patient selection unavailable.")
        return initial_cohorts

    patient_ids = sorted(pde["project_id"].dropna().astype(str).unique().tolist())

    selected = st.selectbox(
        "Search for a patient",
        options=[""] + patient_ids,
        format_func=lambda x: "— select a patient —" if x == "" else x,
        key=f"{key_prefix}_select",
    )

    if not selected:
        return initial_cohorts

    # ── Patient details table ───────────────────────────────────────────────
    st.subheader("Patient details")
    info_df = report_patient_info_table(selected, pde)
    st.dataframe(
        info_df,
        use_container_width=True,
        hide_index=True,
    )

    # ── Substitute placeholder in cohort definitions ────────────────────────
    return _substitute_patient_id(initial_cohorts, selected)


def _substitute_patient_id(
    cohorts: list[CohortDefinition],
    project_id: str,
) -> list[CohortDefinition]:
    """Deep-copy cohort definitions, replacing SELECT_PROJECT_ID with *project_id*."""
    result: list[CohortDefinition] = []
    for cohort in cohorts:
        new_steps: list[CohortFilterStep] = []
        for step in cohort.config:
            new_val = [
                project_id if str(v) == _PLACEHOLDER else v for v in (step.val or [])
            ]
            new_steps.append(
                CohortFilterStep(
                    type=step.type,
                    rdv=step.rdv,
                    column=step.column,
                    val=new_val,
                    inclusion=step.inclusion,
                    query_type=step.query_type,
                    window=step.window,
                )
            )
        result.append(CohortDefinition(label=cohort.label, config=new_steps))
    return result
