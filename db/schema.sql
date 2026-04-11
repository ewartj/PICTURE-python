-- PICTURE RDV schema for PostgreSQL
--
-- Column names are normalised to snake_case. A few CSV columns are renamed to
-- match the names the analytics layer expects:
--
--   flo.type              → flowsheet_measure_name
--   med.drug_name         → medication_name
--   mda.drug_name         → medication_name
--   lab.Value             → result_value
--   lab.ResultStatus      → result_status
--   lab.abnormal          → abnormal_flag
--   adm.disharge_*        → discharge_* (typo fixed)
--   loc."LSOA Code"       → lsoa_code
--   loc."MSOA Code"       → msoa_code
--
-- Run with:  psql $DATABASE_URL -f db/schema.sql

-- ---------------------------------------------------------------------------
-- Patient Demographics (pde)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pde (
    project_id          TEXT        NOT NULL,
    hospital_no         TEXT,
    surname             TEXT,
    forename            TEXT,
    birth_date          DATE,
    death_date          DATE,
    deceased_flag       TEXT,
    sex_nat_code        TEXT,
    sex_name            TEXT,
    ethnicity_nat_code  TEXT,
    ethnicity_local_code TEXT,
    ethnicity_name      TEXT
);

CREATE INDEX IF NOT EXISTS pde_project_id_idx ON pde (project_id);

-- ---------------------------------------------------------------------------
-- Diagnoses (dia)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dia (
    project_id                  TEXT,
    start_datetime              TIMESTAMP,
    end_datetime                TIMESTAMP,
    epic_diagnosis_source_code  TEXT,
    epic_diagnosis_source_name  TEXT,
    epic_diagnosis_code         TEXT,
    epic_diagnosis_name         TEXT,
    primary_diagnoses           TEXT,
    encounter_key               BIGINT,
    sequence_number             INTEGER,
    diag_nat_code               TEXT,
    diag_local_code             TEXT,
    diag_name                   TEXT,
    diag_supl_local_code        TEXT,
    diag_supl_name              TEXT
);

CREATE INDEX IF NOT EXISTS dia_project_id_idx    ON dia (project_id);
CREATE INDEX IF NOT EXISTS dia_project_dt_idx    ON dia (project_id, start_datetime);

-- ---------------------------------------------------------------------------
-- Diagnoses code reference (dia_codes) — lookup table, not an RDV
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dia_codes (
    diag_nat_code   TEXT,
    chapter_range   TEXT,
    chapter_name    TEXT,
    group_range     TEXT,
    group_name      TEXT,
    sub_group_range TEXT,
    sub_group_name  TEXT
);

CREATE INDEX IF NOT EXISTS dia_codes_nat_code_idx ON dia_codes (diag_nat_code);

-- ---------------------------------------------------------------------------
-- Hospital Admissions (adm)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS adm (
    project_id              TEXT,
    encounter_key           BIGINT,
    patient_class           TEXT,
    hospital_service        TEXT,
    admission_type          TEXT,
    admission_source        TEXT,
    discharge_disposition   TEXT,
    principal_problem       TEXT,
    start_datetime          TIMESTAMP,
    end_datetime            TIMESTAMP
);

CREATE INDEX IF NOT EXISTS adm_project_id_idx ON adm (project_id);
CREATE INDEX IF NOT EXISTS adm_encounter_idx  ON adm (encounter_key);

-- ---------------------------------------------------------------------------
-- Medication Orders (med)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS med (
    project_id                      TEXT,
    start_datetime                  TIMESTAMP,
    end_datetime                    TIMESTAMP,
    medication_order_key            BIGINT,
    ordered_datetime                TIMESTAMP,
    medication_order_id             BIGINT,
    sequence_number                 INTEGER,
    drug_code                       TEXT,
    medication_name                 TEXT,       -- renamed from drug_name
    drug_gpi                        TEXT,
    drug_simple_generic_name        TEXT,
    drug_therapeutic_class_name     TEXT,
    drug_pharmaceutical_class_name  TEXT,
    drug_pharmaceutical_subclass_name TEXT,
    dose_amount                     TEXT,
    formulation_code                TEXT,
    intended_frequency              TEXT,
    quantity                        TEXT,
    dose                            TEXT,
    dose_range                      TEXT,
    calculated_dose_range           TEXT,
    dose_number                     INTEGER,
    route_name                      TEXT,
    indication                      TEXT,
    indication_comments             TEXT,
    response                        TEXT,
    medication_order_name           TEXT,
    medication_order_mode_name      TEXT,
    medication_order_class_name     TEXT,
    medication_order_source_name    TEXT,
    disps_this_period               INTEGER,
    admins_this_period              INTEGER,
    encounter_key                   BIGINT
);

CREATE INDEX IF NOT EXISTS med_project_id_idx ON med (project_id);
CREATE INDEX IF NOT EXISTS med_project_dt_idx ON med (project_id, start_datetime);

-- ---------------------------------------------------------------------------
-- Medication Administrations (mda)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mda (
    project_id              TEXT,
    medication_order_id     BIGINT,
    medication_order_key    BIGINT,
    start_datetime          TIMESTAMP,
    end_datetime            TIMESTAMP,
    prn_dose                TEXT,
    drug_code               TEXT,
    medication_name         TEXT,       -- renamed from drug_name
    admin_seq               INTEGER,
    intended_frequency      TEXT,
    route_name              TEXT,
    medication_order_mode_name TEXT,
    sched_admin_datetime    TIMESTAMP
);

CREATE INDEX IF NOT EXISTS mda_project_id_idx ON mda (project_id);
CREATE INDEX IF NOT EXISTS mda_project_dt_idx ON mda (project_id, start_datetime);

-- ---------------------------------------------------------------------------
-- Procedures (prc)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prc (
    project_id                  TEXT,
    start_datetime              TIMESTAMP,
    end_datetime                TIMESTAMP,
    epic_procedure_source_code  TEXT,
    epic_procedure_source_name  TEXT,
    epic_procedure_code         TEXT,
    epic_procedure_name         TEXT,
    principal_procedure         TEXT,
    encounter_key               BIGINT,
    proc_code_set               TEXT,
    proc_nat_code               TEXT,
    proc_local_code             TEXT,
    proc_name                   TEXT
);

CREATE INDEX IF NOT EXISTS prc_project_id_idx ON prc (project_id);
CREATE INDEX IF NOT EXISTS prc_project_dt_idx ON prc (project_id, start_datetime);

-- ---------------------------------------------------------------------------
-- Flowsheet Rows (flo)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS flo (
    project_id              TEXT,
    encounter_key           BIGINT,
    taken_datetime          TIMESTAMP,
    start_datetime          TIMESTAMP,
    end_datetime            TIMESTAMP,
    flowsheet_measure_name  TEXT,       -- renamed from type
    value                   TEXT,
    comment                 TEXT
);

CREATE INDEX IF NOT EXISTS flo_project_id_idx ON flo (project_id);
CREATE INDEX IF NOT EXISTS flo_project_dt_idx ON flo (project_id, start_datetime);

-- ---------------------------------------------------------------------------
-- Lab Results (lab)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS lab (
    project_id          TEXT,
    lab_test_key        BIGINT,
    start_datetime      TIMESTAMP,
    end_datetime        TIMESTAMP,
    specimen_type       TEXT,
    specimen_source     TEXT,
    method              TEXT,
    pathology_type      TEXT,
    source_type         TEXT,
    section             TEXT,
    sub_section         TEXT,
    test_name           TEXT,
    collected_datetime  TIMESTAMP,
    received_datetime   TIMESTAMP,
    verified_datetime   TIMESTAMP,
    component_basename  TEXT,
    component_name      TEXT,
    labcomponent_header TEXT,
    component_type      TEXT,
    component_subtype   TEXT,
    component_datatype  TEXT,
    result_value        TEXT,           -- renamed from Value
    unit                TEXT,
    numeric_value       NUMERIC,
    result_status       TEXT,           -- renamed from ResultStatus
    reference_range     TEXT,
    low_range           NUMERIC,
    high_range          NUMERIC,
    flag                TEXT,
    abnormal_flag       TEXT,           -- renamed from abnormal
    encounter_key       BIGINT
);

CREATE INDEX IF NOT EXISTS lab_project_id_idx ON lab (project_id);
CREATE INDEX IF NOT EXISTS lab_project_dt_idx ON lab (project_id, start_datetime);

-- ---------------------------------------------------------------------------
-- Theatre List (tht)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tht (
    project_id                      TEXT,
    start_datetime                  TIMESTAMP,
    end_datetime                    TIMESTAMP,
    theatre_name                    TEXT,
    opert_name                      TEXT,
    procedure_code                  TEXT,
    procedure_name                  TEXT,
    consultant_code                 TEXT,
    consultant_name                 TEXT,
    spect_nat_code                  TEXT,
    spect_local_code                TEXT,
    spect_name                      TEXT,
    theatre_department_name         TEXT,
    priority_local_code             TEXT,
    priority_nat_code               TEXT,
    priority_name                   TEXT,
    classification_code             TEXT,
    classification_name             TEXT,
    surgeon_type                    TEXT,
    number_of_procedures            INTEGER,
    division                        TEXT,
    theatre_visit_date              DATE,
    in_room_datetime                TIMESTAMP,
    anaesthesia_induction_datetime  TIMESTAMP,
    anaesthesia_stop_datetime       TIMESTAMP,
    out_room_datetime               TIMESTAMP,
    primary_anaesthesia_type        TEXT,
    patient_class_name              TEXT,
    anaesthetist_code               TEXT,
    anaesthetist_name               TEXT,
    anaesthetist_type               TEXT,
    adcat_nat_code                  TEXT,
    adcat_local_code                TEXT,
    adcat_name                      TEXT,
    procedure_not_performed         TEXT,
    not_performed_local_code        TEXT,
    not_performed_name              TEXT,
    procedure_cancelled             TEXT,
    cancelled_local_code            TEXT,
    cancelled_name                  TEXT,
    encounter_key                   BIGINT
);

CREATE INDEX IF NOT EXISTS tht_project_id_idx ON tht (project_id);
CREATE INDEX IF NOT EXISTS tht_project_dt_idx ON tht (project_id, start_datetime);

-- ---------------------------------------------------------------------------
-- Ward Stays (wst)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS wst (
    project_id      TEXT,
    start_datetime  TIMESTAMP,
    end_datetime    TIMESTAMP,
    ward_code       TEXT,
    ward_short_name TEXT,
    ward_stay_days  NUMERIC,
    icu_ward_stay   INTEGER,
    encounter_key   BIGINT
);

CREATE INDEX IF NOT EXISTS wst_project_id_idx ON wst (project_id);
CREATE INDEX IF NOT EXISTS wst_project_dt_idx ON wst (project_id, start_datetime);

-- ---------------------------------------------------------------------------
-- Locations (loc)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS loc (
    project_id      TEXT,
    start_datetime  TIMESTAMP,
    end_datetime    TIMESTAMP,
    address_type    TEXT,
    postcode        TEXT,
    lsoa_code       TEXT,       -- renamed from "LSOA Code"
    msoa_code       TEXT,       -- renamed from "MSOA Code"
    district        TEXT,
    county          TEXT,
    region          TEXT,
    country         TEXT
);

CREATE INDEX IF NOT EXISTS loc_project_id_idx ON loc (project_id);
