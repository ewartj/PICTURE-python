"""
FastAPI dependency injection.

Shared dependencies (config, cached DataFrames) are defined here and
injected into route handlers via FastAPI's Depends() mechanism.

This keeps route handlers thin and makes the data layer easy to swap
(e.g. replace file-based loading with a database in future).
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Annotated, Optional

import yaml
from fastapi import Depends, HTTPException, Query

from core.data.loader import load_all_rdvs, load_rdv
from core.data.rdv import RdvName

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


@functools.lru_cache(maxsize=1)
def get_config() -> dict:
    with open(_CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    return cfg.get("default", {})


# ---------------------------------------------------------------------------
# Data loading dependencies
# ---------------------------------------------------------------------------

def get_data_dir(
    data_dir: Annotated[Optional[str], Query(description="Override data directory")] = None,
    config: dict = Depends(get_config),
) -> Path:
    """Resolve the data directory from query param or config."""
    resolved = data_dir or config.get("data_dir")
    if not resolved:
        raise HTTPException(
            status_code=400,
            detail="data_dir must be provided as a query parameter or set in config.yaml",
        )
    path = Path(resolved)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"data_dir not found: {path}")
    return path


def get_rdvs(
    data_dir: Path = Depends(get_data_dir),
    config: dict = Depends(get_config),
) -> dict[str, "pd.DataFrame"]:
    """Load all available RDVs from data_dir."""
    n_max = config.get("n_max")
    return load_all_rdvs(data_dir, n_max=n_max)
