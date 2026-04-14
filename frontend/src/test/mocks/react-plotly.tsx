// Lightweight Plotly stub — avoids loading the 5 MB library in tests.
// Renders a div with the layout title so PlotlyChart tests can assert on it.
interface PlotProps {
  data: unknown
  layout: { title?: string | { text?: string } }
  style?: React.CSSProperties
  config?: unknown
  useResizeHandler?: boolean
}

export default function Plot({ layout }: PlotProps) {
  const title =
    typeof layout?.title === 'string'
      ? layout.title
      : (layout?.title as { text?: string } | undefined)?.text ?? ''
  return <div data-testid="plotly-mock" data-layout-title={title} />
}
