import React from 'react'
import { useQuery } from '@tanstack/react-query'
import { runFrequency } from '@/api/client'
import type { CohortDefinition } from '@/api/types'
import { PlotlyChart } from '@/components/PlotlyChart'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'

interface FrequencyPanelProps {
  params: Record<string, unknown>
  cohortDefinitions: CohortDefinition[]
}

export function FrequencyPanel({ params, cohortDefinitions }: FrequencyPanelProps) {
  const rdv = (params['df_rdv'] as string | undefined)?.replace(/^df_/, '') ?? 'dia'
  const defaultCol = (params['event_col'] as string | undefined) ?? ''
  const [eventCol, setEventCol] = React.useState(defaultCol)
  const [valueMode, setValueMode] = React.useState<'frequency' | 'count'>('frequency')

  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics', 'frequency', rdv, eventCol, valueMode, cohortDefinitions],
    queryFn: () => runFrequency({ rdv, event_col: eventCol, cohort_definitions: cohortDefinitions, value: valueMode }),
    enabled: !!eventCol,
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
          label="Value mode"
          value={valueMode}
          onChange={(e) => setValueMode(e.target.value as 'frequency' | 'count')}
          className="w-36"
        >
          <option value="frequency">Frequency</option>
          <option value="count">Count</option>
        </Select>
      </div>

      {!eventCol && <p className="text-sm text-muted-foreground">Enter an event column to run analysis.</p>}
      {isLoading && <div className="flex gap-2 items-center text-muted-foreground text-sm"><Spinner className="h-4 w-4" />Running…</div>}
      {error && <p className="text-sm text-red-500">{(error as Error).message}</p>}

      {data && (
        <Tabs defaultValue="chart">
          <TabsList>
            <TabsTrigger value="chart">Chart</TabsTrigger>
            <TabsTrigger value="table">Table</TabsTrigger>
          </TabsList>
          <TabsContent value="chart">
            <PlotlyChart plotJson={data.plot} />
          </TabsContent>
          <TabsContent value="table">
            <ResultTable rows={data.table} />
          </TabsContent>
        </Tabs>
      )}
    </div>
  )
}

function ResultTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return <p className="text-sm text-muted-foreground">No data.</p>
  const cols = Object.keys(rows[0])
  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="min-w-full text-sm">
        <thead className="bg-muted">
          <tr>{cols.map((c) => <th key={c} className="px-4 py-2 text-left font-medium text-muted-foreground">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t hover:bg-muted/30">
              {cols.map((c) => <td key={c} className="px-4 py-2">{String(row[c] ?? '')}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
