"""Tests for the column rename and normalisation logic in scripts/load_to_postgres.py.

Covers:
- Per-RDV renames: drug_name → medication_name (med, mda)
- Per-RDV renames: type → flowsheet_measure_name (flo)
- Per-RDV renames: Value/ResultStatus/abnormal (lab)
- Per-RDV renames: disharge_disposition typo fix (adm)
- Per-RDV renames: LSOA Code / MSOA Code with spaces (loc)
- General normalisation: CamelCase → snake_case
- General normalisation: spaces → underscores
- Tables with no renames pass through unchanged (pde, dia, etc.)
- _camel_to_snake helper
"""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.load_to_postgres import _apply_renames, _camel_to_snake, _normalise_columns

# ---------------------------------------------------------------------------
# _camel_to_snake
# ---------------------------------------------------------------------------


class TestCamelToSnake:
    def test_simple_camel(self):
        assert _camel_to_snake("CamelCase") == "camel_case"

    def test_already_snake(self):
        assert _camel_to_snake("already_snake") == "already_snake"

    def test_acronym(self):
        assert _camel_to_snake("LabTestKey") == "lab_test_key"

    def test_consecutive_uppercase(self):
        assert _camel_to_snake("ResultStatus") == "result_status"

    def test_lowercase_passthrough(self):
        assert _camel_to_snake("project_id") == "project_id"


# ---------------------------------------------------------------------------
# _normalise_columns
# ---------------------------------------------------------------------------


class TestNormaliseColumns:
    def test_lowercases_columns(self):
        df = pd.DataFrame(columns=["ProjectID", "StartDatetime"])
        df = _normalise_columns(df)
        assert list(df.columns) == ["project_id", "start_datetime"]

    def test_spaces_to_underscores(self):
        df = pd.DataFrame(columns=["LSOA Code", "MSOA Code"])
        df = _normalise_columns(df)
        assert "lsoa_code" in df.columns
        assert "msoa_code" in df.columns

    def test_already_normalised_unchanged(self):
        df = pd.DataFrame(columns=["project_id", "start_datetime"])
        df = _normalise_columns(df)
        assert list(df.columns) == ["project_id", "start_datetime"]


# ---------------------------------------------------------------------------
# _apply_renames — med
# ---------------------------------------------------------------------------


class TestMedRenames:
    def _make_df(self):
        return pd.DataFrame(
            columns=[
                "project_id",
                "start_datetime",
                "end_datetime",
                "MedicationOrderKey",
                "drug_name",
                "drug_code",
            ]
        )

    def test_drug_name_renamed_to_medication_name(self):
        df = _apply_renames("med", self._make_df())
        assert "medication_name" in df.columns
        assert "drug_name" not in df.columns

    def test_medication_order_key_normalised(self):
        df = _apply_renames("med", self._make_df())
        assert "medication_order_key" in df.columns
        assert "MedicationOrderKey" not in df.columns

    def test_other_columns_preserved(self):
        df = _apply_renames("med", self._make_df())
        assert "project_id" in df.columns
        assert "drug_code" in df.columns


# ---------------------------------------------------------------------------
# _apply_renames — mda
# ---------------------------------------------------------------------------


class TestMdaRenames:
    def _make_df(self):
        return pd.DataFrame(
            columns=[
                "project_id",
                "start_datetime",
                "MedicationOrderKey",
                "drug_name",
            ]
        )

    def test_drug_name_renamed_to_medication_name(self):
        df = _apply_renames("mda", self._make_df())
        assert "medication_name" in df.columns
        assert "drug_name" not in df.columns

    def test_medication_order_key_normalised(self):
        df = _apply_renames("mda", self._make_df())
        assert "medication_order_key" in df.columns


# ---------------------------------------------------------------------------
# _apply_renames — flo
# ---------------------------------------------------------------------------


class TestFloRenames:
    def _make_df(self):
        return pd.DataFrame(columns=["project_id", "start_datetime", "type", "value"])

    def test_type_renamed_to_flowsheet_measure_name(self):
        df = _apply_renames("flo", self._make_df())
        assert "flowsheet_measure_name" in df.columns
        assert "type" not in df.columns

    def test_other_columns_preserved(self):
        df = _apply_renames("flo", self._make_df())
        assert "value" in df.columns


# ---------------------------------------------------------------------------
# _apply_renames — lab
# ---------------------------------------------------------------------------


class TestLabRenames:
    def _make_df(self):
        return pd.DataFrame(
            columns=[
                "project_id",
                "LabTestKey",
                "start_datetime",
                "Value",
                "Unit",
                "NumericValue",
                "ResultStatus",
                "abnormal",
                "component_name",
                "SpecimenType",
            ]
        )

    def test_value_renamed_to_result_value(self):
        df = _apply_renames("lab", self._make_df())
        assert "result_value" in df.columns
        assert "Value" not in df.columns

    def test_result_status_normalised(self):
        df = _apply_renames("lab", self._make_df())
        assert "result_status" in df.columns
        assert "ResultStatus" not in df.columns

    def test_abnormal_renamed_to_abnormal_flag(self):
        df = _apply_renames("lab", self._make_df())
        assert "abnormal_flag" in df.columns
        assert "abnormal" not in df.columns

    def test_lab_test_key_normalised(self):
        df = _apply_renames("lab", self._make_df())
        assert "lab_test_key" in df.columns
        assert "LabTestKey" not in df.columns

    def test_numeric_value_normalised(self):
        df = _apply_renames("lab", self._make_df())
        assert "numeric_value" in df.columns
        assert "NumericValue" not in df.columns

    def test_specimen_type_normalised(self):
        df = _apply_renames("lab", self._make_df())
        assert "specimen_type" in df.columns

    def test_component_name_preserved(self):
        df = _apply_renames("lab", self._make_df())
        assert "component_name" in df.columns


# ---------------------------------------------------------------------------
# _apply_renames — adm (typo fix)
# ---------------------------------------------------------------------------


class TestAdmRenames:
    def _make_df(self):
        return pd.DataFrame(
            columns=[
                "project_id",
                "start_datetime",
                "disharge_disposition",
            ]
        )

    def test_typo_fixed(self):
        df = _apply_renames("adm", self._make_df())
        assert "discharge_disposition" in df.columns
        assert "disharge_disposition" not in df.columns


# ---------------------------------------------------------------------------
# _apply_renames — loc (columns with spaces)
# ---------------------------------------------------------------------------


class TestLocRenames:
    def _make_df(self):
        return pd.DataFrame(
            columns=[
                "project_id",
                "LSOA Code",
                "MSOA Code",
                "District",
                "County",
            ]
        )

    def test_lsoa_code_normalised(self):
        df = _apply_renames("loc", self._make_df())
        assert "lsoa_code" in df.columns
        assert "LSOA Code" not in df.columns

    def test_msoa_code_normalised(self):
        df = _apply_renames("loc", self._make_df())
        assert "msoa_code" in df.columns
        assert "MSOA Code" not in df.columns

    def test_district_lowercased(self):
        df = _apply_renames("loc", self._make_df())
        assert "district" in df.columns

    def test_county_lowercased(self):
        df = _apply_renames("loc", self._make_df())
        assert "county" in df.columns


# ---------------------------------------------------------------------------
# Tables with no special renames pass through with only normalisation
# ---------------------------------------------------------------------------


class TestNoRenamesTables:
    @pytest.mark.parametrize("rdv", ["pde", "dia", "prc", "wst", "tht"])
    def test_project_id_always_preserved(self, rdv):
        df = pd.DataFrame(columns=["project_id", "start_datetime"])
        df = _apply_renames(rdv, df)
        assert "project_id" in df.columns

    def test_pde_columns_unchanged(self):
        df = pd.DataFrame(columns=["project_id", "sex_name", "birth_date"])
        df = _apply_renames("pde", df)
        assert list(df.columns) == ["project_id", "sex_name", "birth_date"]
