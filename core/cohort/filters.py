"""
Cohort filtering logic.

Resolves CohortDefinitions against loaded RDV DataFrames, producing
ResolvedCohort objects that carry a patient list with entry/exit windows.

Replaces: picture.platform R/utils_segment_cohorts.R
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Callable

import pandas as pd

from core.cohort.models import (
    CohortDefinition,
    CohortFilterStep,
    Inclusion,
    ResolvedCohort,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def resolve_cohort(
    definition: CohortDefinition,
    rdvs: dict[str, pd.DataFrame],
) -> ResolvedCohort:
    """Resolve a CohortDefinition against loaded RDVs.

    Args:
        definition: Cohort filter definition (from YAML or UI).
        rdvs:       Dict of loaded RDV DataFrames keyed by RDV name.

    Returns:
        ResolvedCohort with patient_list populated.
    """
    logger.info("Resolving cohort: %s", definition.label)

    patient_list: pd.DataFrame = pd.DataFrame()
    filter_fns: list[Callable] = []

    for step in definition.config:
        if step.type == "base":
            patient_list = _base_patient_list(rdvs["pde"])

        elif step.type in ("filter", "and"):
            if step.type == "filter":
                filter_fns = []

            if patient_list.empty:
                patient_list = _base_patient_list(rdvs["pde"])

            rdv_name = step.rdv or "pde"
            rdv_df = rdvs.get(rdv_name)
            if rdv_df is None:
                logger.warning("RDV '%s' not loaded — skipping filter step.", rdv_name)
                continue

            filter_fn = _build_filter_fn(step)
            filter_fns.append(filter_fn)

            if step.inclusion in ("fully_concurrent", "after_first", "on_first"):
                filter_fns.append(_ff_concurrent)

            # Apply filter chain
            working = rdv_df.merge(patient_list, on="project_id", how="right")
            for fn in filter_fns:
                working = fn(working, step)

            new_list = working[["project_id", "entry_date", "exit_date"]].drop_duplicates()

            if step.inclusion == "never":
                excluded = new_list["project_id"].unique()
                patient_list = patient_list[~patient_list["project_id"].isin(excluded)]
            else:
                patient_list = new_list

            patient_list = _merge_contiguous_periods(patient_list)

    patient_list = _add_cohort_ids(patient_list)
    return ResolvedCohort(label=definition.label, patient_list=patient_list)


def apply_cohorts_to_rdv(
    rdv_df: pd.DataFrame,
    cohorts: list[ResolvedCohort],
) -> pd.DataFrame:
    """Filter and label an RDV DataFrame by a list of resolved cohorts.

    Each patient's events are filtered to those concurrent with their cohort
    window and tagged with the cohort label.  Equivalent to the R
    ``filter_by_cohorts()`` function.

    Returns:
        Combined DataFrame with an added ``cohort`` column.
    """
    frames: list[pd.DataFrame] = []

    rdv_df = _strip_tz(rdv_df)

    for cohort in cohorts:
        pl = cohort.patient_list
        filtered = rdv_df.merge(pl, on="project_id", how="inner")

        if _has_datetimes(filtered):
            filtered = _ff_concurrent(filtered, step=None)
            filtered = _ff_crop_start_end(filtered)

        filtered = filtered.assign(cohort=cohort.label)
        frames.append(filtered)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Filter function builders
# ---------------------------------------------------------------------------

def _build_filter_fn(step: CohortFilterStep) -> Callable:
    col = step.column
    vals = step.val or []
    qt = step.query_type

    if qt == "str_matches":
        pattern = "^(" + "|".join(re.escape(v) for v in vals) + ")$"
        return lambda df, _s: df[df[col].astype(str).str.match(pattern, na=False)]

    if qt == "str_contains":
        pattern = "(?i)(" + "|".join(re.escape(v) for v in vals) + ")"
        return lambda df, _s: df[df[col].astype(str).str.contains(pattern, na=False)]

    if qt == "str_starts":
        pattern = "^(" + "|".join(re.escape(v) for v in vals) + ")"
        return lambda df, _s: df[df[col].astype(str).str.match(pattern, na=False)]

    if qt in ("date_between", "numeric_between"):
        lo, hi = vals[0], vals[1]
        return lambda df, _s: df[(df[col] >= lo) & (df[col] <= hi)]

    if qt == "age_between":
        start_age, end_age = int(vals[0]), int(vals[1])
        return lambda df, _s: _filter_age_between(df, col, start_age, end_age)

    raise ValueError(f"Unknown query_type: {qt}")


def _filter_age_between(df: pd.DataFrame, col: str, start_age: int, end_age: int) -> pd.DataFrame:
    if "birth_date" not in df.columns:
        return df
    df = df.copy()
    df["_age_start"] = df["birth_date"] + pd.DateOffset(years=start_age)
    df["_age_end"] = df["birth_date"] + pd.DateOffset(years=end_age)
    df["entry_date"] = df[["entry_date", "_age_start"]].max(axis=1)
    df["exit_date"] = df[["exit_date", "_age_end"]].min(axis=1)
    df = df[df["entry_date"] <= df["exit_date"]]
    return df.drop(columns=["_age_start", "_age_end"])


# ---------------------------------------------------------------------------
# Temporal filter functions  (replaces R ff_* functions)
# ---------------------------------------------------------------------------

def _ff_concurrent(df: pd.DataFrame, step=None) -> pd.DataFrame:
    if not _has_datetimes(df):
        return df
    mask = (
        (df["start_datetime"] <= df["exit_date"]) &
        (df["end_datetime"].isna() | (df["end_datetime"] >= df["entry_date"]))
    )
    return df[mask]


def _ff_crop_start_end(df: pd.DataFrame) -> pd.DataFrame:
    if not _has_datetimes(df):
        return df
    df = df.copy()
    df["start_datetime"] = df[["entry_date", "start_datetime"]].max(axis=1)
    df["end_datetime"] = df[["exit_date", "end_datetime"]].min(axis=1)
    return df


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_patient_list(pde: pd.DataFrame) -> pd.DataFrame:
    today = pd.Timestamp.today().normalize()
    pl = pde[["project_id", "birth_date", "death_date"]].copy()
    pl["entry_date"] = pd.to_datetime(pl["birth_date"])
    pl["exit_date"] = pl["death_date"].fillna(today)
    pl["exit_date"] = pd.to_datetime(pl["exit_date"])
    return pl[["project_id", "entry_date", "exit_date"]].drop_duplicates()


def _add_cohort_ids(patient_list: pd.DataFrame) -> pd.DataFrame:
    if patient_list.empty:
        return patient_list
    patient_list = patient_list.copy()
    patient_list["cohort_id"] = (
        patient_list["project_id"].astype(str)
        + "-"
        + patient_list.groupby("project_id").cumcount().add(1).astype(str).str.zfill(6)
    )
    return patient_list


def _merge_contiguous_periods(patient_list: pd.DataFrame) -> pd.DataFrame:
    """Merge overlapping or contiguous entry/exit windows per patient."""
    if patient_list.empty:
        return patient_list

    result_rows = []
    for pid, grp in patient_list.groupby("project_id"):
        grp = grp.sort_values("entry_date").reset_index(drop=True)
        merged = [grp.iloc[0].to_dict()]
        for _, row in grp.iloc[1:].iterrows():
            last = merged[-1]
            if row["entry_date"] <= last["exit_date"]:
                last["exit_date"] = max(last["exit_date"], row["exit_date"])
            else:
                merged.append(row.to_dict())
        result_rows.extend(merged)

    return pd.DataFrame(result_rows)


def _has_datetimes(df: pd.DataFrame) -> bool:
    return "start_datetime" in df.columns and "end_datetime" in df.columns


def _strip_tz(df: pd.DataFrame) -> pd.DataFrame:
    """Convert any tz-aware datetime columns to tz-naive UTC.

    Parquet files store datetimes as ``datetime64[us, UTC]``.  The cohort
    patient-list dates (entry_date / exit_date) are tz-naive.  Pandas refuses
    to compare the two, so we strip the timezone before any comparison.
    """
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            if hasattr(df[col].dt, "tz") and df[col].dt.tz is not None:
                df[col] = df[col].dt.tz_localize(None)
    return df
