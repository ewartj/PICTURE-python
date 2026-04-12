"""Tests for the DataProvider factory in api/deps.py.

Covers:
- get_data_provider returns FileProvider when backend=file
- get_data_provider returns PostgresProvider when backend=postgres + db_url set
- get_data_provider raises HTTPException when backend=postgres but db_url missing
- get_data_dir returns None when backend=postgres (data_dir not required)
- get_data_dir raises HTTPException when backend=file and path does not exist
- get_data_dir resolves correctly from platform config
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from api.deps import get_data_dir, get_data_provider
from core.config.platform_config import PlatformConfig
from core.data.providers.file import FileProvider
from core.data.providers.postgres import PostgresProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _platform(
    backend: str = "file",
    data_dir: str | None = None,
    db_url: str | None = None,
) -> PlatformConfig:
    return PlatformConfig(
        backend=backend,
        data_dir=Path(data_dir) if data_dir else None,
        db_url=db_url,
    )


# ---------------------------------------------------------------------------
# get_data_dir
# ---------------------------------------------------------------------------


class TestGetDataDir:
    def test_returns_none_when_backend_is_postgres(self):
        platform = _platform(backend="postgres", db_url="postgresql://x:x@localhost/x")
        result = get_data_dir(data_dir=None, platform=platform)
        assert result is None

    def test_returns_path_when_dir_exists(self, tmp_path):
        platform = _platform(backend="file", data_dir=str(tmp_path))
        result = get_data_dir(data_dir=None, platform=platform)
        assert result == tmp_path

    def test_query_param_overrides_platform_config(self, tmp_path):
        platform = _platform(backend="file", data_dir="/some/other/path")
        result = get_data_dir(data_dir=str(tmp_path), platform=platform)
        assert result == tmp_path

    def test_raises_404_when_path_does_not_exist(self, tmp_path):
        missing = str(tmp_path / "nonexistent")
        platform = _platform(backend="file", data_dir=missing)
        with pytest.raises(HTTPException) as exc_info:
            get_data_dir(data_dir=None, platform=platform)
        assert exc_info.value.status_code == 404

    def test_raises_400_when_no_data_dir_and_backend_file(self):
        platform = _platform(backend="file", data_dir=None)
        with pytest.raises(HTTPException) as exc_info:
            get_data_dir(data_dir=None, platform=platform)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# get_data_provider — file backend
# ---------------------------------------------------------------------------


class TestGetDataProviderFile:
    def test_returns_file_provider(self, tmp_path):
        platform = _platform(backend="file")
        provider = get_data_provider(platform=platform, data_dir=tmp_path)
        assert isinstance(provider, FileProvider)

    def test_raises_500_when_data_dir_is_none_for_file_backend(self):
        platform = _platform(backend="file")
        with pytest.raises(HTTPException) as exc_info:
            get_data_provider(platform=platform, data_dir=None)
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# get_data_provider — postgres backend
# ---------------------------------------------------------------------------


class TestGetDataProviderPostgres:
    def test_returns_postgres_provider(self):
        platform = _platform(
            backend="postgres",
            db_url="postgresql://user:pass@localhost:5432/picture",
        )
        provider = get_data_provider(platform=platform, data_dir=None)
        assert isinstance(provider, PostgresProvider)

    def test_raises_500_when_db_url_missing(self):
        platform = _platform(backend="postgres", db_url=None)
        with pytest.raises(HTTPException) as exc_info:
            get_data_provider(platform=platform, data_dir=None)
        assert exc_info.value.status_code == 500

    def test_error_message_mentions_db_url(self):
        platform = _platform(backend="postgres", db_url=None)
        with pytest.raises(HTTPException) as exc_info:
            get_data_provider(platform=platform, data_dir=None)
        assert "db_url" in exc_info.value.detail
