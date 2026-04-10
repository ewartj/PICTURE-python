"""Shared colour palette for analytics plots."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

COHORT_COLOURS = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
]


def cohort_colour(index: int) -> str:
    """Return the colour for cohort *index*, wrapping with a warning if exceeded.

    Using this helper instead of ``COHORT_COLOURS[i % len(COHORT_COLOURS)]``
    directly ensures callers are notified when colour reuse occurs (which
    produces identical colours for distinct cohorts in the same plot).
    """
    n = len(COHORT_COLOURS)
    if index >= n:
        logger.warning(
            "cohort_colour: index %d exceeds palette size (%d); "
            "colour %s will be reused — consider adding more cohort colours.",
            index,
            n,
            COHORT_COLOURS[index % n],
        )
    return COHORT_COLOURS[index % n]
