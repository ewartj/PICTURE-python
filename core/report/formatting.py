"""
Report metadata table generation.

Mirrors picture.platform R/utils_report_formatting.R.

Generates small summary DataFrames that describe the patient, cohorts,
analysis run, and dataset.  These are intended for inclusion in PDF
reports (future) and in the Streamlit UI info panels.

Usage::

    from core.report.formatting import (
        report_patient_info_table,
        report_cohort_info_table,
        report_analysis_info_table,
        report_dataset_info_table,
    )
"""

from __future__ import annotations

import hashlib
import os
import platform
from datetime import date, datetime
from typing import Optional

import pandas as pd

from core.cohort.formatting import describe_cohort_short
from core.cohort.models import CohortDefinition


# ── Patient info ────────────────────────────────────────────────────────────────


def report_patient_info_table(
    project_id: str,
    pde_df: pd.DataFrame,
) -> pd.DataFrame:
    """Return a two-column (Field / Value) table of patient demographics.

    Mirrors R ``report_patient_info_table()``.

    Args:
        project_id: The patient's project_id.
        pde_df:     The full demographics RDV filtered to this patient.
    """
    row = pde_df[pde_df["project_id"] == project_id]
    if row.empty:
        return pd.DataFrame({"Field": ["Patient ID"], "Value": [project_id]})

    r = row.iloc[0]

    def _fmt_date(val) -> str:
        if pd.isna(val):
            return ""
        try:
            return pd.to_datetime(val).strftime("%-d %B %Y")
        except Exception:
            return str(val)

    def _age(dob) -> str:
        if pd.isna(dob):
            return ""
        try:
            today = date.today()
            born = pd.to_datetime(dob).date()
            years = (today - born).days / 365.25
            return f"{years:.1f} years"
        except Exception:
            return ""

    dob = r.get("birth_date")
    records = [
        ("Patient ID", str(project_id)),
        ("Sex", str(r.get("sex_name", ""))),
        ("Date of birth", _fmt_date(dob)),
        ("Age", _age(dob)),
        ("Ethnicity", str(r.get("ethnicity_name", ""))),
    ]
    if "death_date" in r and pd.notna(r["death_date"]):
        records.append(("Date of death", _fmt_date(r["death_date"])))

    return pd.DataFrame(records, columns=["Field", "Value"])


# ── Cohort info ─────────────────────────────────────────────────────────────────


def report_cohort_info_table(cohort_defs: list[CohortDefinition]) -> pd.DataFrame:
    """Return a two-column (Cohort / Description) table of cohort definitions.

    Mirrors R ``report_cohort_info_table(cohort_defs)``.
    """
    records = [(c.label, describe_cohort_short(c)) for c in cohort_defs]
    return pd.DataFrame(records, columns=["Cohort", "Description"])


# ── Analysis run info ───────────────────────────────────────────────────────────


def report_analysis_info_table(session_string: str = "") -> pd.DataFrame:
    """Return a two-column (Field / Value) table of analysis run metadata.

    Mirrors R ``report_analysis_info_table(session_string)``.

    Includes: PICTURE version, date/time, analyst username, a short report ID.
    """
    now = datetime.now()
    date_str = now.strftime("%-d %B %Y at %H:%M:%S")
    username = _get_username()

    # Short hash for report ID
    raw = f"{date_str}{username}{session_string}"
    report_id = hashlib.md5(raw.encode()).hexdigest()[:12].upper()

    try:
        from importlib.metadata import version

        picture_version = version("picture-python")
    except Exception:
        picture_version = "dev"

    records = [
        ("PICTURE Version", picture_version),
        ("Date", date_str),
        ("Analyst", username),
        ("Report ID", report_id),
    ]
    return pd.DataFrame(records, columns=["Field", "Value"])


# ── Dataset info ────────────────────────────────────────────────────────────────


def report_dataset_info_table(
    name: str,
    description: str = "",
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    extraction_date: Optional[str] = None,
) -> pd.DataFrame:
    """Return a two-column (Field / Value) table of dataset metadata.

    Mirrors R ``report_dataset_info_table(dataset_summary)``.
    """

    def _fmt(val) -> str:
        if not val:
            return ""
        try:
            return pd.to_datetime(val).strftime("%-d %B %Y")
        except Exception:
            return str(val)

    period = ""
    if from_date or to_date:
        period = f"{_fmt(from_date)} to {_fmt(to_date)}"

    records = [
        ("Name", name),
        ("Description", description),
        ("Period", period),
        ("Extraction Date", _fmt(extraction_date)),
    ]
    return pd.DataFrame(records, columns=["Field", "Value"])


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _get_username() -> str:
    """Return the current OS username.  Mirrors R ``get_username()``."""
    try:
        return os.getlogin()
    except Exception:
        return os.environ.get("USER") or os.environ.get("USERNAME") or platform.node()
