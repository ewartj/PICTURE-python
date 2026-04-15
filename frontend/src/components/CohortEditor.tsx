/**
 * CohortEditor — lets users build and modify cohort filter chains interactively.
 * Each filter row auto-resolves its patient count as values are entered.
 * The "Resolve cohorts" button pushes the final definitions up to the parent.
 */
import React from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Plus, Trash2, RefreshCw, Users } from 'lucide-react'
import { resolveCohorts, getRdvInfo } from '@/api/client'
import type { CohortDefinition, CohortFilterStep, ResolvedCohort } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Select } from '@/components/ui/select'
import { Spinner } from '@/components/ui/spinner'

const QUERY_TYPES = ['str_matches', 'date_between', 'num_between', 'not_str_matches']
const INCLUSION_TYPES = ['ever', 'never', 'first', 'last']

interface CohortEditorProps {
  initialCohorts: CohortDefinition[]
  availableRdvs: string[]
  onResolved: (cohorts: ResolvedCohort[], definitions: CohortDefinition[]) => void
}

export function CohortEditor({ initialCohorts, availableRdvs, onResolved }: CohortEditorProps) {
  const [cohorts, setCohorts] = React.useState<CohortDefinition[]>(
    initialCohorts.length > 0 ? initialCohorts : [{ label: 'Cohort 1', config: [] }]
  )

  // Sync if parent updates initialCohorts (e.g. on first load)
  const synced = React.useRef(false)
  React.useEffect(() => {
    if (!synced.current && initialCohorts.length > 0) {
      synced.current = true
      setCohorts(initialCohorts)
    }
  }, [initialCohorts])

  const { mutate, isPending, error } = useMutation({
    mutationFn: () => resolveCohorts({ cohorts }),
    onSuccess: (data) => onResolved(data.cohorts, cohorts),
  })

  // ── Cohort-level helpers ────────────────────────────────────────────────────

  const addCohort = () =>
    setCohorts((prev) => [...prev, { label: `Cohort ${prev.length + 1}`, config: [] }])

  const removeCohort = (i: number) =>
    setCohorts((prev) => prev.filter((_, idx) => idx !== i))

  const updateLabel = (i: number, label: string) =>
    setCohorts((prev) => prev.map((c, idx) => (idx === i ? { ...c, label } : c)))

  // ── Filter-level helpers ────────────────────────────────────────────────────

  const addFilter = (ci: number) =>
    setCohorts((prev) =>
      prev.map((c, idx) =>
        idx !== ci
          ? c
          : {
              ...c,
              config: [
                ...c.config,
                {
                  type: 'filter',
                  rdv: availableRdvs[0] ?? '',
                  column: '',
                  query_type: 'str_matches',
                  inclusion: 'ever',
                  val: [],
                  window: null,
                },
              ],
            }
      )
    )

  const removeFilter = (ci: number, fi: number) =>
    setCohorts((prev) =>
      prev.map((c, idx) =>
        idx !== ci ? c : { ...c, config: c.config.filter((_, i) => i !== fi) }
      )
    )

  const updateFilter = (ci: number, fi: number, patch: Partial<CohortFilterStep>) =>
    setCohorts((prev) =>
      prev.map((c, idx) =>
        idx !== ci
          ? c
          : { ...c, config: c.config.map((f, i) => (i === fi ? { ...f, ...patch } : f)) }
      )
    )

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {cohorts.map((cohort, ci) => (
        <div key={ci} className="rounded-lg border p-4 space-y-3">
          {/* Cohort header */}
          <div className="flex items-center gap-2">
            <input
              className="flex-1 h-8 rounded border border-input bg-background px-3 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={cohort.label}
              onChange={(e) => updateLabel(ci, e.target.value)}
            />
            {cohorts.length > 1 && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeCohort(ci)}
                className="h-8 w-8 text-red-500 hover:text-red-600"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>

          {/* Filter rows */}
          {cohort.config.length === 0 && (
            <p className="text-xs text-muted-foreground italic">No filters — all patients included.</p>
          )}

          {cohort.config.map((filter, fi) => (
            <FilterRow
              key={fi}
              filter={filter}
              availableRdvs={availableRdvs}
              // Pass cumulative filters up to this index so the count is meaningful
              cumulativeFilters={cohort.config.slice(0, fi + 1)}
              onUpdate={(patch) => updateFilter(ci, fi, patch)}
              onRemove={() => removeFilter(ci, fi)}
            />
          ))}

          <Button variant="outline" size="sm" onClick={() => addFilter(ci)} className="gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            Add filter
          </Button>
        </div>
      ))}

      <div className="flex items-center gap-3">
        <Button variant="outline" size="sm" onClick={addCohort} className="gap-1.5">
          <Plus className="h-3.5 w-3.5" />
          Add cohort
        </Button>

        <Button size="sm" onClick={() => mutate()} disabled={isPending} className="gap-1.5">
          {isPending ? <Spinner className="h-3.5 w-3.5" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Apply cohorts
        </Button>

        {error && <span className="text-xs text-red-500">{(error as Error).message}</span>}
      </div>
    </div>
  )
}

// ── FilterRow ─────────────────────────────────────────────────────────────────

interface FilterRowProps {
  filter: CohortFilterStep
  availableRdvs: string[]
  cumulativeFilters: CohortFilterStep[]
  onUpdate: (patch: Partial<CohortFilterStep>) => void
  onRemove: () => void
}

function FilterRow({ filter, availableRdvs, cumulativeFilters, onUpdate, onRemove }: FilterRowProps) {
  // val is stored as string[] internally; we show comma-separated in the input
  const valString = (filter.val ?? []).join(', ')

  const handleValChange = (raw: string) => {
    const parsed = raw
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    onUpdate({ val: parsed })
  }

  // Determine if this filter has enough info to resolve a count
  const canResolve = !!(filter.rdv && filter.column && (filter.val ?? []).length > 0)

  return (
    <div className="rounded-md border border-dashed p-3 space-y-2">
      {/* Controls row */}
      <div className="grid grid-cols-[1fr_1fr_1fr_1fr_auto] gap-2 items-end">
        <Select
          label="RDV"
          value={filter.rdv ?? ''}
          onChange={(e) => onUpdate({ rdv: e.target.value })}
        >
          {availableRdvs.map((r) => <option key={r} value={r}>{r}</option>)}
        </Select>

        <ColumnSelect
          rdv={filter.rdv ?? ''}
          value={filter.column ?? ''}
          onChange={(col) => onUpdate({ column: col })}
        />

        <Select
          label="Match type"
          value={filter.query_type}
          onChange={(e) => onUpdate({ query_type: e.target.value })}
        >
          {QUERY_TYPES.map((qt) => <option key={qt} value={qt}>{qt}</option>)}
        </Select>

        <Select
          label="Inclusion"
          value={filter.inclusion}
          onChange={(e) => onUpdate({ inclusion: e.target.value })}
        >
          {INCLUSION_TYPES.map((it) => <option key={it} value={it}>{it}</option>)}
        </Select>

        <Button
          variant="ghost"
          size="icon"
          onClick={onRemove}
          className="text-red-500 hover:text-red-600 mb-0.5"
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>

      {/* Values row + patient count */}
      <div className="flex items-center gap-3">
        <div className="flex flex-col gap-1 flex-1">
          <label className="text-xs font-medium text-muted-foreground">
            Values <span className="text-muted-foreground/60">(comma-separated)</span>
          </label>
          <input
            className="h-9 rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            placeholder='e.g. Female, Male'
            value={valString}
            onChange={(e) => handleValChange(e.target.value)}
          />
        </div>

        {/* Auto-resolved patient count for this filter */}
        <div className="pt-5 shrink-0">
          <FilterPatientCount
            cumulativeFilters={cumulativeFilters}
            enabled={canResolve}
          />
        </div>
      </div>
    </div>
  )
}

// ── ColumnSelect ─────────────────────────────────────────────────────────────

interface ColumnSelectProps {
  rdv: string
  value: string
  onChange: (col: string) => void
}

function ColumnSelect({ rdv, value, onChange }: ColumnSelectProps) {
  const { data, isFetching } = useQuery({
    queryKey: ['rdv-info', rdv],
    queryFn: () => getRdvInfo(rdv),
    enabled: !!rdv,
    staleTime: Infinity, // columns don't change during a session
  })

  const columns = data?.columns ?? []

  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-muted-foreground">
        Column {isFetching && <span className="text-muted-foreground/50">(loading…)</span>}
      </label>
      <select
        className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={columns.length === 0}
      >
        <option value="">{columns.length === 0 ? (isFetching ? 'Loading…' : 'Select RDV first') : 'Select column'}</option>
        {columns.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>
    </div>
  )
}

// ── FilterPatientCount ────────────────────────────────────────────────────────

interface FilterPatientCountProps {
  cumulativeFilters: CohortFilterStep[]
  enabled: boolean
}

function FilterPatientCount({ cumulativeFilters, enabled }: FilterPatientCountProps) {
  const { data, isFetching, isError } = useQuery({
    queryKey: ['filter-count', JSON.stringify(cumulativeFilters)],
    queryFn: () =>
      resolveCohorts({
        cohorts: [{ label: '_count', config: cumulativeFilters }],
      }),
    enabled,
    staleTime: 1000 * 30,
  })

  const count = data?.cohorts[0]

  if (!enabled) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground/50">
        <Users className="h-3.5 w-3.5" />
        —
      </span>
    )
  }

  if (isFetching) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <Spinner className="h-3 w-3" />
        Counting…
      </span>
    )
  }

  if (isError || !count) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-red-400">
        <Users className="h-3.5 w-3.5" />
        error
      </span>
    )
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-sm font-semibold text-primary">
      <Users className="h-3.5 w-3.5" />
      {count.n_patients.toLocaleString()}
      <span className="text-xs font-normal text-muted-foreground">patients</span>
    </span>
  )
}
