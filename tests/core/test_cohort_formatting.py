"""Tests for cohort specification formatting."""

from __future__ import annotations

import pytest

from core.cohort.formatting import describe_cohort, describe_cohort_short, describe_step
from core.cohort.models import CohortDefinition, CohortFilterStep


def _step(**kwargs) -> CohortFilterStep:
    defaults = dict(
        type="filter",
        rdv="pde",
        column="sex_name",
        val=["Female"],
        inclusion="ever",
        query_type="str_matches",
    )
    defaults.update(kwargs)
    return CohortFilterStep(**defaults)


# ---------------------------------------------------------------------------
# describe_step
# ---------------------------------------------------------------------------


def test_base_step_returns_all_patients():
    step = CohortFilterStep(type="base")
    assert describe_step(step) == "All patients in the dataset"


def test_str_matches_phrase():
    step = _step(val=["Female"])
    result = describe_step(step)
    assert "equal to" in result
    assert "Female" in result


def test_str_contains_phrase():
    step = _step(query_type="str_contains", val=["sepsis"])
    assert "containing" in describe_step(step)


def test_str_starts_phrase():
    step = _step(query_type="str_starts", val=["A"])
    assert "starting with" in describe_step(step)


def test_date_between_phrase():
    step = _step(
        rdv="dia",
        column="start_datetime",
        query_type="date_between",
        val=["2020-01-01", "2021-12-31"],
    )
    result = describe_step(step)
    assert "between dates" in result
    assert "2020-01-01" in result
    assert "2021-12-31" in result


def test_numeric_between_phrase():
    step = _step(
        rdv="wst", column="ward_stay_days", query_type="numeric_between", val=[5, 30]
    )
    result = describe_step(step)
    assert "between" in result
    assert "5" in result


def test_age_between_phrase():
    step = _step(query_type="age_between", val=[18, 65])
    assert "aged between" in describe_step(step)


def test_never_inclusion_phrase():
    step = _step(inclusion="never")
    assert "never had" in describe_step(step)


def test_fully_concurrent_phrase():
    step = _step(inclusion="fully_concurrent")
    assert "concurrent" in describe_step(step)


def test_window_offset_shown_when_nonzero():
    step = _step(window=[-7, 30])
    result = describe_step(step)
    assert "window" in result
    assert "-7" in result
    assert "+30" in result


def test_window_offset_hidden_when_zero():
    step = _step(window=[0, 0])
    assert "window" not in describe_step(step)


def test_unknown_rdv_falls_back_to_code():
    step = _step(rdv="xyz_unknown")
    result = describe_step(step)
    assert "xyz_unknown" in result


def test_multiple_values_comma_separated():
    step = _step(val=["A", "B", "C"])
    result = describe_step(step)
    assert "A" in result and "B" in result and "C" in result


def test_empty_val():
    step = _step(val=[])
    assert "no value" in describe_step(step)


# ---------------------------------------------------------------------------
# describe_cohort
# ---------------------------------------------------------------------------


def test_describe_cohort_includes_label():
    defn = CohortDefinition(
        label="Female",
        config=[
            CohortFilterStep(type="base"),
            _step(val=["Female"]),
        ],
    )
    result = describe_cohort(defn)
    assert result.startswith("Female")


def test_describe_cohort_tree_chars():
    defn = CohortDefinition(
        label="Female",
        config=[
            CohortFilterStep(type="base"),
            _step(val=["Female"]),
        ],
    )
    result = describe_cohort(defn)
    assert "├─" in result or "└─" in result


# ---------------------------------------------------------------------------
# describe_cohort_short
# ---------------------------------------------------------------------------


def test_describe_cohort_short_no_filters():
    defn = CohortDefinition(label="All", config=[CohortFilterStep(type="base")])
    assert describe_cohort_short(defn) == "All patients"


def test_describe_cohort_short_single_filter():
    defn = CohortDefinition(
        label="Female",
        config=[
            CohortFilterStep(type="base"),
            _step(val=["Female"]),
        ],
    )
    result = describe_cohort_short(defn)
    assert "Female" in result
    assert "\n" not in result  # one line
