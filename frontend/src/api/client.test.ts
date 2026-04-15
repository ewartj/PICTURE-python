/**
 * API client tests — verify that each function sends the correct request body.
 *
 * These tests exist specifically to catch field-name mismatches between the
 * frontend and backend schemas (the `cohorts` vs `cohort_definitions` bug is
 * the canonical example).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  resolveCohorts,
  runFrequency,
  runEventCount,
  runEventTime,
  runCategoricalRatios,
  runCohortCharacteristics,
} from './client'

const OK_JSON = (body: unknown) =>
  Promise.resolve(new Response(JSON.stringify(body), { status: 200 }))

beforeEach(() => {
  vi.restoreAllMocks()
})

// ── Helper to capture the request body sent by a client function ──────────────

async function captureBody(fn: () => Promise<unknown>): Promise<Record<string, unknown>> {
  const spy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => OK_JSON({}))
  await fn().catch(() => {}) // ignore response shape errors
  const [, init] = spy.mock.calls[0]
  return JSON.parse((init as RequestInit).body as string)
}

// ── resolveCohorts ────────────────────────────────────────────────────────────

describe('resolveCohorts', () => {
  it('sends "cohorts" not "cohort_definitions"', async () => {
    const body = await captureBody(() =>
      resolveCohorts({ cohorts: [{ label: 'All', config: [] }] })
    )
    expect(body).toHaveProperty('cohorts')
    expect(body).not.toHaveProperty('cohort_definitions')
  })

  it('passes cohort definitions through unchanged', async () => {
    const defs = [{ label: 'Female', config: [{ type: 'filter', rdv: 'pde', column: 'sex_name', query_type: 'str_matches', inclusion: 'ever', val: ['Female'], window: null }] }]
    const body = await captureBody(() => resolveCohorts({ cohorts: defs }))
    expect(body.cohorts).toEqual(defs)
  })
})

// ── Analytics endpoints all use "cohort_definitions" ─────────────────────────

describe('runFrequency', () => {
  it('sends "cohort_definitions" not "cohorts"', async () => {
    const body = await captureBody(() =>
      runFrequency({ rdv: 'dia', event_col: 'diag_name', cohort_definitions: [], value: 'frequency' })
    )
    expect(body).toHaveProperty('cohort_definitions')
    expect(body).not.toHaveProperty('cohorts')
  })

  it('sends rdv, event_col, and value', async () => {
    const body = await captureBody(() =>
      runFrequency({ rdv: 'dia', event_col: 'diag_name', cohort_definitions: [], value: 'count' })
    )
    expect(body.rdv).toBe('dia')
    expect(body.event_col).toBe('diag_name')
    expect(body.value).toBe('count')
  })
})

describe('runEventCount', () => {
  it('sends "cohort_definitions"', async () => {
    const body = await captureBody(() =>
      runEventCount({ rdv: 'dia', event_col: 'diag_name', cohort_definitions: [], count_unique: true })
    )
    expect(body).toHaveProperty('cohort_definitions')
  })
})

describe('runEventTime', () => {
  it('sends "cohort_definitions"', async () => {
    const body = await captureBody(() =>
      runEventTime({ rdv: 'dia', event_col: 'diag_name', cohort_definitions: [], plot_type: 'boxplot', log_scale: false })
    )
    expect(body).toHaveProperty('cohort_definitions')
  })
})

describe('runCategoricalRatios', () => {
  it('sends "cohort_definitions"', async () => {
    const body = await captureBody(() =>
      runCategoricalRatios({ rdv: 'pde', col: 'sex_name', cohort_definitions: [] })
    )
    expect(body).toHaveProperty('cohort_definitions')
  })
})

describe('runCohortCharacteristics', () => {
  it('sends "cohort_definitions"', async () => {
    const body = await captureBody(() =>
      runCohortCharacteristics({ cohort_definitions: [] })
    )
    expect(body).toHaveProperty('cohort_definitions')
  })
})

// ── Error handling ────────────────────────────────────────────────────────────

describe('error handling', () => {
  it('throws with the detail message from a 422 response', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.resolve(new Response(JSON.stringify({ detail: 'Validation error' }), { status: 422 }))
    )
    await expect(resolveCohorts({ cohorts: [] })).rejects.toThrow('Validation error')
  })

  it('throws with status text when response body is not JSON', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(() =>
      Promise.resolve(new Response('Bad gateway', { status: 502, statusText: 'Bad Gateway' }))
    )
    await expect(resolveCohorts({ cohorts: [] })).rejects.toThrow()
  })
})
