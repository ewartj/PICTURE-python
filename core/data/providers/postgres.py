"""
PostgresProvider — loads RDVs from a PostgreSQL database via SQLAlchemy.

Each RDV maps to a table with the same short name (``pde``, ``dia``, etc.).
Column names in the database match those defined in ``core/data/rdv.py`` and
produced by ``scripts/load_to_postgres.py``.

Usage:
    from core.data.providers.postgres import PostgresProvider

    provider = PostgresProvider("postgresql://user:pass@localhost:5432/picture")
    rdvs = provider.load_all_rdvs()
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, inspect, text

from core.data.loader import _optimise_dtypes, _parse_datetimes, _validate
from core.data.rdv import RDV_FILE_MAP, RdvName

logger = logging.getLogger(__name__)


class PostgresProvider:
    """DataProvider backed by a PostgreSQL database."""

    def __init__(self, db_url: str) -> None:
        """
        Args:
            db_url: SQLAlchemy connection string, e.g.
                    ``postgresql://user:pass@host:5432/dbname``
        """
        self._engine = create_engine(db_url, future=True, pool_pre_ping=True)

    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    def load_rdv(self, rdv: RdvName, n_max: Optional[int] = None) -> pd.DataFrame:
        """Load a single RDV table and return it as a DataFrame.

        Raises:
            ValueError: If the table does not exist in the database.
        """
        table = str(rdv)
        if not self._table_exists(table):
            raise ValueError(
                f"Table '{table}' not found in the database. "
                f"Run scripts/load_to_postgres.py to load the data first."
            )

        limit_clause = f"LIMIT {n_max}" if n_max is not None else ""
        query = text(f"SELECT * FROM {table} {limit_clause}")

        logger.info("Loading RDV '%s' from Postgres (limit=%s)", rdv, n_max)
        with self._engine.connect() as conn:
            df = pd.read_sql(query, conn)

        df = _parse_datetimes(df)
        df = _optimise_dtypes(df)
        _validate(rdv, df)
        logger.info("Loaded '%s': %d rows, %d cols", rdv, len(df), len(df.columns))
        return df

    def load_all_rdvs(
        self,
        n_max: Optional[int] = None,
        rdvs: Optional[list[RdvName]] = None,
    ) -> dict[str, pd.DataFrame]:
        """Load multiple RDV tables and return them keyed by RDV name.

        Tables that don't exist are silently skipped (matching FileProvider
        behaviour for missing files).
        """
        targets: list[RdvName] = rdvs if rdvs is not None else list(RDV_FILE_MAP.keys())  # type: ignore[arg-type]
        result: dict[str, pd.DataFrame] = {}

        for rdv in targets:
            try:
                result[rdv] = self.load_rdv(rdv, n_max=n_max)
            except ValueError:
                logger.debug("Table '%s' not found — skipping.", rdv)

        return result

    def list_available_rdvs(self) -> list[RdvName]:
        """Return the RDV names whose tables exist in the database."""
        existing_tables = inspect(self._engine).get_table_names()
        return [rdv for rdv in RDV_FILE_MAP if rdv in existing_tables]  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _table_exists(self, table: str) -> bool:
        return inspect(self._engine).has_table(table)
