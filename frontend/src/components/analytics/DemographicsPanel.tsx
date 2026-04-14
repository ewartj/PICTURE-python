import { useQuery } from '@tanstack/react-query'
import { runCohortCharacteristics } from '@/api/client'
import type { CohortDefinition } from '@/api/types'
import { PlotlyChart } from '@/components/PlotlyChart'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Spinner } from '@/components/ui/spinner'

// ---------------------------------------------------------------------------
// Table with section headers derived from the "grouping" column
// ---------------------------------------------------------------------------

function DemographicsTable({ rows }: { rows: Record<string, string>[] }) {
  // Cohort columns are every key that is not the internal grouping/Characteristic keys
  const cohortCols = rows.length > 0
    ? Object.keys(rows[0]).filter((k) => k !== 'grouping' && k !== 'Characteristic')
    : []

  let lastGrouping = ''

  return (
    <div className="overflow-x-auto rounded-md border">
      <table className="min-w-full text-sm">
        <thead className="bg-muted">
          <tr>
            <th className="px-4 py-2 text-left font-medium text-muted-foreground">Characteristic</th>
            {cohortCols.map((c) => (
              <th key={c} className="px-4 py-2 text-left font-medium text-muted-foreground">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => {
            const grouping = row['grouping'] ?? ''
            const isNewGroup = grouping !== lastGrouping
            if (isNewGroup) lastGrouping = grouping

            return [
              isNewGroup && grouping ? (
                <tr key={`group-${i}`} className="bg-muted/60 border-t">
                  <td
                    colSpan={1 + cohortCols.length}
                    className="px-4 py-1 text-xs font-semibold text-foreground uppercase tracking-wide"
                  >
                    {grouping}
                  </td>
                </tr>
              ) : null,
              <tr key={i} className="border-t hover:bg-muted/30">
                <td className="px-4 py-2 pl-6 text-muted-foreground">{row['Characteristic'] ?? ''}</td>
                {cohortCols.map((c) => (
                  <td key={c} className="px-4 py-2">{String(row[c] ?? '')}</td>
                ))}
              </tr>,
            ]
          })}
        </tbody>
      </table>
    </div>
  )
}

// ---------------------------------------------------------------------------

interface DemographicsPanelProps {
  cohortDefinitions: CohortDefinition[]
}

export function DemographicsPanel({ cohortDefinitions }: DemographicsPanelProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['analytics', 'cohort-characteristics', cohortDefinitions],
    queryFn: () => runCohortCharacteristics({ cohort_definitions: cohortDefinitions }),
    enabled: cohortDefinitions.length > 0,
  })

  if (isLoading) return <div className="flex gap-2 items-center text-muted-foreground text-sm"><Spinner className="h-4 w-4" />Running…</div>
  if (error) return <p className="text-sm text-red-500">{(error as Error).message}</p>
  if (!data) return null

  return (
    <Tabs defaultValue="chart">
      <TabsList>
        <TabsTrigger value="chart">Chart</TabsTrigger>
        <TabsTrigger value="table">Table</TabsTrigger>
      </TabsList>
      <TabsContent value="chart">
        <PlotlyChart plotJson={data.plot} style={{ width: '100%', height: 'auto', minHeight: '400px' }} />
      </TabsContent>
      <TabsContent value="table">
        {data.table.length === 0 ? (
          <p className="text-sm text-muted-foreground">No data.</p>
        ) : (
          <DemographicsTable rows={data.table as Record<string, string>[]} />
        )}
      </TabsContent>
    </Tabs>
  )
}
