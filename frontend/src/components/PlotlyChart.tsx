import React from 'react'
import Plot from 'react-plotly.js'

interface PlotlyChartProps {
  plotJson: string
  className?: string
  style?: React.CSSProperties
}

export function PlotlyChart({ plotJson, className, style }: PlotlyChartProps) {
  const fig = React.useMemo(() => {
    try {
      return JSON.parse(plotJson) as { data: Plotly.Data[]; layout: Partial<Plotly.Layout> }
    } catch {
      return null
    }
  }, [plotJson])

  // Hooks must all be called before any early return (Rules of Hooks).
  const layout = React.useMemo(() => {
    if (!fig) return {}
    return {
      ...fig.layout,
      title: undefined, // rendered as HTML below — prevents Plotly drawing it inside the chart
      autosize: true,
      margin: { t: 16, r: 24, b: 24, l: 24, pad: 4 },
      xaxis: { ...fig.layout.xaxis, automargin: true },
      yaxis: { ...fig.layout.yaxis, automargin: true },
    }
  }, [fig])

  if (!fig) return <p className="text-sm text-red-500">Failed to parse chart data.</p>

  const title =
    typeof fig.layout.title === 'string'
      ? fig.layout.title
      : (fig.layout.title as { text?: string } | undefined)?.text ?? ''

  return (
    <div className={className}>
      {title && (
        <p className="text-sm font-medium text-foreground mb-1 px-1">{title}</p>
      )}
      <Plot
        data={fig.data}
        layout={layout}
        config={{ responsive: true, displayModeBar: false }}
        style={style ?? { width: '100%', height: '460px' }}
        useResizeHandler
      />
    </div>
  )
}
