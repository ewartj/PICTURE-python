"""
PICTURE Streamlit application — temporary UI layer.

This will be replaced by a React frontend once the API layer is stable.
All business logic lives in core/ and is accessed via api/ service functions.
This file should contain ONLY layout and display code.

Run with:
    streamlit run ui/app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is on the path when running from ui/
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

st.set_page_config(
    page_title="PICTURE Analytics",
    page_icon=":bar_chart:",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Sidebar — data directory and cohort config
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("PICTURE")
    st.markdown("---")

    data_dir = st.text_input(
        "Data directory",
        value="",
        placeholder="/path/to/rdv/data",
        help="Path to the folder containing RDV CSV or Parquet files.",
    )

    st.markdown("---")
    st.caption("UI layer — will be replaced by React frontend.")

# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------

PAGES = {
    "Frequency Analysis": "ui/pages/frequency.py",
    # Add more pages here as analytics modules are implemented:
    # "Distribution": "ui/pages/distribution.py",
    # "Correlation": "ui/pages/correlation.py",
    # "Time Series": "ui/pages/timeseries.py",
    # "Demographics": "ui/pages/demographics.py",
}

page = st.sidebar.radio("Analysis", list(PAGES.keys()))

if not data_dir:
    st.info("Enter a data directory in the sidebar to get started.")
    st.stop()

# ---------------------------------------------------------------------------
# Load selected page
# ---------------------------------------------------------------------------

if page == "Frequency Analysis":
    from ui.pages.frequency import render
    render(data_dir=data_dir)
else:
    st.warning(f"Page '{page}' not yet implemented.")
