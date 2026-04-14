// Types mirroring the FastAPI Pydantic schemas in api/schemas/

// ── Apps ─────────────────────────────────────────────────────────────────────

export interface AppConfigSummary {
  id: number
  title: string
  description: string
  creator: string
  img: string | null
  dataset: string | null
}

export interface CohortFilterStep {
  type: string
  rdv: string | null
  column: string | null
  query_type: string
  inclusion: string
  val: unknown[] | null
  window: number[] | null
}

export interface CohortDefinition {
  label: string
  config: CohortFilterStep[]
}

export interface AnalysisMethod {
  fn: string
  params: Record<string, unknown>
  tab_lbl: string | null
  output: string | null
  rpkg: string | null
}

export interface AnalysisTab {
  tab: string
  method_list: AnalysisMethod[]
}

export interface OutputConfig {
  interactive: boolean
  pdf: boolean
}

export interface AppConfigDetail extends AppConfigSummary {
  offer_cohort_builder: boolean
  initial_cohorts: CohortDefinition[]
  analysis: AnalysisTab[]
  outputs: OutputConfig
  all_rdv_names: string[]
}

// ── Cohorts ───────────────────────────────────────────────────────────────────

export interface ResolvedCohort {
  label: string
  n_patients: number
  n_periods: number
}

export interface CohortResolveRequest {
  cohorts: CohortDefinition[]
}

export interface CohortResolveResponse {
  cohorts: ResolvedCohort[]
}

// ── Analytics shared ──────────────────────────────────────────────────────────

export interface AnalysisResponseBase {
  table: Record<string, unknown>[]
  plot: string // Plotly figure JSON
  meta: Record<string, unknown>
}

// ── Frequency ─────────────────────────────────────────────────────────────────

export interface FrequencyRequest {
  rdv: string
  event_col: string
  cohort_definitions: CohortDefinition[]
  n_max?: number
  value: 'frequency' | 'count'
}

export type FrequencyResponse = AnalysisResponseBase

// ── Event Count ───────────────────────────────────────────────────────────────

export interface EventCountRequest {
  rdv: string
  event_col: string
  cohort_definitions: CohortDefinition[]
  count_unique: boolean
  n_max?: number
}

export type EventCountResponse = AnalysisResponseBase

// ── Event Time ────────────────────────────────────────────────────────────────

export interface EventTimeRequest {
  rdv: string
  event_col: string
  cohort_definitions: CohortDefinition[]
  plot_type: 'boxplot' | 'histogram'
  log_scale: boolean
  n_max?: number
}

export interface EventTimeResponse {
  summary: Record<string, unknown>[]
  plot: string
  meta: Record<string, unknown>
}

// ── Categorical Ratios ────────────────────────────────────────────────────────

export interface CategoricalRatiosRequest {
  rdv: string
  col: string
  cohort_definitions: CohortDefinition[]
}

export type CategoricalRatiosResponse = AnalysisResponseBase

// ── Cohort Characteristics ────────────────────────────────────────────────────

export interface CohortCharacteristicsRequest {
  cohort_definitions: CohortDefinition[]
}

export type CohortCharacteristicsResponse = AnalysisResponseBase

// ── Data ──────────────────────────────────────────────────────────────────────

export interface RdvListResponse {
  available: string[]
}

export interface RdvInfoResponse {
  name: string
  label: string
  n_rows: number
  columns: string[]
}
