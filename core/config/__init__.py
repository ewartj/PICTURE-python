"""PICTURE configuration layer.

Two config files drive the system:

1. ``config/config.yaml``  — platform config (data_dir, infrastructure, etc.)
   Parsed by :mod:`core.config.platform_config`.

2. One or more *app YAML* files  — define cohorts + analysis tabs for a study.
   Parsed by :mod:`core.config.app_config`.
"""

from core.config.app_config import (
    AnalysisMethod,
    AnalysisTab,
    AppConfig,
    OutputConfig,
    load_app_config,
    load_app_configs,
)
from core.config.platform_config import PlatformConfig, load_platform_config

__all__ = [
    "AnalysisMethod",
    "AnalysisTab",
    "AppConfig",
    "OutputConfig",
    "load_app_config",
    "load_app_configs",
    "PlatformConfig",
    "load_platform_config",
]
