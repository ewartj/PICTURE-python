"""Tests for the backend and db_url fields added to PlatformConfig.

Covers:
- Default values when neither config file nor env vars are set
- Reading backend and db_url from a YAML config file
- PICTURE_BACKEND env var overrides config file
- DATABASE_URL env var overrides config file
- Both env vars set together
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from core.config.platform_config import load_platform_config

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(content))
    return p


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


class TestDefaults:
    def test_backend_defaults_to_file(self, tmp_path):
        p = _write_config(tmp_path, "default:\n  data_dir: /data\n")
        cfg = load_platform_config(p)
        assert cfg.backend == "file"

    def test_db_url_defaults_to_none(self, tmp_path):
        p = _write_config(tmp_path, "default:\n  data_dir: /data\n")
        cfg = load_platform_config(p)
        assert cfg.db_url is None

    def test_defaults_with_empty_config(self, tmp_path):
        p = _write_config(tmp_path, "default: {}\n")
        cfg = load_platform_config(p)
        assert cfg.backend == "file"
        assert cfg.db_url is None


# ---------------------------------------------------------------------------
# Reading from config file
# ---------------------------------------------------------------------------


class TestFromConfigFile:
    def test_backend_postgres_from_yaml(self, tmp_path):
        p = _write_config(
            tmp_path,
            """
            default:
              backend: postgres
              db_url: postgresql://user:pass@localhost:5432/picture
            """,
        )
        cfg = load_platform_config(p)
        assert cfg.backend == "postgres"

    def test_db_url_from_yaml(self, tmp_path):
        p = _write_config(
            tmp_path,
            """
            default:
              backend: postgres
              db_url: postgresql://user:pass@localhost:5432/picture
            """,
        )
        cfg = load_platform_config(p)
        assert cfg.db_url == "postgresql://user:pass@localhost:5432/picture"

    def test_backend_file_explicit_in_yaml(self, tmp_path):
        p = _write_config(tmp_path, "default:\n  backend: file\n")
        cfg = load_platform_config(p)
        assert cfg.backend == "file"

    def test_db_url_null_in_yaml(self, tmp_path):
        p = _write_config(tmp_path, "default:\n  db_url: null\n")
        cfg = load_platform_config(p)
        assert cfg.db_url is None


# ---------------------------------------------------------------------------
# Environment variable overrides
# ---------------------------------------------------------------------------


class TestEnvVarOverrides:
    def test_picture_backend_overrides_yaml(self, tmp_path, monkeypatch):
        p = _write_config(tmp_path, "default:\n  backend: file\n")
        monkeypatch.setenv("PICTURE_BACKEND", "postgres")
        cfg = load_platform_config(p)
        assert cfg.backend == "postgres"

    def test_database_url_overrides_yaml(self, tmp_path, monkeypatch):
        p = _write_config(
            tmp_path,
            "default:\n  db_url: postgresql://old:old@localhost/old\n",
        )
        monkeypatch.setenv("DATABASE_URL", "postgresql://new:new@host/new")
        cfg = load_platform_config(p)
        assert cfg.db_url == "postgresql://new:new@host/new"

    def test_env_vars_win_over_yaml_for_both(self, tmp_path, monkeypatch):
        p = _write_config(
            tmp_path,
            """
            default:
              backend: file
              db_url: postgresql://old:old@localhost/old
            """,
        )
        monkeypatch.setenv("PICTURE_BACKEND", "postgres")
        monkeypatch.setenv("DATABASE_URL", "postgresql://new:new@host/new")
        cfg = load_platform_config(p)
        assert cfg.backend == "postgres"
        assert cfg.db_url == "postgresql://new:new@host/new"

    def test_env_var_does_not_bleed_between_tests(self, tmp_path):
        """monkeypatch cleanup: env var set in other tests must not be visible here."""
        p = _write_config(tmp_path, "default:\n  backend: file\n")
        cfg = load_platform_config(p)
        assert cfg.backend == "file"
