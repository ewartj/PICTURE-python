"""
RDV metadata lookups.

Mirrors picture.platform R/utils_rdv_lookups.R.

Provides human-readable labels and metadata for RDV codes and their
variables, loaded from the bundled CSV lookup tables.

Usage::

    from core.rdv.lookups import get_variable_label, get_rdv_label

    get_rdv_label("dia_conditions")          # "diagnoses - medical conditions"
    get_variable_label("dia_conditions", "diag_name")   # "diagnosis name"
    get_variable_filter_type("pde", "sex_name")         # "str_matches"
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

import pandas as pd

_DIR = Path(__file__).parent


# ── CSV loaders (cached) ────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _rdv_codes() -> pd.DataFrame:
    df = pd.read_csv(_DIR / "rdv_code_lookup.csv")
    df.columns = df.columns.str.strip()
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip().str.strip('"')
    return df


@lru_cache(maxsize=1)
def _rdv_variables() -> pd.DataFrame:
    df = pd.read_csv(_DIR / "rdv_variable_lookup.csv")
    df.columns = df.columns.str.strip()
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip().str.strip('"')
    return df


# ── RDV-level lookups ───────────────────────────────────────────────────────────

def get_rdv_label(rdv_code: str) -> str:
    """Return the human-readable label for an RDV code.

    >>> get_rdv_label("pde")
    'demographics'
    """
    row = _rdv_codes()[_rdv_codes()["rdv_code"] == rdv_code]
    return row["label"].iloc[0].strip() if not row.empty else rdv_code


def get_rdv_description(rdv_code: str) -> str:
    """Return the description for an RDV code."""
    row = _rdv_codes()[_rdv_codes()["rdv_code"] == rdv_code]
    return row["description"].iloc[0].strip() if not row.empty else ""


def get_rdv_type(rdv_code: str) -> str:
    """Return the rdv_type (e.g. 'patient_diagnoses') for an RDV code."""
    row = _rdv_codes()[_rdv_codes()["rdv_code"] == rdv_code]
    return row["rdv_type"].iloc[0].strip() if not row.empty else ""


def list_rdv_codes() -> list[str]:
    """Return all known RDV codes."""
    return _rdv_codes()["rdv_code"].tolist()


# ── Variable-level lookups ──────────────────────────────────────────────────────

def get_variable_label(rdv_code: str, variable_code: str) -> str:
    """Return the human-readable label for an RDV variable.

    >>> get_variable_label("pde", "sex_name")
    'sex'
    """
    row = _var_row(rdv_code, variable_code)
    return row["label"].iloc[0].strip() if not row.empty else variable_code


def get_variable_description(rdv_code: str, variable_code: str) -> str:
    """Return the description for an RDV variable."""
    row = _var_row(rdv_code, variable_code)
    return row["description"].iloc[0].strip() if not row.empty else ""


def get_variable_filter_type(rdv_code: str, variable_code: str) -> Optional[str]:
    """Return the recommended filter_type (e.g. 'str_matches', 'date_between').

    Returns None if the variable is not in the lookup.
    """
    row = _var_row(rdv_code, variable_code)
    return row["filter_type"].iloc[0].strip() if not row.empty else None


def get_variable_input_type(rdv_code: str, variable_code: str) -> Optional[str]:
    """Return the UI input_type ('select', 'text', 'date_range', 'age_range', 'numeric_range')."""
    row = _var_row(rdv_code, variable_code)
    return row["input_type"].iloc[0].strip() if not row.empty else None


def get_rdv_variables(rdv_code: str) -> list[dict]:
    """Return all variables defined for an RDV as a list of dicts.

    Each dict has keys: variable_code, label, description, input_type, filter_type.
    """
    rows = _rdv_variables()[_rdv_variables()["rdv_code"] == rdv_code]
    return rows.drop(columns=["rdv_code"]).to_dict(orient="records")


# ── Private ─────────────────────────────────────────────────────────────────────

def _var_row(rdv_code: str, variable_code: str) -> pd.DataFrame:
    df = _rdv_variables()
    return df[(df["rdv_code"] == rdv_code) & (df["variable_code"] == variable_code)]
