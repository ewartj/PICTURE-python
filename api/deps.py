"""
FastAPI dependency injection.

Shared dependencies (config, cached DataFrames, app configs) are defined here
and injected into route handlers via FastAPI's Depends() mechanism.

This keeps route handlers thin and makes the data layer easy to swap
(e.g. replace file-based loading with a database in future).
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path

import pandas as pd
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, Query

from core.config.app_config import AppConfig, load_app_configs
from core.config.platform_config import PlatformConfig, load_platform_config
from core.data.loader import load_all_rdvs

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.yaml"


# ---------------------------------------------------------------------------
# Platform config
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def get_platform_config() -> PlatformConfig:
    """Load and cache the platform config.yaml."""
    return load_platform_config(_CONFIG_PATH)


# Keep a thin shim so existing code that calls get_config() still works.
def get_config() -> dict:
    cfg = get_platform_config()
    return {
        "data_dir": str(cfg.data_dir) if cfg.data_dir else None,
        "n_max": cfg.n_max,
        "infrastructure": cfg.infrastructure,
        "external_data_dir": str(cfg.external_data_dir)
        if cfg.external_data_dir
        else None,
    }


# ---------------------------------------------------------------------------
# App configs
# ---------------------------------------------------------------------------


@functools.lru_cache(maxsize=1)
def _load_app_configs_cached(config_path: Path) -> tuple[AppConfig, ...]:
    """Load app configs once and cache them (tuple is hashable)."""
    platform = load_platform_config(config_path)
    if not platform.app_yaml_paths:
        return ()
    return tuple(load_app_configs(platform.app_yaml_paths))


def get_app_configs(
    platform: PlatformConfig = Depends(get_platform_config),
) -> list[AppConfig]:
    """Return all loaded app configs.

    Results are cached after the first load.  The cache is keyed on the
    platform config path, so restarting the server (which clears the LRU
    cache) will reload from disk.
    """
    return list(_load_app_configs_cached(_CONFIG_PATH))


# ---------------------------------------------------------------------------
# Data loading dependencies
# ---------------------------------------------------------------------------


def get_data_dir(
    data_dir: Annotated[
        Optional[str], Query(description="Override data directory")
    ] = None,
    platform: PlatformConfig = Depends(get_platform_config),
) -> Path:
    """Resolve the data directory from query param or platform config."""
    resolved = data_dir or (str(platform.data_dir) if platform.data_dir else None)
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
    platform: PlatformConfig = Depends(get_platform_config),
) -> dict[str, "pd.DataFrame"]:
    """Load all available RDVs from data_dir."""
    return load_all_rdvs(data_dir, n_max=platform.n_max)
