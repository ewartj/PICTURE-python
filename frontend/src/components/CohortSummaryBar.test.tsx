/**
 * CohortSummaryBar tests — loading state, empty state, and rendered cohort pills.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { CohortSummaryBar } from './CohortSummaryBar'
import type { ResolvedCohort } from '@/api/types'

const FEMALE_MALE: ResolvedCohort[] = [
  { label: 'Female', n_patients: 150, n_periods: 300 },
  { label: 'Male',   n_patients: 120, n_periods: 240 },
]

describe('CohortSummaryBar — loading state', () => {
  it('shows a loading message while resolving', () => {
    render(<CohortSummaryBar cohorts={[]} isLoading={true} />)
    expect(screen.getByText(/resolving cohorts/i)).toBeInTheDocument()
  })

  it('does not render cohort pills while loading', () => {
    render(<CohortSummaryBar cohorts={FEMALE_MALE} isLoading={true} />)
    expect(screen.queryByText('Female')).not.toBeInTheDocument()
  })
})

describe('CohortSummaryBar — empty state', () => {
  it('shows a placeholder when no cohorts are resolved', () => {
    render(<CohortSummaryBar cohorts={[]} isLoading={false} />)
    expect(screen.getByText(/no cohorts resolved/i)).toBeInTheDocument()
  })
})

describe('CohortSummaryBar — resolved cohorts', () => {
  it('renders a pill for each cohort', () => {
    render(<CohortSummaryBar cohorts={FEMALE_MALE} isLoading={false} />)
    expect(screen.getByText('Female')).toBeInTheDocument()
    expect(screen.getByText('Male')).toBeInTheDocument()
  })

  it('displays patient counts', () => {
    render(<CohortSummaryBar cohorts={FEMALE_MALE} isLoading={false} />)
    expect(screen.getByText('150')).toBeInTheDocument()
    expect(screen.getByText('120')).toBeInTheDocument()
  })

  it('displays period counts', () => {
    const { container } = render(<CohortSummaryBar cohorts={FEMALE_MALE} isLoading={false} />)
    // Period count and " periods" label are sibling text nodes in the same span,
    // so we assert on the container's combined textContent instead of getByText.
    expect(container.textContent).toContain('300')
    expect(container.textContent).toContain('240')
  })

  it('applies distinct colour classes to the first two cohorts', () => {
    const { container } = render(
      <CohortSummaryBar cohorts={FEMALE_MALE} isLoading={false} />
    )
    const pills = container.querySelectorAll('[class*="cohort-color-"]')
    expect(pills[0].className).toContain('cohort-color-0')
    expect(pills[1].className).toContain('cohort-color-1')
  })

  it('cycles colours for more than 5 cohorts', () => {
    const many: ResolvedCohort[] = Array.from({ length: 6 }, (_, i) => ({
      label: `Cohort ${i}`,
      n_patients: i,
      n_periods: i * 2,
    }))
    const { container } = render(
      <CohortSummaryBar cohorts={many} isLoading={false} />
    )
    const pills = container.querySelectorAll('[class*="cohort-color-"]')
    // 6th cohort (index 5) wraps back to cohort-color-0
    expect(pills[5].className).toContain('cohort-color-0')
  })
})
