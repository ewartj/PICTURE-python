import React from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'

import { ChevronRight, User, Database } from 'lucide-react'
import { getApp, resolveCohorts } from '@/api/client'
import type { CohortDefinition, ResolvedCohort } from '@/api/types'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Spinner } from '@/components/ui/spinner'
import { CohortEditor } from '@/components/CohortEditor'
import { CohortSummaryBar } from '@/components/CohortSummaryBar'
import { MethodPanel } from '@/components/analytics/MethodPanel'
import { cn } from '@/lib/utils'

export function AppView() {
  const { appId } = useParams<{ appId: string }>()
  const id = Number(appId)

  const { data: app, isLoading, error } = useQuery({
    queryKey: ['app', id],
    queryFn: () => getApp(id),
    enabled: !isNaN(id),
  })

  const [cohortDefs, setCohortDefs] = React.useState<CohortDefinition[]>([])
  const [resolvedCohorts, setResolvedCohorts] = React.useState<ResolvedCohort[]>([])

  const seeded = React.useRef(false)
  React.useEffect(() => {
    if (app && !seeded.current) {
      seeded.current = true
      setCohortDefs(app.initial_cohorts)
    }
  }, [app])

  const { mutate: resolveInitial, isPending: resolving } = useMutation({
    mutationFn: (defs: CohortDefinition[]) => resolveCohorts({ cohorts: defs }),
    onSuccess: (data) => setResolvedCohorts(data.cohorts),
  })

  React.useEffect(() => {
    if (cohortDefs.length > 0 && resolvedCohorts.length === 0) {
      resolveInitial(cohortDefs)
    }
  }, [cohortDefs]) // eslint-disable-line react-hooks/exhaustive-deps

  const handleCohortsResolved = (cohorts: ResolvedCohort[], defs: CohortDefinition[]) => {
    setResolvedCohorts(cohorts)
    setCohortDefs(defs)
  }

  // ── Loading ──────────────────────────────────────────────────────────────────

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 gap-3 text-muted-foreground">
        <Spinner />
        <span>Loading app…</span>
      </div>
    )
  }

  if (error || !app) {
    return (
      <div className="max-w-2xl mx-auto px-6 py-10">
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
          {error ? (error as Error).message : 'App not found.'}
        </div>
      </div>
    )
  }

  // ── Main render ─────────────────────────────────────────────────────────────

  return (
    <div>
      {/* Page header */}
      <div className="border-b bg-white">
        <div className="max-w-6xl mx-auto px-6 py-5">
          {/* Breadcrumb */}
          <nav className="flex items-center gap-1.5 text-sm text-muted-foreground mb-3">
            <Link to="/" className="hover:text-foreground transition-colors">Apps</Link>
            <ChevronRight className="h-3.5 w-3.5" />
            <span className="text-foreground font-medium truncate">{app.title}</span>
          </nav>

          <div className="flex items-start justify-between gap-6">
            <div>
              <h1 className="text-2xl font-bold mb-1">{app.title}</h1>
              {app.description && (
                <p className="text-sm text-muted-foreground max-w-2xl leading-relaxed">
                  {app.description}
                </p>
              )}
            </div>
            {/* Meta badges */}
            <div className="flex items-center gap-2 shrink-0 mt-1">
              {app.creator && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted rounded-full px-2.5 py-1">
                  <User className="h-3 w-3" />
                  {app.creator}
                </div>
              )}
              {app.dataset && (
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground bg-muted rounded-full px-2.5 py-1">
                  <Database className="h-3 w-3" />
                  {app.dataset}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-6xl mx-auto px-6 py-6 space-y-5">
        {/* Cohort summary strip */}
        <div className="bg-white rounded-xl border p-4">
          <CohortSummaryBar cohorts={resolvedCohorts} isLoading={resolving} />
        </div>

        {/* Main tabs */}
        <div className="bg-white rounded-xl border overflow-hidden">
          <Tabs defaultValue={app.offer_cohort_builder ? '__cohorts__' : (app.analysis[0]?.tab ?? '__cohorts__')}>
            <div className="border-b px-4 pt-3">
              <TabsList className="bg-transparent h-auto gap-0 p-0 flex-wrap">
                {app.offer_cohort_builder && (
                  <AppTab value="__cohorts__" label="Cohorts" />
                )}
                {app.analysis.map((tab) => (
                  <AppTab key={tab.tab} value={tab.tab} label={tab.tab} />
                ))}
              </TabsList>
            </div>

            <div className="p-6">
              {app.offer_cohort_builder && (
                <TabsContent value="__cohorts__">
                  <CohortEditor
                    initialCohorts={cohortDefs}
                    availableRdvs={app.all_rdv_names}
                    onResolved={handleCohortsResolved}
                  />
                </TabsContent>
              )}

              {app.analysis.map((tab) => (
                <TabsContent key={tab.tab} value={tab.tab}>
                  <AnalysisTabContent methods={tab.method_list} cohortDefinitions={cohortDefs} />
                </TabsContent>
              ))}
            </div>
          </Tabs>
        </div>
      </div>
    </div>
  )
}

// ── Custom tab trigger with underline style ───────────────────────────────────

function AppTab({ value, label }: { value: string; label: string }) {
  return (
    <TabsTrigger
      value={value}
      className={cn(
        'rounded-none border-b-2 border-transparent bg-transparent px-4 py-2 text-sm font-medium text-muted-foreground',
        'hover:text-foreground hover:bg-transparent',
        'data-[state=active]:border-primary data-[state=active]:text-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none'
      )}
    >
      {label}
    </TabsTrigger>
  )
}

// ── Analysis tab content ──────────────────────────────────────────────────────

interface AnalysisTabContentProps {
  methods: Array<{ fn: string; params: Record<string, unknown>; tab_lbl: string | null }>
  cohortDefinitions: CohortDefinition[]
}

function AnalysisTabContent({ methods, cohortDefinitions }: AnalysisTabContentProps) {
  if (methods.length === 0) {
    return <p className="text-sm text-muted-foreground">No methods configured for this tab.</p>
  }

  if (methods.length === 1) {
    const m = methods[0]
    return <MethodPanel fn={m.fn} params={m.params} cohortDefinitions={cohortDefinitions} />
  }

  return (
    <Tabs defaultValue={methods[0].fn}>
      <TabsList className="mb-4">
        {methods.map((m) => (
          <TabsTrigger key={m.fn} value={m.fn}>{m.tab_lbl ?? m.fn}</TabsTrigger>
        ))}
      </TabsList>
      {methods.map((m) => (
        <TabsContent key={m.fn} value={m.fn}>
          <MethodPanel fn={m.fn} params={m.params} cohortDefinitions={cohortDefinitions} />
        </TabsContent>
      ))}
    </Tabs>
  )
}
