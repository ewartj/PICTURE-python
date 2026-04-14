import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { runEventTime } from '@/api/client'
import type { CohortDefinition } from '@/api/types'
import { PlotlyChart } from '@/components/PlotlyChart'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'

interface EventTimePanelProps {
  params: Record<string, unknown>
  cohortDefinitions: CohortDefinition[]
}

export function EventTimePanel({ params, cohortDefinitions }: EventTimePanelProps) {
  const rdv = (params['df_rdv'] as string | undefined)?.replace(/^df_/, '') ?? ''
  const defaultCol = (params['event_col'] as string | undefined) ?? ''
  const [eventCol, setEventCol] = React.useState(defaultCol)
  const [plotType, setPlotType] = React.useState<'boxplot' | 'histogram'>('boxplot')
  const [logScale, setLogScale] = React.useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics', 'event-time', rdv, eventCol, plotType, logScale, cohortDefinitions],
    queryFn: () => runEventTime({ rdv, event_col: eventCol, cohort_definitions: cohortDefinitions, plot_type: plotType, log_scale: logScale }),
    enabled: !!rdv && !!eventCol,
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-4 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-muted-foreground">Event column</label>
          <input
            className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring w-48"
            value={eventCol}
            onChange={(e) => setEventCol(e.target.value)}
            placeholder="e.g. diag_name"
          />
        </div>
        <Select
          label="Plot type"
          value={plotType}
          onChange={(e) => setPlotType(e.target.value as 'boxplot' | 'histogram')}
          className="w-36"
        >
          <option value="boxplot">Boxplot</option>
          <option value="histogram">Histogram</option>
        </Select>
        <label className="flex items-center gap-2 text-sm cursor-pointer select-none">
          <input type="checkbox" checked={logScale} onChange={(e) => setLogScale(e.target.checked)} />
          Log scale
        </label>
      </div>

      {(!rdv || !eventCol) && <p className="text-sm text-muted-foreground">Enter event column to run.</p>}
      {isLoading && <div className="flex gap-2 items-center text-muted-foreground text-sm"><Spinner className="h-4 w-4" />Running…</div>}
      {error && <p className="text-sm text-red-500">{(error as Error).message}</p>}

      {data && <PlotlyChart plotJson={data.plot} />}
    </div>
  )
}
