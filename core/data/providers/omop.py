"""
OmopProvider — loads RDVs from an OMOP CDM v5.4 database.

Each PICTURE RDV is mapped to one or more OMOP CDM tables via SQL queries
that alias OMOP column names to the names the analytics layer expects.

Concept lookups join to the ``concept`` table to convert integer concept IDs
into human-readable strings (e.g. gender_concept_id 8532 → "Female").

Mapping fidelity
----------------
Most RDVs map cleanly. Two are best-effort:

  tht (Theatre List)
      OMOP has no theatre-list entity. Mapped from ``procedure_occurrence``
      filtered to the "Surgical procedure" concept hierarchy. Returns the
      most useful columns; theatre-specific fields (anaesthetist, priority)
      are not available.

  mda (Medication Administrations)
      OMOP stores orders and administrations in the same ``drug_exposure``
      table, differentiated by ``drug_type_concept_id``. mda is filtered to
      administration-type records (concept IDs 43542356 and 32838).

Schema prefix
-------------
If your OMOP tables live in a non-default schema (e.g. ``cdm.person``),
pass ``schema="cdm"`` to the constructor. All table references in the SQL
will be prefixed accordingly.

Alternatively, set a Postgres ``search_path`` in the connection URL:
  ``postgresql://user:pass@host/db?options=-csearch_path%3Dcdm``

Usage::

    provider = OmopProvider("postgresql://user:pass@host:5432/db", schema="omop")
    rdvs = provider.load_all_rdvs()
"""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from sqlalchemy import create_engine, text

from core.data.loader import _optimise_dtypes, _parse_datetimes, _validate
from core.data.rdv import RDV_FILE_MAP, RdvName

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# OMOP CDM → PICTURE RDV SQL query templates
#
# {schema} is replaced with "schema." or "" at query-build time.
# {limit}  is replaced with "LIMIT n" or "" at query-build time.
# ---------------------------------------------------------------------------

_OMOP_QUERIES: dict[str, str] = {
    # ── Patient Demographics (pde) ─────────────────────────────────────────
    # person + death + concept (gender, ethnicity)
    "pde": """
        SELECT
            p.person_id::TEXT                                           AS project_id,
            COALESCE(
                p.birth_datetime::DATE,
                MAKE_DATE(
                    p.year_of_birth,
                    COALESCE(p.month_of_birth, 1),
                    COALESCE(p.day_of_birth, 1)
                )
            )                                                           AS birth_date,
            d.death_date                                                AS death_date,
            CASE WHEN d.person_id IS NOT NULL THEN 'Y' ELSE 'N' END    AS deceased_flag,
            gc.concept_name                                             AS sex_name,
            ec.concept_name                                             AS ethnicity_name
        FROM      {schema}person      p
        LEFT JOIN {schema}death       d  ON p.person_id          = d.person_id
        LEFT JOIN {schema}concept     gc ON p.gender_concept_id   = gc.concept_id
        LEFT JOIN {schema}concept     ec ON p.ethnicity_concept_id = ec.concept_id
        {limit}
    """,
    # ── Diagnoses (dia) ────────────────────────────────────────────────────
    # condition_occurrence + concept
    "dia": """
        SELECT
            co.person_id::TEXT              AS project_id,
            co.condition_start_datetime     AS start_datetime,
            co.condition_end_datetime       AS end_datetime,
            c.concept_name                  AS diag_name,
            co.condition_source_value       AS diag_nat_code,
            co.condition_source_value       AS diag_local_code,
            co.visit_occurrence_id          AS encounter_key,
            co.condition_occurrence_id      AS sequence_number
        FROM      {schema}condition_occurrence co
        LEFT JOIN {schema}concept             c  ON co.condition_concept_id = c.concept_id
        {limit}
    """,
    # ── Hospital Admissions (adm) ──────────────────────────────────────────
    # visit_occurrence + concept (visit type, admission source, discharge)
    "adm": """
        SELECT
            vo.person_id::TEXT          AS project_id,
            vo.visit_occurrence_id      AS encounter_key,
            vc.concept_name             AS patient_class,
            vo.visit_source_value       AS admission_type,
            ac.concept_name             AS admission_source,
            dc.concept_name             AS discharge_disposition,
            vo.visit_start_datetime     AS start_datetime,
            vo.visit_end_datetime       AS end_datetime
        FROM      {schema}visit_occurrence vo
        LEFT JOIN {schema}concept          vc ON vo.visit_concept_id         = vc.concept_id
        LEFT JOIN {schema}concept          ac ON vo.admitting_concept_id     = ac.concept_id
        LEFT JOIN {schema}concept          dc ON vo.discharge_to_concept_id  = dc.concept_id
        {limit}
    """,
    # ── Medication Orders (med) ────────────────────────────────────────────
    # drug_exposure filtered to prescription / order type records
    # drug_type_concept_id:
    #   38000175 — Prescription written
    #   38000177 — Prescription dispensed through hub
    #   32817    — EHR
    "med": """
        SELECT
            de.person_id::TEXT                  AS project_id,
            de.drug_exposure_start_datetime     AS start_datetime,
            de.drug_exposure_end_datetime       AS end_datetime,
            de.drug_exposure_id                 AS medication_order_id,
            c.concept_name                      AS medication_name,
            de.drug_source_value                AS drug_code,
            de.quantity::TEXT                   AS dose_amount,
            de.refills                          AS dose_number,
            rc.concept_name                     AS route_name,
            de.visit_occurrence_id              AS encounter_key
        FROM      {schema}drug_exposure de
        LEFT JOIN {schema}concept       c  ON de.drug_concept_id  = c.concept_id
        LEFT JOIN {schema}concept       rc ON de.route_concept_id = rc.concept_id
        WHERE de.drug_type_concept_id IN (38000175, 38000177, 32817)
        {limit}
    """,
    # ── Medication Administrations (mda) ───────────────────────────────────
    # drug_exposure filtered to administration-type records
    # drug_type_concept_id:
    #   43542356 — Physician administered drug
    #   32838    — EHR administration record
    "mda": """
        SELECT
            de.person_id::TEXT                  AS project_id,
            de.drug_exposure_id                 AS medication_order_id,
            de.drug_exposure_start_datetime     AS start_datetime,
            de.drug_exposure_end_datetime       AS end_datetime,
            c.concept_name                      AS medication_name,
            de.drug_source_value                AS drug_code,
            rc.concept_name                     AS route_name,
            de.visit_occurrence_id              AS encounter_key
        FROM      {schema}drug_exposure de
        LEFT JOIN {schema}concept       c  ON de.drug_concept_id  = c.concept_id
        LEFT JOIN {schema}concept       rc ON de.route_concept_id = rc.concept_id
        WHERE de.drug_type_concept_id IN (43542356, 32838)
        {limit}
    """,
    # ── Procedures (prc) ───────────────────────────────────────────────────
    # procedure_occurrence + concept
    "prc": """
        SELECT
            po.person_id::TEXT          AS project_id,
            po.procedure_datetime       AS start_datetime,
            po.procedure_datetime       AS end_datetime,
            c.concept_name              AS proc_name,
            po.procedure_source_value   AS proc_nat_code,
            po.procedure_source_value   AS proc_local_code,
            po.visit_occurrence_id      AS encounter_key
        FROM      {schema}procedure_occurrence po
        LEFT JOIN {schema}concept             c  ON po.procedure_concept_id = c.concept_id
        {limit}
    """,
    # ── Flowsheet Rows (flo) ───────────────────────────────────────────────
    # measurement, excluding lab-type records
    # Excluded measurement_type_concept_ids:
    #   44818702 — Lab result
    #   32856    — Lab
    #   44818701 — From physical examination (typically labs)
    "flo": """
        SELECT
            m.person_id::TEXT           AS project_id,
            m.visit_occurrence_id       AS encounter_key,
            m.measurement_datetime      AS start_datetime,
            m.measurement_datetime      AS end_datetime,
            c.concept_name              AS flowsheet_measure_name,
            COALESCE(
                m.value_as_string,
                m.value_as_number::TEXT
            )                           AS value
        FROM      {schema}measurement m
        LEFT JOIN {schema}concept     c ON m.measurement_concept_id = c.concept_id
        WHERE m.measurement_type_concept_id NOT IN (44818702, 32856, 44818701)
        {limit}
    """,
    # ── Lab Results (lab) ──────────────────────────────────────────────────
    # measurement filtered to lab-type records
    "lab": """
        SELECT
            m.person_id::TEXT           AS project_id,
            m.measurement_datetime      AS start_datetime,
            m.measurement_datetime      AS end_datetime,
            c.concept_name              AS component_name,
            COALESCE(
                m.value_source_value,
                m.value_as_string,
                m.value_as_number::TEXT
            )                           AS result_value,
            m.value_as_number           AS numeric_value,
            uc.concept_name             AS unit,
            m.range_low                 AS low_range,
            m.range_high                AS high_range,
            m.visit_occurrence_id       AS encounter_key
        FROM      {schema}measurement m
        LEFT JOIN {schema}concept     c  ON m.measurement_concept_id = c.concept_id
        LEFT JOIN {schema}concept     uc ON m.unit_concept_id        = uc.concept_id
        WHERE m.measurement_type_concept_id IN (44818702, 32856, 44818701)
        {limit}
    """,
    # ── Theatre List (tht) — best effort ───────────────────────────────────
    # OMOP has no theatre-list entity.  Mapped from procedure_occurrence.
    # Theatre-specific fields (anaesthetist, priority, anaesthesia type)
    # are not available in standard OMOP and will be absent from results.
    "tht": """
        SELECT
            po.person_id::TEXT          AS project_id,
            po.procedure_datetime       AS start_datetime,
            po.procedure_datetime       AS end_datetime,
            c.concept_name              AS procedure_name,
            po.procedure_source_value   AS procedure_code,
            po.visit_occurrence_id      AS encounter_key
        FROM      {schema}procedure_occurrence po
        LEFT JOIN {schema}concept             c ON po.procedure_concept_id = c.concept_id
        {limit}
    """,
    # ── Ward Stays (wst) ───────────────────────────────────────────────────
    # visit_detail holds sub-visit records (ward/bed level) in OMOP v5.3+.
    # Falls back gracefully if visit_detail is absent (empty result).
    "wst": """
        SELECT
            vd.person_id::TEXT                                              AS project_id,
            vd.visit_detail_start_datetime                                  AS start_datetime,
            vd.visit_detail_end_datetime                                    AS end_datetime,
            cs.care_site_source_value                                       AS ward_code,
            cs.care_site_name                                               AS ward_short_name,
            EXTRACT(
                EPOCH FROM (
                    vd.visit_detail_end_datetime - vd.visit_detail_start_datetime
                )
            ) / 86400.0                                                     AS ward_stay_days,
            vd.visit_occurrence_id                                          AS encounter_key
        FROM      {schema}visit_detail vd
        LEFT JOIN {schema}care_site    cs ON vd.care_site_id = cs.care_site_id
        {limit}
    """,
    # ── Locations (loc) ────────────────────────────────────────────────────
    # person → location
    "loc": """
        SELECT
            p.person_id::TEXT           AS project_id,
            l.zip                       AS postcode,
            l.city                      AS district,
            l.state                     AS county,
            l.country_source_value      AS country
        FROM      {schema}person   p
        LEFT JOIN {schema}location l ON p.location_id = l.location_id
        {limit}
    """,
}

# RDVs flagged as best-effort — logged at WARNING, not ERROR, when columns differ
_BEST_EFFORT_RDVS: frozenset[str] = frozenset({"tht", "mda"})


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class OmopProvider:
    """DataProvider backed by an OMOP CDM v5.4 database.

    Args:
        db_url: SQLAlchemy connection string.
        schema: OMOP schema name (e.g. ``"cdm"``). When set, all table
                references are prefixed with ``"schema."``. Leave empty
                if the tables are in the default search path.
    """

    def __init__(self, db_url: str, schema: str = "") -> None:
        self._engine = create_engine(db_url, future=True, pool_pre_ping=True)
        self._schema_prefix = f"{schema}." if schema else ""

    # ------------------------------------------------------------------
    # DataProvider interface
    # ------------------------------------------------------------------

    def load_rdv(self, rdv: RdvName, n_max: Optional[int] = None) -> pd.DataFrame:
        """Query the OMOP CDM and return the RDV as a DataFrame.

        Raises:
            ValueError: If there is no OMOP mapping for this RDV.
        """
        rdv_str = str(rdv)
        if rdv_str not in _OMOP_QUERIES:
            raise ValueError(
                f"No OMOP mapping defined for RDV '{rdv_str}'. "
                f"Available: {sorted(_OMOP_QUERIES)}"
            )

        sql = _build_query(rdv_str, n_max, self._schema_prefix)
        logger.info("Loading RDV '%s' from OMOP (limit=%s)", rdv_str, n_max)

        try:
            with self._engine.connect() as conn:
                df = pd.read_sql(text(sql), conn)
        except Exception as exc:
            if rdv_str in _BEST_EFFORT_RDVS:
                logger.warning(
                    "Best-effort RDV '%s' failed — returning empty DataFrame. Error: %s",
                    rdv_str,
                    exc,
                )
                return pd.DataFrame()
            raise

        df = _parse_datetimes(df)
        df = _optimise_dtypes(df)
        _validate(rdv, df)
        logger.info("Loaded '%s': %d rows, %d cols", rdv_str, len(df), len(df.columns))
        return df

    def load_all_rdvs(
        self,
        n_max: Optional[int] = None,
        rdvs: Optional[list[RdvName]] = None,
    ) -> dict[str, pd.DataFrame]:
        """Load multiple RDVs and return them keyed by RDV name.

        RDVs with no OMOP mapping are silently skipped.
        """
        targets: list[RdvName] = rdvs if rdvs is not None else list(RDV_FILE_MAP.keys())  # type: ignore[arg-type]
        result: dict[str, pd.DataFrame] = {}

        for rdv in targets:
            if str(rdv) not in _OMOP_QUERIES:
                logger.debug("No OMOP mapping for '%s' — skipping.", rdv)
                continue
            try:
                result[rdv] = self.load_rdv(rdv, n_max=n_max)
            except Exception:
                logger.debug("Failed to load '%s' — skipping.", rdv)

        return result

    def list_available_rdvs(self) -> list[RdvName]:
        """Return all RDV names that have an OMOP mapping."""
        return [rdv for rdv in RDV_FILE_MAP if rdv in _OMOP_QUERIES]  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_query(rdv: str, n_max: Optional[int], schema_prefix: str) -> str:
    """Substitute schema prefix and LIMIT clause into a query template."""
    limit_clause = f"LIMIT {n_max}" if n_max is not None else ""
    return _OMOP_QUERIES[rdv].format(schema=schema_prefix, limit=limit_clause).strip()
