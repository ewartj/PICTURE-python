"""Platform config parser.

Parses ``config/config.yaml`` into a :class:`PlatformConfig` dataclass and
resolves the ``app_yaml`` field to a concrete list of file paths.

The config file supports a ``default`` top-level key (matching R's
``config::get()`` convention) plus optional ``api`` and ``ui`` sections::

    default:
      data_dir: /data/study01
      app_yaml: "*"          # "*" = all YAMLs in data_dir; or a path/glob
      external_data_dir: null
      n_max: null
      infrastructure: local  # local | cloud

    api:
      host: "0.0.0.0"
      port: 8000
      reload: true

    ui:
      host: "0.0.0.0"
      port: 8501

Environment variable overrides (all optional):
    PICTURE_DATA_DIR        → default.data_dir
    PICTURE_APP_YAML        → default.app_yaml
    PICTURE_INFRASTRUCTURE  → default.infrastructure
    PICTURE_N_MAX           → default.n_max

Replaces: picture.platform R/app_picture.R  ``.load_config_yaml()``
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


# Default config file shipped with the package
_DEFAULT_CONFIG_PATH = Path(__file__).parent.parent.parent / "config" / "config.yaml"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class PlatformConfig:
    """Parsed platform configuration.

    Attributes:
        data_dir:          Path to the folder containing RDV files.
        app_yaml_paths:    Resolved list of app YAML file paths.
        external_data_dir: Optional path for external data (e.g. shapefiles).
        n_max:             Maximum rows to load per RDV (None = unlimited).
        infrastructure:    ``"local"`` or ``"cloud"``.
        api_host:          FastAPI host.
        api_port:          FastAPI port.
        api_reload:        Enable uvicorn auto-reload.
        ui_host:           Streamlit/React host.
        ui_port:           Streamlit/React port.
    """

    data_dir: Optional[Path] = None
    app_dir: Optional[Path] = None
    app_yaml_paths: list[Path] = field(default_factory=list)
    external_data_dir: Optional[Path] = None
    n_max: Optional[int] = None
    infrastructure: str = "local"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True
    ui_host: str = "0.0.0.0"
    ui_port: int = 8501


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _resolve_app_yaml(
    raw: Optional[str],
    data_dir: Optional[Path],
) -> list[Path]:
    """Resolve the ``app_yaml`` config value to a concrete list of paths.

    Resolution rules (mirroring R's ``apps_lookup()``):

    * ``None`` or ``""``  → empty list (no app YAMLs configured)
    * ``"*"``             → all ``*.yaml`` files in *data_dir* (if set),
                            falling back to the built-in ``config/apps/``
                            directory next to this file
    * A path ending with ``/*``  → all ``*.yaml`` files under that directory
    * A path to an existing file → ``[path]``
    * Anything else              → treated as a glob pattern
    """
    if not raw:
        return []

    raw = str(raw).strip()

    if raw == "*":
        # All YAMLs in data_dir, or built-in apps directory
        search_dir = data_dir or (_DEFAULT_CONFIG_PATH.parent / "apps")
        if search_dir and search_dir.is_dir():
            return sorted(search_dir.glob("*.yaml"))
        return []

    if raw.endswith("/*"):
        directory = Path(raw[:-2])
        if directory.is_dir():
            return sorted(directory.glob("*.yaml"))
        return []

    candidate = Path(raw)
    if candidate.exists():
        return [candidate]

    # Try as a glob
    parent = candidate.parent
    if parent.is_dir():
        return sorted(parent.glob(candidate.name))

    return []


def _to_path_or_none(value: Optional[str]) -> Optional[Path]:
    if not value:
        return None
    p = Path(value)
    return p


def _to_int_or_none(value) -> Optional[int]:
    if value is None:
        return None
    try:
        f = float(value)
        if math.isinf(f):
            return None  # R's Inf means no limit
        return int(f)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_platform_config(path: Optional[Path] = None) -> PlatformConfig:
    """Load the platform ``config.yaml`` and return a :class:`PlatformConfig`.

    Args:
        path: Path to the config YAML.  Defaults to
              ``config/config.yaml`` at the project root.

    Returns:
        Parsed :class:`PlatformConfig` with environment variable overrides
        applied.
    """
    config_path = Path(path) if path else _DEFAULT_CONFIG_PATH

    raw: dict = {}
    if config_path.exists():
        with config_path.open() as f:
            raw = yaml.safe_load(f) or {}

    default = raw.get("default", {}) or {}
    api_cfg = raw.get("api", {}) or {}
    ui_cfg = raw.get("ui", {}) or {}

    # Environment variable overrides
    data_dir_str = os.environ.get("PICTURE_DATA_DIR") or default.get("data_dir")
    app_dir_str = os.environ.get("PICTURE_APP_DIR") or default.get("app_dir")
    app_yaml_str = os.environ.get("PICTURE_APP_YAML") or default.get("app_yaml") or "*"
    infrastructure = os.environ.get("PICTURE_INFRASTRUCTURE") or default.get(
        "infrastructure", "local"
    )
    n_max_raw = os.environ.get("PICTURE_N_MAX") or default.get("n_max")

    data_dir = _to_path_or_none(data_dir_str)
    app_dir = _to_path_or_none(app_dir_str)
    n_max = _to_int_or_none(n_max_raw)

    # Resolve app YAMLs from app_dir (not data_dir)
    app_yaml_paths = _resolve_app_yaml(app_yaml_str, app_dir)

    return PlatformConfig(
        data_dir=data_dir,
        app_dir=app_dir,
        app_yaml_paths=app_yaml_paths,
        external_data_dir=_to_path_or_none(default.get("external_data_dir")),
        n_max=n_max,
        infrastructure=str(infrastructure),
        api_host=str(api_cfg.get("host", "0.0.0.0")),
        api_port=int(api_cfg.get("port", 8000)),
        api_reload=bool(api_cfg.get("reload", True)),
        ui_host=str(ui_cfg.get("host", "0.0.0.0")),
        ui_port=int(ui_cfg.get("port", 8501)),
    )
