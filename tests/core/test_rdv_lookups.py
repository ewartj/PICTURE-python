"""Tests for RDV metadata lookups."""

from __future__ import annotations

import pytest

from core.rdv.lookups import (
    get_rdv_description,
    get_rdv_label,
    get_rdv_type,
    get_rdv_variables,
    get_variable_description,
    get_variable_filter_type,
    get_variable_input_type,
    get_variable_label,
    list_rdv_codes,
)


# ---------------------------------------------------------------------------
# RDV-level
# ---------------------------------------------------------------------------


def test_get_rdv_label_known():
    assert get_rdv_label("pde") == "demographics"


def test_get_rdv_label_unknown_returns_code():
    assert get_rdv_label("nonexistent_rdv") == "nonexistent_rdv"


def test_get_rdv_description_known():
    desc = get_rdv_description("pde")
    assert len(desc) > 0


def test_get_rdv_description_unknown_returns_empty():
    assert get_rdv_description("nonexistent_rdv") == ""


def test_get_rdv_type_known():
    assert get_rdv_type("pde") == "patient_demographics"


def test_list_rdv_codes_contains_known():
    codes = list_rdv_codes()
    assert "pde" in codes
    assert "dia_conditions" in codes
    assert "wst" in codes


def test_list_rdv_codes_nonempty():
    assert len(list_rdv_codes()) >= 10


# ---------------------------------------------------------------------------
# Variable-level
# ---------------------------------------------------------------------------


def test_get_variable_label_known():
    assert get_variable_label("pde", "sex_name") == "sex"


def test_get_variable_label_unknown_returns_code():
    assert get_variable_label("pde", "nonexistent_col") == "nonexistent_col"


def test_get_variable_description_known():
    desc = get_variable_description("pde", "sex_name")
    assert len(desc) > 0


def test_get_variable_filter_type_select_column():
    assert get_variable_filter_type("pde", "sex_name") == "str_matches"


def test_get_variable_filter_type_date_column():
    assert (
        get_variable_filter_type("dia_conditions", "start_datetime") == "date_between"
    )


def test_get_variable_filter_type_unknown_returns_none():
    assert get_variable_filter_type("pde", "nonexistent_col") is None


def test_get_variable_input_type_select():
    assert get_variable_input_type("pde", "sex_name") == "select"


def test_get_variable_input_type_text():
    assert get_variable_input_type("dia_conditions", "diag_name") == "text"


def test_get_variable_input_type_date_range():
    assert get_variable_input_type("dia_conditions", "start_datetime") == "date_range"


def test_get_variable_input_type_unknown_returns_none():
    assert get_variable_input_type("pde", "nonexistent_col") is None


# ---------------------------------------------------------------------------
# get_rdv_variables
# ---------------------------------------------------------------------------


def test_get_rdv_variables_returns_list():
    variables = get_rdv_variables("pde")
    assert isinstance(variables, list)
    assert len(variables) > 0


def test_get_rdv_variables_contain_expected_keys():
    variables = get_rdv_variables("pde")
    first = variables[0]
    assert "variable_code" in first
    assert "label" in first
    assert "input_type" in first
    assert "filter_type" in first


def test_get_rdv_variables_contains_sex_name():
    variables = get_rdv_variables("pde")
    codes = [v["variable_code"] for v in variables]
    assert "sex_name" in codes


def test_get_rdv_variables_unknown_rdv_returns_empty():
    assert get_rdv_variables("nonexistent_rdv") == []
