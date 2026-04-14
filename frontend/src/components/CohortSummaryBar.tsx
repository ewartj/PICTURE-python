import type { ResolvedCohort } from '@/api/types'
import { Users } from 'lucide-react'
import { cn } from '@/lib/utils'

const COHORT_COLORS = [
  'cohort-color-0',
  'cohort-color-1',
  'cohort-color-2',
  'cohort-color-3',
  'cohort-color-4',
]

interface CohortSummaryBarProps {
  cohorts: ResolvedCohort[]
  isLoading: boolean
}

export function CohortSummaryBar({ cohorts, isLoading }: CohortSummaryBarProps) {
  if (isLoading) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted border-t-primary" />
        Resolving cohorts…
      </div>
    )
  }

  if (cohorts.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Users className="h-4 w-4" />
        No cohorts resolved yet
      </div>
    )
  }

  return (
    <div className="flex flex-wrap items-center gap-3">
      <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">
        <Users className="h-3.5 w-3.5" />
        Cohorts
      </div>
      <div className="h-4 w-px bg-border" />
      {cohorts.map((c, i) => (
        <div
          key={c.label}
          className={cn(
            'flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium',
            COHORT_COLORS[i % COHORT_COLORS.length]
          )}
        >
          <span>{c.label}</span>
          <span className="font-bold">{c.n_patients.toLocaleString()}</span>
          <span className="opacity-70">pts</span>
          <span className="opacity-50">·</span>
          <span className="opacity-70">{c.n_periods.toLocaleString()} periods</span>
        </div>
      ))}
    </div>
  )
}
