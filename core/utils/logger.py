"""
System and environment information utilities.

Mirrors picture.platform R/utils_logger.R.

Usage::

    from core.utils.logger import get_system_info, get_packages_info

    info = get_system_info()
    # {'python_version': '3.11.8', 'platform': 'Linux-6.x ...', 'os': 'linux'}
"""

from __future__ import annotations

import os
import platform
import sys


def get_system_info() -> dict:
    """Return Python version and OS information.

    Mirrors R ``get_system_info()``.
    """
    return {
        "python_version": sys.version,
        "platform": platform.platform(),
        "os": sys.platform,
        "processor": platform.processor() or "unknown",
        "hostname": platform.node(),
    }


def get_env_info() -> dict[str, str]:
    """Return all current environment variables.

    Mirrors R ``get_env_info()``.
    """
    return dict(os.environ)


def get_packages_info() -> list[dict]:
    """Return installed Python packages with name and version.

    Mirrors R ``get_packages_info()``.
    """
    try:
        from importlib.metadata import packages_distributions, version

        pkgs = []
        seen: set[str] = set()
        for dist_name in packages_distributions().values():
            for name in dist_name:
                if name not in seen:
                    seen.add(name)
                    try:
                        pkgs.append({"package": name, "version": version(name)})
                    except Exception:
                        pass
        return sorted(pkgs, key=lambda p: p["package"].lower())
    except Exception:
        return []
