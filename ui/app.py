"""
PICTURE Streamlit application — temporary UI layer.

This will be replaced by a React frontend once the API layer is stable.
All business logic lives in core/ and is accessed via api/ service functions.
This file should contain ONLY layout and display code.

Run with:
    streamlit run ui/app.py

Two-screen flow (mirrors the React frontend pattern):

  1. HOME  — user enters data directory; app discovers all YAML app
             definitions and displays a card per app (title, description,
             creator).  User clicks "Open" on one.

  2. ANALYSIS — cohorts from the selected app YAML are resolved, then
                analysis tabs are rendered (one tab per ``analysis`` entry
                in the YAML, sub-tabbed per method).

Session state keys
──────────────────
  selected_app_id          int | None   — which app the user opened
  apps:{data_dir}          list[AppConfig]
  rdvs:{data_dir}          dict[str, DataFrame]
  cohorts:{app_id}:{data_dir}  list[ResolvedCohort]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

from core.config.app_config import AppConfig, load_app_configs
from core.config.platform_config import _resolve_app_yaml, load_platform_config
from core.cohort.filters import resolve_cohort
from core.cohort.models import ResolvedCohort
from core.data.loader import load_all_rdvs

_platform = load_platform_config()

st.set_page_config(
    page_title="PICTURE Analytics",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Analytics method → page render function registry ──────────────────────────
# Add entries here as new analytics modules are implemented.
_FN_REGISTRY: dict[str, str] = {
    "gen_frequency_analysis": "frequency",
    "tpl_pde_all":            "demographics",
    "gen_distribution_plots": "distribution",
    # "gen_timeseries_analysis": "timeseries",
    # "gen_event_time_analysis": "event_time",
    # "gen_event_count":         "event_count",
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def _load_apps(app_dir: str) -> list[AppConfig]:
    key = f"apps:{app_dir}"
    if key not in st.session_state:
        paths = _resolve_app_yaml("*", Path(app_dir))
        st.session_state[key] = load_app_configs(paths) if paths else []
    return st.session_state[key]


def _load_rdvs(data_dir: str) -> dict:
    key = f"rdvs:{data_dir}"
    if key not in st.session_state:
        with st.spinner("Loading RDVs…"):
            st.session_state[key] = load_all_rdvs(data_dir)
    return st.session_state[key]


def _resolve_cohorts(app: AppConfig, data_dir: str, rdvs: dict) -> list[ResolvedCohort]:
    key = f"cohorts:{app.id}:{data_dir}"
    if key not in st.session_state:
        resolved: list[ResolvedCohort] = []
        if app.initial_cohorts:
            with st.spinner("Resolving cohorts…"):
                for defn in app.initial_cohorts:
                    try:
                        resolved.append(resolve_cohort(defn, rdvs))
                    except Exception as exc:
                        st.warning(f"Could not resolve cohort '{defn.label}': {exc}")
        st.session_state[key] = resolved
    return st.session_state[key]


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("PICTURE")
    st.markdown("---")

    _default_app_dir = str(_platform.app_dir) if _platform.app_dir else ""
    app_dir = st.text_input(
        "App YAML directory",
        value=_default_app_dir,
        placeholder="/path/to/app/yamls",
        help="Folder containing app YAML definitions. Can be local even when data is remote.",
    )

    _default_data_dir = str(_platform.data_dir) if _platform.data_dir else ""
    data_dir = st.text_input(
        "Data directory",
        value=_default_data_dir,
        placeholder="/path/to/rdv/data",
        help="Folder containing RDV files. Can be a remote/cloud path.",
    )

    # Back button shown only when an app is open
    if st.session_state.get("selected_app_id") is not None:
        st.markdown("---")
        if st.button("← All apps"):
            st.session_state["selected_app_id"] = None
            st.rerun()

    st.markdown("---")
    st.caption("UI layer — will be replaced by React frontend.")

if not app_dir or not data_dir:
    st.info("Enter an App YAML directory and a data directory in the sidebar to get started.")
    st.stop()

if not Path(app_dir).is_dir():
    st.error(f"App YAML directory not found: `{app_dir}`")
    st.stop()

if not Path(data_dir).is_dir():
    st.error(f"Data directory not found: `{data_dir}`")
    st.stop()

# ── Load app list ──────────────────────────────────────────────────────────────

try:
    apps = _load_apps(app_dir)
except Exception as exc:
    st.error(f"Failed to discover app YAMLs: {exc}")
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 1 — HOME: app card gallery
# ══════════════════════════════════════════════════════════════════════════════

if st.session_state.get("selected_app_id") is None:
    st.title("PICTURE Apps")

    if not apps:
        st.info(
            f"No app YAML files found in `{app_dir}`.  "
            "Add `.yaml` files to that directory to get started."
        )
        st.stop()

    st.caption(f"{len(apps)} app{'s' if len(apps) != 1 else ''} available")
    st.markdown("---")

    # Render cards in rows of 3
    COLS_PER_ROW = 3
    for row_start in range(0, len(apps), COLS_PER_ROW):
        row_apps = apps[row_start : row_start + COLS_PER_ROW]
        cols = st.columns(COLS_PER_ROW)

        for col, app in zip(cols, row_apps):
            with col:
                with st.container(border=True):
                    st.subheader(app.title)

                    if app.description:
                        # Trim to ~160 chars so cards stay the same height
                        desc = app.description.strip()
                        if len(desc) > 160:
                            desc = desc[:157] + "…"
                        st.markdown(desc)

                    # Metadata pills
                    meta_parts: list[str] = []
                    if app.creator:
                        meta_parts.append(f"👤 {app.creator}")
                    if app.dataset:
                        meta_parts.append(f"📂 {app.dataset}")
                    if app.initial_cohorts:
                        meta_parts.append(f"👥 {len(app.initial_cohorts)} cohort{'s' if len(app.initial_cohorts) != 1 else ''}")
                    if meta_parts:
                        st.caption("  ·  ".join(meta_parts))

                    if st.button("Open", key=f"open_{app.id}", type="primary", use_container_width=False):
                        st.session_state["selected_app_id"] = app.id
                        st.rerun()

    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# SCREEN 2 — ANALYSIS: cohort resolution + YAML-driven tabs
# ══════════════════════════════════════════════════════════════════════════════

selected_id: int = st.session_state["selected_app_id"]
app = next((a for a in apps if a.id == selected_id), None)

if app is None:
    st.error(f"App {selected_id} not found.")
    st.session_state["selected_app_id"] = None
    st.rerun()

# Load RDVs and resolve cohorts
try:
    rdvs = _load_rdvs(data_dir)
except Exception as exc:
    st.error(f"Failed to load RDVs: {exc}")
    st.stop()

if not rdvs:
    st.warning("No RDV files found in the data directory.")
    st.stop()

resolved_cohorts = _resolve_cohorts(app, data_dir, rdvs)

# ── App header ─────────────────────────────────────────────────────────────────

st.title(app.title)
if app.description:
    st.markdown(app.description.strip())

# Cohort summary bar
if resolved_cohorts:
    cohort_cols = st.columns(len(resolved_cohorts))
    for col, cohort in zip(cohort_cols, resolved_cohorts):
        col.metric(cohort.label, f"{cohort.n_patients:,} patients", f"{cohort.n_periods:,} periods")

st.markdown("---")

# ── Tabs: Cohorts (editor) + analysis tabs ─────────────────────────────────────

analysis_tab_labels = [t.tab for t in app.analysis] if app.analysis else []
all_tab_labels = ["Cohorts"] + analysis_tab_labels
all_st_tabs = st.tabs(all_tab_labels)

# ── Cohorts tab ─────────────────────────────────────────────────────────────────

with all_st_tabs[0]:
    from ui.pages.cohort_editor import render as render_cohort_editor
    render_cohort_editor(
        app_id=app.id,
        initial_cohorts=app.initial_cohorts or [],
        rdvs=rdvs,
        data_dir=data_dir,
    )
    # Re-read resolved_cohorts in case the editor just re-resolved them
    resolved_cohorts = st.session_state.get(
        f"cohorts:{app.id}:{data_dir}", resolved_cohorts
    )

# ── Analysis tabs ───────────────────────────────────────────────────────────────

for st_tab, analysis_tab in zip(all_st_tabs[1:], app.analysis or []):
    with st_tab:
        if not analysis_tab.method_list:
            st.info("No methods defined for this tab.")
            continue

        # Single method → no sub-tabs needed; multiple → sub-tabs
        if len(analysis_tab.method_list) == 1:
            containers = [st.container()]
        else:
            sub_labels = [m.tab_lbl or m.fn for m in analysis_tab.method_list]
            containers = list(st.tabs(sub_labels))

        for container, method in zip(containers, analysis_tab.method_list):
            with container:
                page_key = _FN_REGISTRY.get(method.fn)

                if page_key == "frequency":
                    from ui.pages.frequency import render as render_frequency
                    render_frequency(
                        method=method,
                        resolved_cohorts=resolved_cohorts,
                        rdvs=rdvs,
                    )
                elif page_key == "demographics":
                    from ui.pages.demographics import render as render_demographics
                    render_demographics(
                        method=method,
                        resolved_cohorts=resolved_cohorts,
                        rdvs=rdvs,
                    )
                elif page_key == "distribution":
                    from ui.pages.distribution import render as render_distribution
                    render_distribution(
                        method=method,
                        resolved_cohorts=resolved_cohorts,
                        rdvs=rdvs,
                    )
                else:
                    st.info(
                        f"`{method.fn}` is not yet implemented in the Python UI.  "
                        "It will appear here once the analytics module is ported."
                    )
