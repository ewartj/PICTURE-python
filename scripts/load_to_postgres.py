"""
Load RDV flat files (CSV or Parquet) into a PostgreSQL database.

Usage:
    python scripts/load_to_postgres.py \\
        --data-dir /path/to/dmv \\
        --db-url postgresql://user:pass@localhost:5432/picture

    # Or set the DATABASE_URL environment variable:
    DATABASE_URL=postgresql://... python scripts/load_to_postgres.py --data-dir /path/to/dmv

Column renames applied during load (CSV name → Postgres column name):
    flo.type           → flowsheet_measure_name
    med.drug_name      → medication_name
    mda.drug_name      → medication_name
    lab.Value          → result_value
    lab.ResultStatus   → result_status
    lab.abnormal       → abnormal_flag
    adm.disharge_*     → discharge_* (typo corrected)
    loc."LSOA Code"    → lsoa_code
    loc."MSOA Code"    → msoa_code

All other column names are lowercased and spaces replaced with underscores.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RDV → file stem mapping (mirrors core/data/rdv.py)
# ---------------------------------------------------------------------------

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
    # Reference table — not an RDV but included for completeness
    "dia_codes": "dmv_caboodle_patient_diagnoses_codes",
}

# ---------------------------------------------------------------------------
# Per-RDV column renames (applied before general normalisation)
# ---------------------------------------------------------------------------

_RENAMES: dict[str, dict[str, str]] = {
    "flo": {
        "type": "flowsheet_measure_name",
    },
    "med": {
        "drug_name": "medication_name",
        "MedicationOrderKey": "medication_order_key",
    },
    "mda": {
        "drug_name": "medication_name",
        "MedicationOrderKey": "medication_order_key",
    },
    "lab": {
        "Value": "result_value",
        "ResultStatus": "result_status",
        "abnormal": "abnormal_flag",
        "LabTestKey": "lab_test_key",
        "SpecimenType": "specimen_type",
        "SpecimenSource": "specimen_source",
        "Method": "method",
        "PathologyType": "pathology_type",
        "SourceType": "source_type",
        "Section": "section",
        "SubSection": "sub_section",
        "TestName": "test_name",
        "Unit": "unit",
        "NumericValue": "numeric_value",
    },
    "adm": {
        # Fix typo that exists in the source data
        "disharge_disposition": "discharge_disposition",
    },
    "loc": {
        "LSOA Code": "lsoa_code",
        "MSOA Code": "msoa_code",
        "District": "district",
        "County": "county",
        "Region": "region",
        "Country": "country",
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case."""
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    s = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", s)
    return s.lower()


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase, strip spaces, and normalise all remaining column names."""
    df.columns = [_camel_to_snake(col).replace(" ", "_").strip("_") for col in df.columns]
    return df


def _load_file(stem: str, data_dir: Path, n_max: Optional[int] = None) -> Optional[pd.DataFrame]:
    """Try Parquet first, fall back to CSV. Returns None if neither found."""
    parquet = data_dir / f"{stem}.parquet"
    csv = data_dir / f"{stem}.csv"

    if parquet.exists():
        logger.info("  Reading Parquet: %s", parquet.name)
        df = pd.read_parquet(parquet)
        return df.head(n_max) if n_max else df
    elif csv.exists():
        logger.info("  Reading CSV: %s", csv.name)
        return pd.read_csv(csv, nrows=n_max, low_memory=False)
    else:
        return None


def _apply_renames(rdv: str, df: pd.DataFrame) -> pd.DataFrame:
    """Apply per-RDV column renames, then general normalisation."""
    renames = _RENAMES.get(rdv, {})
    if renames:
        df = df.rename(columns=renames)
    return _normalise_columns(df)


def load_rdv_to_db(
    rdv: str,
    stem: str,
    data_dir: Path,
    engine,
    if_exists: str = "replace",
    n_max: Optional[int] = None,
) -> bool:
    """Load one RDV file into Postgres. Returns True if loaded, False if skipped."""
    df = _load_file(stem, data_dir, n_max)
    if df is None:
        logger.warning("  No file found for '%s' (%s) — skipping.", rdv, stem)
        return False

    df = _apply_renames(rdv, df)
    rows = len(df)

    logger.info("  Writing %d rows to table '%s' ...", rows, rdv)
    df.to_sql(
        rdv,
        engine,
        if_exists=if_exists,
        index=False,
        method="multi",
        chunksize=5_000,
    )
    logger.info("  Done: %s (%d rows)", rdv, rows)
    return True


def apply_indexes(engine, schema_path: Optional[Path] = None) -> None:
    """Apply indexes from schema.sql (skips CREATE TABLE statements)."""
    if schema_path is None:
        schema_path = Path(__file__).parent.parent / "db" / "schema.sql"

    if not schema_path.exists():
        logger.warning("schema.sql not found at %s — skipping index creation.", schema_path)
        return

    sql = schema_path.read_text()
    index_statements = [stmt.strip() for stmt in sql.split(";") if "CREATE INDEX" in stmt.upper()]

    with engine.connect() as conn:
        for stmt in index_statements:
            if stmt:
                try:
                    conn.execute(text(stmt))
                except Exception as exc:
                    logger.debug("Index already exists or failed: %s", exc)
        conn.commit()

    logger.info("Indexes applied (%d statements).", len(index_statements))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load PICTURE RDV flat files into PostgreSQL.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Directory containing RDV CSV or Parquet files.",
    )
    parser.add_argument(
        "--db-url",
        default=os.environ.get("DATABASE_URL"),
        help="SQLAlchemy connection string. Falls back to DATABASE_URL env var.",
    )
    parser.add_argument(
        "--if-exists",
        choices=["replace", "append", "fail"],
        default="replace",
        help="What to do if the table already exists.",
    )
    parser.add_argument(
        "--n-max",
        type=int,
        default=None,
        help="Maximum rows to load per table (useful for testing).",
    )
    parser.add_argument(
        "--rdvs",
        nargs="*",
        help="Subset of RDV names to load (e.g. pde dia). Loads all if omitted.",
    )
    parser.add_argument(
        "--no-indexes",
        action="store_true",
        help="Skip index creation after loading.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.db_url:
        logger.error("No --db-url provided and DATABASE_URL is not set.")
        sys.exit(1)

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        logger.error("data-dir does not exist: %s", data_dir)
        sys.exit(1)

    engine = create_engine(args.db_url, future=True)
    targets = args.rdvs or list(RDV_FILE_MAP.keys())

    logger.info("Connecting to: %s", args.db_url)
    logger.info("Loading %d RDV(s) from: %s", len(targets), data_dir)

    loaded, skipped = 0, 0
    for rdv in targets:
        stem = RDV_FILE_MAP.get(rdv)
        if stem is None:
            logger.warning("Unknown RDV '%s' — skipping.", rdv)
            skipped += 1
            continue

        logger.info("[%s]", rdv)
        ok = load_rdv_to_db(rdv, stem, data_dir, engine, args.if_exists, args.n_max)
        if ok:
            loaded += 1
        else:
            skipped += 1

    if not args.no_indexes:
        logger.info("Creating indexes ...")
        apply_indexes(engine)

    logger.info("Complete. Loaded: %d, Skipped: %d", loaded, skipped)


if __name__ == "__main__":
    main()
