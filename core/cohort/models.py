"""
Cohort data models.

A *cohort* is a labelled set of patients with associated entry/exit date
windows.  Multiple cohorts can be defined for side-by-side comparison in
analytics modules.

Replaces: picture.platform R/ui_select_cohort-shiny.R
          picture.platform R/utils_segment_cohorts.R (data structures)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal, Optional

import pandas as pd

QueryType = Literal[
    "str_matches",
    "str_contains",
    "str_starts",
    "date_between",
    "age_between",
    "numeric_between",
]

Inclusion = Literal[
    "ever",
    "never",
    "fully_concurrent",
    "after_first",
    "on_first",
]


@dataclass
class CohortFilterStep:
    """A single filter step within a cohort definition.

    Mirrors one row of the YAML ``initialCohorts[].config`` list.
    """

    type: Literal["base", "filter", "and"]
    rdv: Optional[str] = None  # e.g. "pde", "dia"
    column: Optional[str] = None  # column name in the RDV
    val: Optional[list] = None  # filter value(s)
    inclusion: Inclusion = "ever"
    query_type: QueryType = "str_matches"
    window: Optional[list[int]] = None  # [days_before, days_after]


@dataclass
class CohortDefinition:
    """Definition of a single named cohort, built from YAML config.

    Example YAML::

        label: Female
        config:
          - type: filter
            rdv: pde
            val: [Female]
            inclusion: ever
            column: sex_name
            query_type: str_matches
    """

    label: str
    config: list[CohortFilterStep] = field(default_factory=list)


@dataclass
class ResolvedCohort:
    """A cohort after patient lists have been resolved against actual data.

    ``patient_list`` is a DataFrame with columns:
        - project_id
        - entry_date
        - exit_date
        - cohort_id   (unique per patient-period, "{project_id}-{n:06d}")
    """

    label: str
    patient_list: pd.DataFrame
    n_patients: int = 0
    n_periods: int = 0

    def __post_init__(self) -> None:
        if not self.patient_list.empty:
            self.n_patients = self.patient_list["project_id"].nunique()
            self.n_periods = len(self.patient_list)


def cohort_definition_from_yaml(raw: dict) -> CohortDefinition:
    """Parse a single cohort dict from a YAML app definition."""
    steps = [
        CohortFilterStep(
            type=step.get("type", "filter"),
            rdv=step.get("rdv"),
            column=step.get("column"),
            val=step.get("val") if isinstance(step.get("val"), list) else [step.get("val")],
            inclusion=step.get("inclusion", "ever"),
            query_type=step.get("query_type", "str_matches"),
            window=step.get("window"),
        )
        for step in raw.get("config", [])
    ]
    return CohortDefinition(label=raw["label"], config=steps)
