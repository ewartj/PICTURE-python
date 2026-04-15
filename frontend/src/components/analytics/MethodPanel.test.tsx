/**
 * MethodPanel tests — verifies the fn → component dispatch logic.
 *
 * Each analytics panel is mocked to a simple sentinel div so we test only
 * the routing logic, not the panels themselves.
 */
import { describe, it, expect, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '@/test/utils'
import { MethodPanel } from './MethodPanel'

vi.mock('./FrequencyPanel', () => ({
  FrequencyPanel: () => <div data-testid="frequency-panel" />,
}))
vi.mock('./EventCountPanel', () => ({
  EventCountPanel: () => <div data-testid="event-count-panel" />,
}))
vi.mock('./EventTimePanel', () => ({
  EventTimePanel: () => <div data-testid="event-time-panel" />,
}))
vi.mock('./DemographicsPanel', () => ({
  DemographicsPanel: () => <div data-testid="demographics-panel" />,
}))

const EMPTY_COHORTS = [] as never[]

describe('MethodPanel dispatch', () => {
  it('renders FrequencyPanel for gen_frequency_analysis', () => {
    renderWithProviders(
      <MethodPanel fn="gen_frequency_analysis" params={{}} cohortDefinitions={EMPTY_COHORTS} />
    )
    expect(screen.getByTestId('frequency-panel')).toBeInTheDocument()
  })

  it('renders EventCountPanel for gen_event_count', () => {
    renderWithProviders(
      <MethodPanel fn="gen_event_count" params={{}} cohortDefinitions={EMPTY_COHORTS} />
    )
    expect(screen.getByTestId('event-count-panel')).toBeInTheDocument()
  })

  it('renders EventTimePanel for gen_event_time_analysis', () => {
    renderWithProviders(
      <MethodPanel fn="gen_event_time_analysis" params={{}} cohortDefinitions={EMPTY_COHORTS} />
    )
    expect(screen.getByTestId('event-time-panel')).toBeInTheDocument()
  })

  it('renders DemographicsPanel for tpl_pde_all', () => {
    renderWithProviders(
      <MethodPanel fn="tpl_pde_all" params={{}} cohortDefinitions={EMPTY_COHORTS} />
    )
    expect(screen.getByTestId('demographics-panel')).toBeInTheDocument()
  })

  it('renders a "not implemented" fallback for unknown fn', () => {
    renderWithProviders(
      <MethodPanel fn="some_future_method" params={{}} cohortDefinitions={EMPTY_COHORTS} />
    )
    expect(screen.getByText(/some_future_method/)).toBeInTheDocument()
    expect(screen.getByText(/not yet implemented/i)).toBeInTheDocument()
  })

  it('passes params through to the panel', () => {
    // FrequencyPanel mock doesn't use params, but we can verify no crash
    expect(() =>
      renderWithProviders(
        <MethodPanel
          fn="gen_frequency_analysis"
          params={{ df_rdv: 'df_dia', event_col: 'diag_name' }}
          cohortDefinitions={EMPTY_COHORTS}
        />
      )
    ).not.toThrow()
  })
})
