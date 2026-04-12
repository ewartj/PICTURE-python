"""Tests for the DataProvider protocol and FileProvider implementation.

Covers:
- FileProvider satisfies the DataProvider protocol (runtime check)
- list_available_rdvs() returns only RDVs that have a file present
- load_rdv() raises FileNotFoundError for a missing file
- load_all_rdvs() silently skips missing RDVs and returns found ones
- load_all_rdvs() respects the rdvs subset argument
- load_all_rdvs() respects n_max

PostgresProvider is not tested here (requires a live database).
Connection-string validation and error handling are covered in test_deps_provider.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from core.data.provider import DataProvider
from core.data.providers.file import FileProvider

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def data_dir(tmp_path) -> Path:
    """Minimal data directory with a pde CSV and a dia CSV."""
    pde = pd.DataFrame(
        {
            "project_id": ["P001", "P002"],
            "birth_date": ["1990-01-01", "1985-06-15"],
            "sex_name": ["Female", "Male"],
            "death_date": [None, None],
        }
    )
    dia = pd.DataFrame(
        {
            "project_id": ["P001", "P002"],
            "diag_name": ["Asthma", "COPD"],
            "start_datetime": ["2020-01-01", "2020-03-01"],
            "end_datetime": ["2020-06-01", "2020-09-01"],
        }
    )
    pde.to_csv(tmp_path / "dmv_caboodle_patient_demographics.csv", index=False)
    dia.to_csv(tmp_path / "dmv_caboodle_patient_diagnoses.csv", index=False)
    return tmp_path


@pytest.fixture
def provider(data_dir) -> FileProvider:
    return FileProvider(data_dir)


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_file_provider_satisfies_data_provider_protocol(self, provider):
        assert isinstance(provider, DataProvider)

    def test_has_load_rdv(self, provider):
        assert callable(getattr(provider, "load_rdv", None))

    def test_has_load_all_rdvs(self, provider):
        assert callable(getattr(provider, "load_all_rdvs", None))

    def test_has_list_available_rdvs(self, provider):
        assert callable(getattr(provider, "list_available_rdvs", None))


# ---------------------------------------------------------------------------
# list_available_rdvs
# ---------------------------------------------------------------------------


class TestListAvailableRdvs:
    def test_returns_only_present_rdvs(self, provider):
        available = provider.list_available_rdvs()
        assert set(available) == {"pde", "dia"}

    def test_returns_list(self, provider):
        assert isinstance(provider.list_available_rdvs(), list)

    def test_empty_dir_returns_empty(self, tmp_path):
        assert FileProvider(tmp_path).list_available_rdvs() == []

    def test_does_not_include_missing_rdv(self, provider):
        assert "med" not in provider.list_available_rdvs()


# ---------------------------------------------------------------------------
# load_rdv
# ---------------------------------------------------------------------------


class TestLoadRdv:
    def test_returns_dataframe(self, provider):
        df = provider.load_rdv("pde")
        assert isinstance(df, pd.DataFrame)

    def test_correct_row_count(self, provider):
        df = provider.load_rdv("pde")
        assert len(df) == 2

    def test_required_columns_present(self, provider):
        df = provider.load_rdv("pde")
        assert "project_id" in df.columns
        assert "sex_name" in df.columns

    def test_n_max_limits_rows(self, provider):
        df = provider.load_rdv("pde", n_max=1)
        assert len(df) == 1

    def test_missing_rdv_raises_file_not_found(self, provider):
        with pytest.raises(FileNotFoundError):
            provider.load_rdv("med")


# ---------------------------------------------------------------------------
# load_all_rdvs
# ---------------------------------------------------------------------------


class TestLoadAllRdvs:
    def test_returns_dict(self, provider):
        result = provider.load_all_rdvs()
        assert isinstance(result, dict)

    def test_returns_available_rdvs_only(self, provider):
        result = provider.load_all_rdvs()
        assert set(result.keys()) == {"pde", "dia"}

    def test_skips_missing_rdvs_silently(self, provider):
        # med is not present — should not raise, just be absent
        result = provider.load_all_rdvs(rdvs=["pde", "med"])
        assert "pde" in result
        assert "med" not in result

    def test_rdvs_subset_respected(self, provider):
        result = provider.load_all_rdvs(rdvs=["pde"])
        assert set(result.keys()) == {"pde"}

    def test_n_max_applied_to_all_tables(self, provider):
        result = provider.load_all_rdvs(n_max=1)
        for df in result.values():
            assert len(df) == 1

    def test_values_are_dataframes(self, provider):
        result = provider.load_all_rdvs()
        for df in result.values():
            assert isinstance(df, pd.DataFrame)
