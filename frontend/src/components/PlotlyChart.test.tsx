/**
 * PlotlyChart tests — focuses on the title-extraction logic and edge cases.
 * The Plotly library itself is stubbed (see src/test/mocks/react-plotly.tsx).
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { PlotlyChart } from './PlotlyChart'

const makePlotJson = (title?: unknown, extraLayout?: object) =>
  JSON.stringify({ data: [], layout: { title, ...extraLayout } })

describe('PlotlyChart — title rendering', () => {
  it('renders a string title above the chart', () => {
    render(<PlotlyChart plotJson={makePlotJson('Diagnosis Frequency')} />)
    expect(screen.getByText('Diagnosis Frequency')).toBeInTheDocument()
  })

  it('renders a title from a Plotly title object { text }', () => {
    render(<PlotlyChart plotJson={makePlotJson({ text: 'Event Count' })} />)
    expect(screen.getByText('Event Count')).toBeInTheDocument()
  })

  it('renders no title element when title is absent', () => {
    render(<PlotlyChart plotJson={makePlotJson(undefined)} />)
    // The plotly mock is present but no <p> title element
    expect(screen.getByTestId('plotly-mock')).toBeInTheDocument()
    expect(screen.queryByRole('paragraph')).not.toBeInTheDocument()
  })

  it('renders no title element when title is an empty string', () => {
    render(<PlotlyChart plotJson={makePlotJson('')} />)
    expect(screen.queryByRole('paragraph')).not.toBeInTheDocument()
  })

  it('does not pass the title into Plotly layout (prevents double-render)', () => {
    render(<PlotlyChart plotJson={makePlotJson('My Title')} />)
    const mock = screen.getByTestId('plotly-mock')
    // The stub renders data-layout-title from what it receives —
    // it should be empty because PlotlyChart strips the title before passing layout down.
    expect(mock.getAttribute('data-layout-title')).toBe('')
  })
})

describe('PlotlyChart — invalid input', () => {
  it('shows an error message when plotJson is not valid JSON', () => {
    render(<PlotlyChart plotJson="not json {{{" />)
    expect(screen.getByText(/failed to parse/i)).toBeInTheDocument()
  })

  it('shows an error message when plotJson is an empty string', () => {
    render(<PlotlyChart plotJson="" />)
    expect(screen.getByText(/failed to parse/i)).toBeInTheDocument()
  })
})
