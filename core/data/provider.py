"""
DataProvider protocol — the contract every backend must satisfy.

Any class that implements ``load_rdv`` and ``load_all_rdvs`` with the correct
signatures is a valid DataProvider; no inheritance required.

Current implementations:
    core.data.providers.file.FileProvider      — CSV / Parquet flat files
    core.data.providers.postgres.PostgresProvider — PostgreSQL via SQLAlchemy
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

import pandas as pd

from core.data.rdv import RdvName


@runtime_checkable
class DataProvider(Protocol):
    """Read RDVs and return them as pandas DataFrames.

    Each implementation is responsible for fetching the data and returning it
    with the column names defined in ``core/data/rdv.py``.  The analytics,
    cohort, and service layers only ever see ``dict[str, pd.DataFrame]`` —
    they are unaware of where the data came from.
    """

    def load_rdv(
        self,
        rdv: RdvName,
        n_max: Optional[int] = None,
    ) -> pd.DataFrame:
        """Load a single RDV and return it as a DataFrame.

        Args:
            rdv:   RDV identifier (e.g. ``"pde"``, ``"dia"``).
            n_max: Maximum rows to return.  ``None`` means all rows.

        Returns:
            DataFrame with datetime columns already parsed.

        Raises:
            KeyError / FileNotFoundError / sqlalchemy.exc.* as appropriate.
        """
        ...

    def load_all_rdvs(
        self,
        n_max: Optional[int] = None,
        rdvs: Optional[list[RdvName]] = None,
    ) -> dict[str, pd.DataFrame]:
        """Load multiple RDVs and return them keyed by RDV name.

        Args:
            n_max: Maximum rows per RDV.
            rdvs:  Subset to load.  ``None`` loads all available.

        Returns:
            Dict mapping RDV name → DataFrame.  RDVs that are not found
            (missing file, missing table, etc.) are silently omitted.
        """
        ...

    def list_available_rdvs(self) -> list[RdvName]:
        """Return the RDV names that this provider can serve."""
        ...
