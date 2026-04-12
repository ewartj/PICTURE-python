"""
FileProvider — loads RDVs from CSV or Parquet flat files.

This is a thin wrapper around ``core.data.loader`` that satisfies the
``DataProvider`` protocol, so it can be swapped for any other backend
without changing the analytics or API layers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from core.data.loader import load_all_rdvs, load_rdv
from core.data.rdv import RDV_FILE_MAP, RdvName

logger = logging.getLogger(__name__)


class FileProvider:
    """DataProvider backed by CSV / Parquet files in a local directory."""

    def __init__(self, data_dir: str | Path) -> None:
        self._data_dir = Path(data_dir)

    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    def load_rdv(self, rdv: RdvName, n_max: Optional[int] = None) -> pd.DataFrame:
        return load_rdv(rdv, self._data_dir, n_max=n_max)

    def load_all_rdvs(
        self,
        n_max: Optional[int] = None,
        rdvs: Optional[list[RdvName]] = None,
    ) -> dict[str, pd.DataFrame]:
        return load_all_rdvs(self._data_dir, n_max=n_max, rdvs=rdvs)

    def list_available_rdvs(self) -> list[RdvName]:
        available: list[RdvName] = []
        for rdv, stem in RDV_FILE_MAP.items():
            parquet = self._data_dir / f"{stem}.parquet"
            csv = self._data_dir / f"{stem}.csv"
            if parquet.exists() or csv.exists():
                available.append(rdv)  # type: ignore[arg-type]
        return available
