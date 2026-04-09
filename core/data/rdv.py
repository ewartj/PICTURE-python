"""
RDV (Research Data View) registry.

Each RDV is a named tabular dataset with a known schema. This module defines
the canonical names, expected columns, and load helpers for every RDV that
PICTURE supports.

Replaces: picture.platform R/utils_rdv_lookups.R
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# RDV identifiers — these match the file stem in data_dir
# (e.g. "pde" → dmv_caboodle_patient_demographics.csv / .parquet)
# ---------------------------------------------------------------------------

RdvName = Literal[
    "pde",  # Patient Demographics
    "dia",  # Diagnoses (ICD-10)
    "adm",  # Hospital Admissions
    "med",  # Medication Orders
    "mda",  # Medication Administrations
    "prc",  # Procedures (OPCS)
    "flo",  # Flowsheet rows
    "lab",  # Lab results
    "tht",  # Theatre list
    "wst",  # Ward stays
    "loc",  # Locations
]

# Canonical file name prefixes — kept in sync with dummy CSV filenames
RDV_FILE_MAP: dict[str, str] = {
    "pde": "dmv_caboodle_patient_demographics",
    "dia": "dmv_caboodle_patient_diagnoses",
    "adm": "dmv_caboodle_patient_hospital_admissions",
    "med": "dmv_caboodle_patient_medication_orders",
    "mda": "dmv_caboodle_patient_medication_admins",
    "prc": "dmv_caboodle_patient_procedures",
    "flo": "dmv_caboodle_patient_selected_flowsheetrows_main",
    "lab": "dmv_caboodle_patient_selected_lab_components_main",
    "tht": "dmv_caboodle_patient_theatre_list",
    "wst": "dmv_caboodle_patient_ward_stays",
    "loc": "dmv_caboodle_patient_locations",
}


@dataclass
class RdvSchema:
    """Minimal schema description for an RDV."""

    name: str
    label: str
    # Columns that must be present (used for validation on load)
    required_cols: list[str] = field(default_factory=list)
    # Whether this RDV has start/end datetimes (enables temporal filtering)
    has_datetimes: bool = False
    # Primary patient identifier column
    patient_id_col: str = "project_id"


RDV_SCHEMAS: dict[str, RdvSchema] = {
    "pde": RdvSchema(
        name="pde",
        label="Patient Demographics",
        required_cols=["project_id", "birth_date", "sex_name"],
        has_datetimes=False,
    ),
    "dia": RdvSchema(
        name="dia",
        label="Diagnoses",
        required_cols=["project_id", "diag_name", "start_datetime"],
        has_datetimes=True,
    ),
    "adm": RdvSchema(
        name="adm",
        label="Hospital Admissions",
        required_cols=["project_id", "start_datetime", "end_datetime"],
        has_datetimes=True,
    ),
    "med": RdvSchema(
        name="med",
        label="Medication Orders",
        required_cols=["project_id", "medication_name", "start_datetime"],
        has_datetimes=True,
    ),
    "mda": RdvSchema(
        name="mda",
        label="Medication Administrations",
        required_cols=["project_id", "medication_name", "start_datetime"],
        has_datetimes=True,
    ),
    "prc": RdvSchema(
        name="prc",
        label="Procedures",
        required_cols=["project_id", "procedure_name", "start_datetime"],
        has_datetimes=True,
    ),
    "flo": RdvSchema(
        name="flo",
        label="Flowsheet Rows",
        required_cols=["project_id", "flowsheet_measure_name", "start_datetime"],
        has_datetimes=True,
    ),
    "lab": RdvSchema(
        name="lab",
        label="Lab Results",
        required_cols=[
            "project_id",
            "component_name",
            "result_value",
            "start_datetime",
        ],
        has_datetimes=True,
    ),
    "tht": RdvSchema(
        name="tht",
        label="Theatre List",
        required_cols=["project_id", "start_datetime"],
        has_datetimes=True,
    ),
    "wst": RdvSchema(
        name="wst",
        label="Ward Stays",
        required_cols=["project_id", "ward_code", "start_datetime", "end_datetime"],
        has_datetimes=True,
    ),
    "loc": RdvSchema(
        name="loc",
        label="Locations",
        required_cols=["project_id"],
        has_datetimes=False,
    ),
}
