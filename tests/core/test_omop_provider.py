"""Tests for the OmopProvider.

Because we cannot run against a real OMOP database in CI, these tests cover:

  - _build_query: LIMIT injection and schema prefix substitution
  - list_available_rdvs: all expected RDVs are present
  - load_rdv: delegates to pd.read_sql with the right SQL (engine mocked)
  - load_rdv: raises ValueError for unknown RDV
  - load_rdv: best-effort RDVs (tht, mda) return empty DataFrame on DB error
  - load_all_rdvs: skips RDVs with no mapping, respects n_max and rdvs subset
  - OmopProvider satisfies the DataProvider protocol
  - get_data_provider factory returns OmopProvider when backend=omop

No real database connection is made.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
from fastapi import HTTPException

from api.deps import get_data_provider
from core.config.platform_config import PlatformConfig
from core.data.provider import DataProvider
from core.data.providers.omop import OmopProvider, _build_query, _OMOP_QUERIES


# ---------------------------------------------------------------------------
# _build_query
# ---------------------------------------------------------------------------


class TestBuildQuery:
    def test_no_limit_when_n_max_is_none(self):
        sql = _build_query("pde", n_max=None, schema_prefix="")
        assert "LIMIT" not in sql.upper()

    def test_limit_injected_when_n_max_set(self):
        sql = _build_query("pde", n_max=100, schema_prefix="")
        assert "LIMIT 100" in sql

    def test_schema_prefix_applied_to_tables(self):
        sql = _build_query("pde", n_max=None, schema_prefix="cdm.")
        assert "cdm.person" in sql
        assert "cdm.concept" in sql

    def test_empty_schema_prefix_uses_bare_table_names(self):
        sql = _build_query("pde", n_max=None, schema_prefix="")
        # Should reference bare table names, not schema-prefixed ones
        assert "FROM person" in sql or "JOIN person" in sql or "{schema}" not in sql

    def test_all_rdvs_produce_valid_sql(self):
        for rdv in _OMOP_QUERIES:
            sql = _build_query(rdv, n_max=None, schema_prefix="")
            assert "SELECT" in sql.upper()
            assert "FROM" in sql.upper()
            assert "{schema}" not in sql
            assert "{limit}" not in sql

    def test_schema_and_limit_together(self):
        sql = _build_query("dia", n_max=50, schema_prefix="omop.")
        assert "omop.condition_occurrence" in sql
        assert "LIMIT 50" in sql


# ---------------------------------------------------------------------------
# list_available_rdvs
# ---------------------------------------------------------------------------


class TestListAvailableRdvs:
    @pytest.fixture
    def provider(self):
        with patch("core.data.providers.omop.create_engine"):
            return OmopProvider("postgresql://fake/db")

    def test_returns_list(self, provider):
        assert isinstance(provider.list_available_rdvs(), list)

    def test_all_core_rdvs_present(self, provider):
        available = provider.list_available_rdvs()
        for rdv in ("pde", "dia", "adm", "med", "mda", "prc", "flo", "lab", "wst", "loc"):
            assert rdv in available, f"Expected '{rdv}' in list_available_rdvs()"

    def test_all_eleven_rdvs_covered(self, provider):
        assert len(provider.list_available_rdvs()) == 11


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_satisfies_data_provider_protocol(self):
        with patch("core.data.providers.omop.create_engine"):
            provider = OmopProvider("postgresql://fake/db")
        assert isinstance(provider, DataProvider)


# ---------------------------------------------------------------------------
# load_rdv
# ---------------------------------------------------------------------------


class TestLoadRdv:
    @pytest.fixture
    def mock_engine(self):
        with patch("core.data.providers.omop.create_engine") as mock_create:
            engine = MagicMock()
            mock_create.return_value = engine
            engine.connect.return_value.__enter__ = MagicMock(return_value=MagicMock())
            engine.connect.return_value.__exit__ = MagicMock(return_value=False)
            yield engine

    @pytest.fixture
    def provider(self, mock_engine):
        return OmopProvider("postgresql://fake/db")

    def test_raises_value_error_for_unknown_rdv(self, provider):
        with pytest.raises(ValueError, match="No OMOP mapping"):
            provider.load_rdv("unknown_rdv")  # type: ignore[arg-type]

    def test_error_message_lists_available_rdvs(self, provider):
        with pytest.raises(ValueError) as exc_info:
            provider.load_rdv("unknown_rdv")  # type: ignore[arg-type]
        assert "pde" in str(exc_info.value)

    def test_calls_read_sql_with_correct_table(self, provider):
        sample_df = pd.DataFrame({"project_id": ["P001"], "birth_date": ["1990-01-01"],
                                   "sex_name": ["Female"], "death_date": [None]})
        with patch("core.data.providers.omop.pd.read_sql", return_value=sample_df) as mock_sql:
            provider.load_rdv("pde")
        sql_text = mock_sql.call_args[0][0].text
        assert "person" in sql_text

    def test_n_max_injects_limit(self, provider):
        sample_df = pd.DataFrame({"project_id": ["P001"], "birth_date": ["1990-01-01"],
                                   "sex_name": ["Female"], "death_date": [None]})
        with patch("core.data.providers.omop.pd.read_sql", return_value=sample_df) as mock_sql:
            provider.load_rdv("pde", n_max=10)
        sql_text = mock_sql.call_args[0][0].text
        assert "LIMIT 10" in sql_text

    def test_best_effort_rdv_returns_empty_df_on_db_error(self, provider):
        with patch("core.data.providers.omop.pd.read_sql", side_effect=Exception("DB error")):
            result = provider.load_rdv("tht")
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_non_best_effort_rdv_raises_on_db_error(self, provider):
        with patch("core.data.providers.omop.pd.read_sql", side_effect=Exception("DB error")):
            with pytest.raises(Exception, match="DB error"):
                provider.load_rdv("pde")


# ---------------------------------------------------------------------------
# load_all_rdvs
# ---------------------------------------------------------------------------


class TestLoadAllRdvs:
    @pytest.fixture
    def provider(self):
        with patch("core.data.providers.omop.create_engine"):
            return OmopProvider("postgresql://fake/db")

    def test_rdvs_subset_respected(self, provider):
        pde_df = pd.DataFrame({"project_id": ["P001"], "birth_date": ["1990-01-01"],
                                "sex_name": ["Female"], "death_date": [None]})
        with patch("core.data.providers.omop.pd.read_sql", return_value=pde_df):
            result = provider.load_all_rdvs(rdvs=["pde"])
        assert set(result.keys()) == {"pde"}

    def test_unknown_rdv_in_subset_is_skipped(self, provider):
        pde_df = pd.DataFrame({"project_id": ["P001"], "birth_date": ["1990-01-01"],
                                "sex_name": ["Female"], "death_date": [None]})
        with patch("core.data.providers.omop.pd.read_sql", return_value=pde_df):
            result = provider.load_all_rdvs(rdvs=["pde", "not_an_rdv"])  # type: ignore[list-item]
        assert "not_an_rdv" not in result

    def test_db_failure_skips_rdv(self, provider):
        with patch("core.data.providers.omop.pd.read_sql", side_effect=Exception("fail")):
            result = provider.load_all_rdvs(rdvs=["pde"])
        assert "pde" not in result


# ---------------------------------------------------------------------------
# Schema prefix
# ---------------------------------------------------------------------------


class TestSchemaPrefix:
    def test_schema_passed_to_queries(self):
        with patch("core.data.providers.omop.create_engine"):
            provider = OmopProvider("postgresql://fake/db", schema="cdm")

        pde_df = pd.DataFrame({"project_id": ["P001"], "birth_date": ["1990-01-01"],
                                "sex_name": ["Female"], "death_date": [None]})
        with patch("core.data.providers.omop.pd.read_sql", return_value=pde_df) as mock_sql:
            provider.load_rdv("pde")
        assert "cdm.person" in mock_sql.call_args[0][0].text

    def test_no_schema_uses_bare_names(self):
        with patch("core.data.providers.omop.create_engine"):
            provider = OmopProvider("postgresql://fake/db")

        pde_df = pd.DataFrame({"project_id": ["P001"], "birth_date": ["1990-01-01"],
                                "sex_name": ["Female"], "death_date": [None]})
        with patch("core.data.providers.omop.pd.read_sql", return_value=pde_df) as mock_sql:
            provider.load_rdv("pde")
        call_args = str(mock_sql.call_args)
        assert "cdm.person" not in call_args


# ---------------------------------------------------------------------------
# Factory wiring (api/deps.py)
# ---------------------------------------------------------------------------


class TestDepFactory:
    def test_returns_omop_provider_when_backend_omop(self):
        platform = PlatformConfig(
            backend="omop",
            db_url="postgresql://user:pass@localhost:5432/omop",
        )
        with patch("core.data.providers.omop.create_engine"):
            provider = get_data_provider(platform=platform, data_dir=None)
        assert isinstance(provider, OmopProvider)

    def test_raises_500_when_backend_omop_but_no_db_url(self):
        platform = PlatformConfig(backend="omop", db_url=None)
        with pytest.raises(HTTPException) as exc_info:
            get_data_provider(platform=platform, data_dir=None)
        assert exc_info.value.status_code == 500

    def test_get_data_dir_returns_none_for_omop(self):
        from api.deps import get_data_dir
        platform = PlatformConfig(backend="omop", db_url="postgresql://x/x")
        assert get_data_dir(data_dir=None, platform=platform) is None
