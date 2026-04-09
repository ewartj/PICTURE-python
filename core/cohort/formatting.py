"""
Cohort specification formatting.

Mirrors picture.platform R/utils_cohort_formatting.R.

Converts structured CohortFilterStep objects into human-readable sentences
for display in the UI and in reports.

Usage::

    from core.cohort.formatting import describe_step, describe_cohort

    describe_step(step)           # "had demographics sex equal to Female"
    describe_cohort(definition)   # multi-line description of all steps
"""

from __future__ import annotations

from core.cohort.models import CohortDefinition, CohortFilterStep
from core.rdv.lookups import get_rdv_label, get_variable_label

_INCLUSION_PHRASES: dict[str, str] = {
    "ever": "had",
    "never": "never had",
    "fully_concurrent": "had (concurrent)",
    "after_first": "had (after first occurrence of)",
    "on_first": "had (at first occurrence of)",
}

_QUERY_PHRASES: dict[str, str] = {
    "str_matches": "equal to",
    "str_contains": "containing",
    "str_starts": "starting with",
    "date_between": "between dates",
    "numeric_between": "between",
    "age_between": "aged between",
}


def describe_step(step: CohortFilterStep) -> str:
    """Return a single human-readable sentence describing a filter step.

    Example::

        "had demographics sex equal to ['Female']"
    """
    if step.type == "base":
        return "All patients in the dataset"

    inclusion = _INCLUSION_PHRASES.get(step.inclusion, step.inclusion)
    rdv_label = get_rdv_label(step.rdv) if step.rdv else step.rdv or "?"
    var_label = (
        get_variable_label(step.rdv, step.column)
        if step.rdv and step.column
        else step.column or "?"
    )
    query = _QUERY_PHRASES.get(step.query_type, step.query_type)

    val = step.val or []
    if len(val) == 0:
        val_str = "(no value)"
    elif len(val) == 1:
        val_str = str(val[0])
    elif len(val) == 2 and step.query_type in (
        "date_between",
        "numeric_between",
        "age_between",
    ):
        val_str = f"{val[0]} – {val[1]}"
    else:
        val_str = ", ".join(str(v) for v in val)

    window_str = ""
    if step.window and step.window != [0, 0]:
        w0, w1 = step.window
        window_str = f" (window: {w0:+d} to {w1:+d} days)"

    return f"{inclusion} {rdv_label} {var_label} {query} {val_str}{window_str}"


def describe_cohort(definition: CohortDefinition) -> str:
    """Return a multi-line plain-text description of a full cohort definition.

    Suitable for reports and tooltips.

    Example::

        Female
        ├─ All patients in the dataset
        └─ had demographics sex equal to Female
    """
    lines = [definition.label]
    steps = [s for s in definition.config if s.type != "base"]
    base = [s for s in definition.config if s.type == "base"]

    all_steps = base + steps
    for i, step in enumerate(all_steps):
        prefix = "└─" if i == len(all_steps) - 1 else "├─"
        lines.append(f"  {prefix} {describe_step(step)}")

    return "\n".join(lines)


def describe_cohort_short(definition: CohortDefinition) -> str:
    """Return a compact one-line summary of the non-base filter steps."""
    steps = [s for s in definition.config if s.type != "base"]
    if not steps:
        return "All patients"
    return "; ".join(describe_step(s) for s in steps)
