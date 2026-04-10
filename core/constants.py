"""Shared constants used across core analytics, cohort, and data modules.

Centralising column names here prevents typo bugs and makes bulk renames trivial.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Column names
# ---------------------------------------------------------------------------

#: Primary patient identifier column, present in every RDV.
PROJECT_ID_COL: str = "project_id"

#: Column added by apply_cohorts_to_rdv / AnalysisBase to carry cohort labels.
COHORT_COL: str = "cohort"

#: Per-cohort-period patient identifier (project_id + period index).
COHORT_ID_COL: str = "cohort_id"

#: Standard start/end datetime column names in clinical RDVs.
START_DATETIME_COL: str = "start_datetime"
END_DATETIME_COL: str = "end_datetime"

#: Cohort window boundary columns added after patient-list merge.
ENTRY_DATE_COL: str = "entry_date"
EXIT_DATE_COL: str = "exit_date"

#: Demographics RDV key used in the rdvs dict.
PDE_RDV_NAME: str = "pde"

# ---------------------------------------------------------------------------
# Sentinel / default labels
# ---------------------------------------------------------------------------

#: Cohort label used when no cohorts are defined.
DEFAULT_COHORT_LABEL: str = "All"

#: Category value substituted for missing / NaN entries in categorical columns.
UNKNOWN_CATEGORY: str = "Unknown"
