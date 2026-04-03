"""
Cohort editor page.

Lets users inspect, modify, add, and remove cohort definitions, then
re-resolve them against the loaded RDVs.  Results are written back into
``st.session_state`` so all analysis tabs pick up the changes.

Session state keys managed here
────────────────────────────────
  editable_cohorts:{app_id}:{data_dir}
      list of cohort dicts (mutable copies of CohortDefinition configs)
"""

from __future__ import annotations

import copy
from typing import Optional

import pandas as pd
import streamlit as st

from core.cohort.filters import resolve_cohort
from core.cohort.formatting import describe_step
from core.cohort.models import (
    CohortDefinition,
    CohortFilterStep,
    ResolvedCohort,
)
from core.rdv.lookups import get_variable_filter_type, get_variable_input_type

# ── Constants ──────────────────────────────────────────────────────────────────

_QUERY_TYPES = [
    "str_matches",
    "str_contains",
    "str_starts",
    "date_between",
    "numeric_between",
    "age_between",
]

_INCLUSIONS = [
    "ever",
    "never",
    "fully_concurrent",
    "after_first",
    "on_first",
]

_INCLUSION_HELP = {
    "ever":             "Patient had this at any point in their cohort window",
    "never":            "Exclude patients who had this",
    "fully_concurrent": "Narrow window to overlap with this event",
    "after_first":      "Start cohort window from first occurrence of this event",
    "on_first":         "Pin cohort window to first occurrence of this event",
}

_QUERY_HELP = {
    "str_matches":      "Exact match (one of the values)",
    "str_contains":     "Case-insensitive substring match",
    "str_starts":       "Value starts with one of the strings",
    "date_between":     "Date falls in range [from, to]",
    "numeric_between":  "Number falls in range [lo, hi]",
    "age_between":      "Patient age (years) at entry falls in range",
}

# ── Public entry point ──────────────────────────────────────────────────────────

def render(
    app_id: int,
    initial_cohorts: list[CohortDefinition],
    rdvs: dict[str, pd.DataFrame],
    data_dir: str,
) -> None:
    """Render the cohort editor tab.

    Writes updated resolved cohorts back to
    ``st.session_state[f"cohorts:{app_id}:{data_dir}"]`` when the user
    clicks **Apply & Re-resolve**.

    Args:
        app_id:          Identifier of the currently open AppConfig.
        initial_cohorts: Cohort definitions from the app YAML (used to
                         seed editable state on first load).
        rdvs:            Loaded RDV DataFrames (for column value lookup).
        data_dir:        Current data directory (part of cache key).
    """
    state_key = f"editable_cohorts:{app_id}:{data_dir}"

    # Seed editable state from the YAML definitions on first visit
    if state_key not in st.session_state:
        st.session_state[state_key] = _cohorts_to_dicts(initial_cohorts)

    cohort_dicts: list[dict] = st.session_state[state_key]

    # ── Top action bar ──────────────────────────────────────────────────────
    col_add, col_apply, col_reset, _ = st.columns([1.2, 1.5, 1, 5])

    with col_add:
        if st.button("+ Add cohort", key=f"add_cohort_{app_id}"):
            cohort_dicts.append(_empty_cohort_dict())
            st.rerun()

    with col_apply:
        apply_clicked = st.button(
            "Apply & Re-resolve",
            key=f"apply_{app_id}",
            type="primary",
        )

    with col_reset:
        if st.button("Reset to YAML", key=f"reset_{app_id}"):
            st.session_state[state_key] = _cohorts_to_dicts(initial_cohorts)
            st.rerun()

    st.markdown("---")

    # ── Per-cohort editors ──────────────────────────────────────────────────
    to_remove: list[int] = []

    for ci, cohort in enumerate(cohort_dicts):
        _render_cohort_editor(ci, cohort, rdvs, app_id, to_remove)

    # Apply removals (reverse order to keep indices valid)
    for idx in reversed(to_remove):
        cohort_dicts.pop(idx)
    if to_remove:
        st.rerun()

    # ── Apply & Re-resolve ──────────────────────────────────────────────────
    if apply_clicked:
        _apply_cohorts(app_id, data_dir, cohort_dicts, rdvs)


# ── Per-cohort editor ───────────────────────────────────────────────────────────

def _render_cohort_editor(
    ci: int,
    cohort: dict,
    rdvs: dict[str, pd.DataFrame],
    app_id: int,
    to_remove: list[int],
) -> None:
    label_col, remove_col = st.columns([8, 1])

    with label_col:
        cohort["label"] = st.text_input(
            "Cohort label",
            value=cohort["label"],
            key=f"label_{app_id}_{ci}",
            label_visibility="collapsed",
            placeholder="Cohort name…",
        )

    with remove_col:
        if st.button("Remove", key=f"rm_cohort_{app_id}_{ci}"):
            to_remove.append(ci)

    steps: list[dict] = cohort["steps"]
    steps_to_remove: list[int] = []

    for si, step in enumerate(steps):
        _render_step_editor(ci, si, step, rdvs, app_id, steps_to_remove)

    for idx in reversed(steps_to_remove):
        steps.pop(idx)

    if st.button("+ Add filter step", key=f"add_step_{app_id}_{ci}"):
        steps.append(_empty_step_dict())
        st.rerun()

    st.markdown("---")


def _render_step_editor(
    ci: int,
    si: int,
    step: dict,
    rdvs: dict[str, pd.DataFrame],
    app_id: int,
    steps_to_remove: list[int],
) -> None:
    key = f"{app_id}_{ci}_{si}"

    with st.container(border=True):
        top_cols = st.columns([2, 2, 3, 1])

        # RDV selector
        rdv_names = sorted(rdvs.keys())
        current_rdv = step.get("rdv") or (rdv_names[0] if rdv_names else "")
        with top_cols[0]:
            step["rdv"] = st.selectbox(
                "RDV",
                options=rdv_names,
                index=rdv_names.index(current_rdv) if current_rdv in rdv_names else 0,
                key=f"rdv_{key}",
            )

        # Column selector — derived from chosen RDV
        rdv_df = rdvs.get(step["rdv"], pd.DataFrame())
        col_names = sorted(rdv_df.columns.tolist()) if not rdv_df.empty else []
        current_col = step.get("column") or (col_names[0] if col_names else "")
        with top_cols[1]:
            step["column"] = st.selectbox(
                "Column",
                options=col_names,
                index=col_names.index(current_col) if current_col in col_names else 0,
                key=f"col_{key}",
            )

        # Query type
        current_qt = step.get("query_type", "str_matches")
        with top_cols[2]:
            step["query_type"] = st.selectbox(
                "Query type",
                options=_QUERY_TYPES,
                index=_QUERY_TYPES.index(current_qt) if current_qt in _QUERY_TYPES else 0,
                format_func=lambda q: f"{q}  —  {_QUERY_HELP[q]}",
                key=f"qt_{key}",
            )

        # Remove step button
        with top_cols[3]:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("✕", key=f"rm_step_{key}", help="Remove this filter step"):
                steps_to_remove.append(si)

        # Auto-suggest query type from lookup when column changes
        suggested_qt = get_variable_filter_type(step.get("rdv", ""), step.get("column", ""))
        if suggested_qt and step.get("_last_column") != step.get("column"):
            step["query_type"] = suggested_qt
        step["_last_column"] = step.get("column")

        # Value inputs (depend on query type)
        bottom_cols = st.columns([4, 3])

        with bottom_cols[0]:
            step["val"] = _render_val_input(step, rdv_df, key)

        with bottom_cols[1]:
            current_inc = step.get("inclusion", "ever")
            step["inclusion"] = st.selectbox(
                "Inclusion",
                options=_INCLUSIONS,
                index=_INCLUSIONS.index(current_inc) if current_inc in _INCLUSIONS else 0,
                format_func=lambda i: f"{i}  —  {_INCLUSION_HELP[i]}",
                key=f"inc_{key}",
            )

        # Human-readable preview of what this step means
        preview_step = CohortFilterStep(
            type="filter",
            rdv=step.get("rdv"),
            column=step.get("column"),
            val=step.get("val") or [],
            inclusion=step.get("inclusion", "ever"),
            query_type=step.get("query_type", "str_matches"),
        )
        st.caption(f"↳ {describe_step(preview_step)}")

        # Window offsets (advanced, collapsed by default)
        window = step.get("window") or [0, 0]
        with st.expander("Window offsets (days)", expanded=(window != [0, 0])):
            w_cols = st.columns(2)
            with w_cols[0]:
                window[0] = st.number_input(
                    "Start offset (days)",
                    value=int(window[0]),
                    step=1,
                    key=f"w0_{key}",
                    help="Shift the cohort window start by this many days",
                )
            with w_cols[1]:
                window[1] = st.number_input(
                    "End offset (days)",
                    value=int(window[1]),
                    step=1,
                    key=f"w1_{key}",
                    help="Shift the cohort window end by this many days",
                )
            step["window"] = window


def _render_val_input(step: dict, rdv_df: pd.DataFrame, key: str) -> list:
    """Render value input widget appropriate for the query type."""
    qt = step.get("query_type", "str_matches")
    col = step.get("column", "")
    current_val = step.get("val") or []

    if qt in ("str_matches", "str_contains", "str_starts"):
        # Offer unique column values as multiselect options
        if col and col in rdv_df.columns:
            unique_vals = sorted(
                rdv_df[col].dropna().astype(str).unique().tolist()
            )
            # Guard against enormous option lists
            if len(unique_vals) > 500:
                unique_vals = unique_vals[:500]
        else:
            unique_vals = []

        # Include any values already selected (they may not be in the RDV subset)
        all_options = sorted(set(unique_vals) | set(str(v) for v in current_val))
        default = [v for v in current_val if v in all_options]

        selected = st.multiselect(
            "Values",
            options=all_options,
            default=default,
            key=f"val_{key}",
            placeholder="Select or type values…",
        )
        return selected

    elif qt in ("date_between",):
        # Two date inputs
        lo = pd.to_datetime(current_val[0]).date() if len(current_val) > 0 else None
        hi = pd.to_datetime(current_val[1]).date() if len(current_val) > 1 else None
        d_cols = st.columns(2)
        with d_cols[0]:
            lo = st.date_input("From", value=lo, key=f"val_lo_{key}")
        with d_cols[1]:
            hi = st.date_input("To", value=hi, key=f"val_hi_{key}")
        return [str(lo), str(hi)]

    else:
        # numeric_between / age_between — two number inputs
        lo_val = float(current_val[0]) if len(current_val) > 0 else 0.0
        hi_val = float(current_val[1]) if len(current_val) > 1 else 100.0
        n_cols = st.columns(2)
        label_lo = "Min age (years)" if qt == "age_between" else "Min"
        label_hi = "Max age (years)" if qt == "age_between" else "Max"
        with n_cols[0]:
            lo_val = st.number_input(label_lo, value=lo_val, step=1.0, key=f"val_lo_{key}")
        with n_cols[1]:
            hi_val = st.number_input(label_hi, value=hi_val, step=1.0, key=f"val_hi_{key}")
        return [lo_val, hi_val]


# ── Apply logic ─────────────────────────────────────────────────────────────────

def _apply_cohorts(
    app_id: int,
    data_dir: str,
    cohort_dicts: list[dict],
    rdvs: dict[str, pd.DataFrame],
) -> None:
    """Re-resolve cohorts from the current editor state."""
    definitions = _dicts_to_cohorts(cohort_dicts)
    resolved: list[ResolvedCohort] = []
    errors: list[str] = []

    progress = st.progress(0, text="Resolving cohorts…")
    for i, defn in enumerate(definitions):
        progress.progress((i + 1) / max(len(definitions), 1), text=f"Resolving '{defn.label}'…")
        try:
            resolved.append(resolve_cohort(defn, rdvs))
        except Exception as exc:
            errors.append(f"'{defn.label}': {exc}")
    progress.empty()

    if errors:
        for msg in errors:
            st.error(f"Could not resolve cohort {msg}")

    cohorts_key = f"cohorts:{app_id}:{data_dir}"
    st.session_state[cohorts_key] = resolved
    st.success(
        f"Resolved {len(resolved)} cohort{'s' if len(resolved) != 1 else ''}. "
        "Switch to an analysis tab to see the updated results."
    )
    st.rerun()


# ── Dict ↔ CohortDefinition conversion ─────────────────────────────────────────

def _cohorts_to_dicts(cohorts: list[CohortDefinition]) -> list[dict]:
    result = []
    for c in cohorts:
        steps = []
        for s in c.config:
            if s.type == "base":
                continue  # base step is implicit — don't show in UI
            steps.append({
                "rdv":        s.rdv or "pde",
                "column":     s.column or "",
                "query_type": s.query_type,
                "val":        list(s.val) if s.val else [],
                "inclusion":  s.inclusion,
                "window":     list(s.window) if s.window else [0, 0],
            })
        result.append({"label": c.label, "steps": steps})
    return result


def _dicts_to_cohorts(cohort_dicts: list[dict]) -> list[CohortDefinition]:
    definitions = []
    for cd in cohort_dicts:
        label = cd.get("label", "Unnamed").strip() or "Unnamed"
        steps_raw = cd.get("steps", [])
        steps: list[CohortFilterStep] = [CohortFilterStep(type="base")]
        for i, s in enumerate(steps_raw):
            val = s.get("val") or []
            if not isinstance(val, list):
                val = [val]
            val = [str(v) for v in val if v != ""]
            window = s.get("window") or [0, 0]
            steps.append(CohortFilterStep(
                type="filter" if i == 0 else "and",
                rdv=s.get("rdv") or "pde",
                column=s.get("column") or "",
                val=val,
                inclusion=s.get("inclusion", "ever"),
                query_type=s.get("query_type", "str_matches"),
                window=window if window != [0, 0] else None,
            ))
        definitions.append(CohortDefinition(label=label, config=steps))
    return definitions


def _empty_cohort_dict() -> dict:
    return {"label": "", "steps": [_empty_step_dict()]}


def _empty_step_dict() -> dict:
    return {
        "rdv":        "pde",
        "column":     "",
        "query_type": "str_matches",
        "val":        [],
        "inclusion":  "ever",
        "window":     [0, 0],
    }
