import type {
  AppConfigSummary,
  AppConfigDetail,
  CohortResolveRequest,
  CohortResolveResponse,
  FrequencyRequest,
  FrequencyResponse,
  EventCountRequest,
  EventCountResponse,
  EventTimeRequest,
  EventTimeResponse,
  CategoricalRatiosRequest,
  CategoricalRatiosResponse,
  CohortCharacteristicsRequest,
  CohortCharacteristicsResponse,
  RdvListResponse,
  RdvInfoResponse,
} from './types'

const BASE = '/api'

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(body?.detail ?? `API error ${res.status}`)
  }
  return res.json() as Promise<T>
}

// ── Apps ─────────────────────────────────────────────────────────────────────

export const listApps = (): Promise<AppConfigSummary[]> =>
  apiFetch('/apps')

export const getApp = (id: number): Promise<AppConfigDetail> =>
  apiFetch(`/apps/${id}`)

// ── Cohorts ───────────────────────────────────────────────────────────────────

export const resolveCohorts = (body: CohortResolveRequest): Promise<CohortResolveResponse> =>
  apiFetch('/cohorts/resolve', { method: 'POST', body: JSON.stringify(body) })

// ── Analytics ─────────────────────────────────────────────────────────────────

export const runFrequency = (body: FrequencyRequest): Promise<FrequencyResponse> =>
  apiFetch('/analytics/frequency', { method: 'POST', body: JSON.stringify(body) })

export const runEventCount = (body: EventCountRequest): Promise<EventCountResponse> =>
  apiFetch('/analytics/event-count', { method: 'POST', body: JSON.stringify(body) })

export const runEventTime = (body: EventTimeRequest): Promise<EventTimeResponse> =>
  apiFetch('/analytics/event-time', { method: 'POST', body: JSON.stringify(body) })

export const runCategoricalRatios = (body: CategoricalRatiosRequest): Promise<CategoricalRatiosResponse> =>
  apiFetch('/analytics/categorical-ratios', { method: 'POST', body: JSON.stringify(body) })

export const runCohortCharacteristics = (body: CohortCharacteristicsRequest): Promise<CohortCharacteristicsResponse> =>
  apiFetch('/analytics/cohort-characteristics', { method: 'POST', body: JSON.stringify(body) })

// ── Data ──────────────────────────────────────────────────────────────────────

export const listRdvs = (): Promise<RdvListResponse> =>
  apiFetch('/data/rdvs')

export const getRdvInfo = (name: string): Promise<RdvInfoResponse> =>
  apiFetch(`/data/rdvs/${name}`)
