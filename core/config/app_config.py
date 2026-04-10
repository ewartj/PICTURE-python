"""App YAML config parser.

Parses a PICTURE app YAML file into typed dataclasses.

Each app YAML has the structure::

    title: "..."
    description: "..."
    creator: "..."
    dataset: study01
    initialCohorts:
      - label: Female
        config:
          - type: filter
            rdv: pde
            column: sex_name
            query_type: str_matches
            val: Female
            inclusion: ever
    offerCohortBuilder: true
    analysis:
      - tab: Demographics
        methodList:
          - fn: tpl_pde_all
            params:
              df_pde: df_pde
      - tab: Diagnoses
        methodList:
          - fn: gen_frequency_analysis
            tab_lbl: Common diagnoses
            params:
              df_rdv: df_dia
              event_col: diag_name
    outputs:
      interactive: true
      pdf: false

Replaces: picture.platform R/app_picture.R  ``.app_yaml_to_config()``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import yaml

from core.cohort.models import CohortDefinition, cohort_definition_from_yaml


# ---------------------------------------------------------------------------
# Custom YAML tag: !datelist
# ---------------------------------------------------------------------------
# R app YAMLs use ``!datelist [2020-01-01, 2021-12-31]`` to mark a list of
# dates used in ``date_between`` filter values.  We parse them to datetime
# objects so downstream code can use them directly.


def _datelist_constructor(
    loader: yaml.Loader, node: yaml.SequenceNode
) -> list[datetime]:
    raw = loader.construct_sequence(node)
    result = []
    for item in raw:
        if isinstance(item, datetime):
            result.append(item)
        elif isinstance(item, str):
            # Accept ISO formats: "2020-01-01" or "2020-01-01T00:00:00"
            result.append(datetime.fromisoformat(item))
        else:
            result.append(item)
    return result


# Register on SafeLoader so yaml.safe_load works with these tags.
yaml.add_constructor("!datelist", _datelist_constructor, Loader=yaml.SafeLoader)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class AnalysisMethod:
    """A single analytics method within a tab's methodList.

    Mirrors one entry of ``analysis[].methodList`` in the app YAML.

    Attributes:
        fn:       Function name, e.g. ``gen_frequency_analysis``.
                  Maps to a class in ``core/analytics/``.
        params:   Named parameters passed to the function.
                  Values that start with ``df_`` are RDV references resolved
                  at runtime; all others are passed directly.
        tab_lbl:  Optional display label for the sub-tab.
        output:   Optional reactive name to store the result under
                  (used for pipeline chaining, e.g. a wrangling step whose
                  output feeds the next method).
        rpkg:     Original R package name (informational only; ignored at
                  runtime in Python).
    """

    fn: str
    params: dict[str, Any] = field(default_factory=dict)
    tab_lbl: Optional[str] = None
    output: Optional[str] = None
    rpkg: Optional[str] = None

    @property
    def rdv_params(self) -> dict[str, str]:
        """Return only the params that reference an RDV (start with ``df_``)."""
        return {
            k: v
            for k, v in self.params.items()
            if isinstance(v, str) and v.startswith("df_")
        }

    @property
    def static_params(self) -> dict[str, Any]:
        """Return only the params that are literal values (not RDV references)."""
        return {
            k: v
            for k, v in self.params.items()
            if not (isinstance(v, str) and v.startswith("df_"))
        }


@dataclass
class AnalysisTab:
    """A top-level tab in the analysis section.

    Each tab groups one or more analytics methods shown as sub-tabs.
    """

    tab: str
    method_list: list[AnalysisMethod] = field(default_factory=list)


@dataclass
class OutputConfig:
    """Controls which output formats are enabled."""

    interactive: bool = True
    pdf: bool = False


@dataclass
class AppConfig:
    """Parsed representation of a PICTURE app YAML file.

    Attributes:
        id:                   Integer ID assigned at load time (1-based).
        title:                Short title shown on the homepage.
        description:          Longer description of the analysis purpose.
        creator:              Email of the analysis creator.
        img:                  Optional path to a thumbnail image.
        dataset:              Name of the dataset folder to load.
        amount_of_data:       ``"limited"`` or ``"full"`` (controls n_max).
        initial_cohorts:      List of :class:`CohortDefinition` objects.
        offer_cohort_builder: Whether to show the interactive cohort builder.
        analysis:             List of :class:`AnalysisTab` objects.
        outputs:              :class:`OutputConfig`.
        source_path:          Path to the YAML file this was loaded from.
    """

    id: int
    title: str
    description: str = ""
    creator: str = ""
    img: Optional[str] = None
    dataset: Optional[str] = None
    amount_of_data: Optional[str] = None
    initial_cohorts: list[CohortDefinition] = field(default_factory=list)
    offer_cohort_builder: bool = True
    analysis: list[AnalysisTab] = field(default_factory=list)
    outputs: OutputConfig = field(default_factory=OutputConfig)
    source_path: Optional[Path] = None

    @property
    def all_rdv_names(self) -> set[str]:
        """Return every RDV name referenced by any analysis method.

        RDV params have the form ``df_<rdv_name>``, so we strip the ``df_``
        prefix to get the RDV code (e.g. ``df_pde`` → ``pde``).
        """
        names: set[str] = set()
        for tab in self.analysis:
            for method in tab.method_list:
                for v in method.rdv_params.values():
                    rdv_code = re.sub(r"^df_", "", v)
                    names.add(rdv_code)
        return names


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_outputs(raw: Optional[dict]) -> OutputConfig:
    if not raw:
        return OutputConfig()

    # YAML may have uppercase TRUE/FALSE (from R); yaml.safe_load handles these
    # as booleans already, but guard against string values just in case.
    def _bool(v: Any) -> bool:
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("true", "1", "yes")

    return OutputConfig(
        interactive=_bool(raw.get("interactive", True)),
        pdf=_bool(raw.get("pdf", False)),
    )


def _parse_method(raw: dict) -> AnalysisMethod:
    params = raw.get("params") or {}
    # Normalise: params may have R-style TRUE/FALSE strings for boolean values.
    normalised: dict[str, Any] = {}
    for k, v in params.items():
        if isinstance(v, str) and v.upper() == "TRUE":
            normalised[k] = True
        elif isinstance(v, str) and v.upper() == "FALSE":
            normalised[k] = False
        else:
            normalised[k] = v

    return AnalysisMethod(
        fn=raw["fn"],
        params=normalised,
        tab_lbl=raw.get("tab_lbl"),
        output=raw.get("output"),
        rpkg=raw.get("rpkg"),
    )


def _parse_tab(raw: dict) -> AnalysisTab:
    methods = [_parse_method(m) for m in raw.get("methodList", [])]
    return AnalysisTab(tab=raw["tab"], method_list=methods)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_app_config(path: Path, *, app_id: int = 1) -> AppConfig:
    """Load and parse a single app YAML file into an :class:`AppConfig`.

    Args:
        path:   Path to the ``.yaml`` file.
        app_id: Integer ID to assign (used when loading multiple apps).

    Returns:
        Parsed :class:`AppConfig`.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError:        If the YAML is missing required top-level keys.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"App config not found: {path}")

    with path.open() as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ValueError(
            f"Expected a YAML mapping at the top level, got {type(raw)}: {path}"
        )

    # Required field
    if "title" not in raw:
        raise ValueError(f"App YAML missing required field 'title': {path}")

    # initialCohorts
    initial_cohorts = [
        cohort_definition_from_yaml(c) for c in (raw.get("initialCohorts") or [])
    ]

    # analysis tabs
    analysis = [_parse_tab(t) for t in (raw.get("analysis") or [])]

    return AppConfig(
        id=app_id,
        title=raw["title"],
        description=raw.get("description", ""),
        creator=raw.get("creator", ""),
        img=raw.get("img"),
        dataset=raw.get("dataset"),
        amount_of_data=raw.get("amount_of_data_to_load"),
        initial_cohorts=initial_cohorts,
        offer_cohort_builder=bool(raw.get("offerCohortBuilder", True)),
        analysis=analysis,
        outputs=_parse_outputs(raw.get("outputs")),
        source_path=path,
    )


def load_app_configs(paths: list[Path]) -> list[AppConfig]:
    """Load multiple app YAML files, assigning sequential IDs starting at 1.

    Args:
        paths: List of paths to app YAML files.

    Returns:
        List of :class:`AppConfig` objects in the same order as *paths*.
    """
    return [load_app_config(p, app_id=i + 1) for i, p in enumerate(paths)]
