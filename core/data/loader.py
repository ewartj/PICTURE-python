"""
RDV data loader.

Loads Research Data Views from CSV or Parquet files and returns them as
pandas DataFrames.  Supports optional row limits and basic column validation.

Replaces: picture.platform R/ui_load_rdvs-shiny.R + utils_rdv_lookups.R
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from core.data.rdv import RDV_FILE_MAP, RDV_SCHEMAS, RdvName

logger = logging.getLogger(__name__)

# Columns to parse as datetimes on load (if present)
_DATETIME_COLS = [
    "start_datetime",
    "end_datetime",
    "birth_date",
    "death_date",
    "entry_date",
    "exit_date",
]

# String columns to convert to Categorical after loading.
# Categorical uses ~8 bytes/value instead of ~64 bytes (Python object ptr),
# and makes groupby/merge significantly faster on large DataFrames.
_CATEGORICAL_COLS = [
    # Demographics
    "sex_name",
    "ethnicity_name",
    "death_status",
    # Diagnoses
    "diag_name",
    "diagnosis_status",
    "icd10_chapter",
    "icd10_section",
    "icd10_code",
    # Clinical
    "medication_name",
    "procedure_name",
    "ward_code",
    "ward_name",
    "flowsheet_measure_name",
    "component_name",
    "result_status",
    "abnormal_flag",
    # Cohort labels (added dynamically, but include here for re-loads)
    "cohort",
]


def load_rdv(
    rdv: RdvName,
    data_dir: str | Path,
    n_max: Optional[int] = None,
) -> pd.DataFrame:
    """Load a single RDV from *data_dir*.

    Tries Parquet first (faster), falls back to CSV.

    Args:
        rdv:      RDV identifier (e.g. "pde", "dia").
        data_dir: Directory containing the data files.
        n_max:    Maximum rows to load.  ``None`` means load all.

    Returns:
        DataFrame with datetime columns parsed.

    Raises:
        FileNotFoundError: If neither Parquet nor CSV is found.
        ValueError:        If required columns are missing.
    """
    data_dir = Path(data_dir)
    stem = RDV_FILE_MAP[rdv]

    parquet_path = data_dir / f"{stem}.parquet"
    csv_path = data_dir / f"{stem}.csv"

    if parquet_path.exists():
        logger.info("Loading %s from Parquet: %s", rdv, parquet_path)
        df = pd.read_parquet(parquet_path)
        if n_max is not None:
            df = df.head(n_max)
    elif csv_path.exists():
        logger.info("Loading %s from CSV: %s", rdv, csv_path)
        df = pd.read_csv(csv_path, nrows=n_max, low_memory=False)
    else:
        raise FileNotFoundError(
            f"No data file found for RDV '{rdv}' in {data_dir}. "
            f"Expected '{stem}.parquet' or '{stem}.csv'."
        )

    df = _parse_datetimes(df)
    df = _optimise_dtypes(df)
    _validate(rdv, df)
    logger.info("Loaded %s: %d rows, %d cols", rdv, len(df), len(df.columns))
    return df


def load_all_rdvs(
    data_dir: str | Path,
    n_max: Optional[int] = None,
    rdvs: Optional[list[RdvName]] = None,
) -> dict[str, pd.DataFrame]:
    """Load multiple RDVs and return as a dict keyed by RDV name.

    Args:
        data_dir: Directory containing the data files.
        n_max:    Maximum rows per RDV.
        rdvs:     Subset of RDV names to load.  ``None`` loads all available.

    Returns:
        Dict mapping RDV name → DataFrame (only RDVs where a file was found).
    """
    data_dir = Path(data_dir)
    targets: list[RdvName] = rdvs if rdvs is not None else list(RDV_FILE_MAP.keys())  # type: ignore[arg-type]
    result: dict[str, pd.DataFrame] = {}

    for rdv in targets:
        try:
            result[rdv] = load_rdv(rdv, data_dir, n_max=n_max)
        except FileNotFoundError:
            logger.debug("RDV '%s' not found in %s — skipping.", rdv, data_dir)

    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _parse_datetimes(df: pd.DataFrame) -> pd.DataFrame:
    for col in _DATETIME_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=False)
    return df


def _optimise_dtypes(df: pd.DataFrame) -> pd.DataFrame:
    """Convert known low-cardinality string columns to Categorical.

    Reduces memory ~8× for these columns and speeds up groupby/merge.
    Only converts columns that are actually present and still object dtype
    (Parquet may already carry richer types).
    """
    for col in _CATEGORICAL_COLS:
        if col in df.columns and df[col].dtype == object:
            df[col] = df[col].astype("category")
    return df


def _validate(rdv: RdvName, df: pd.DataFrame) -> None:
    schema = RDV_SCHEMAS.get(rdv)
    if schema is None:
        return
    missing = [c for c in schema.required_cols if c not in df.columns]
    if missing:
        logger.warning("RDV '%s' is missing expected columns: %s", rdv, missing)
