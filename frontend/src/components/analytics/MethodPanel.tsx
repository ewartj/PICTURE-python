/**
 * MethodPanel — dispatches to the correct analytics component based on `fn`.
 * Adding a new analytics method: import its panel and add one case here.
 */
import type { CohortDefinition } from '@/api/types'
import { FrequencyPanel } from './FrequencyPanel'
import { EventCountPanel } from './EventCountPanel'
import { EventTimePanel } from './EventTimePanel'
import { DemographicsPanel } from './DemographicsPanel'

interface MethodPanelProps {
  fn: string
  params: Record<string, unknown>
  cohortDefinitions: CohortDefinition[]
}

export function MethodPanel({ fn, params, cohortDefinitions }: MethodPanelProps) {
  switch (fn) {
    case 'gen_frequency_analysis':
      return <FrequencyPanel params={params} cohortDefinitions={cohortDefinitions} />
    case 'gen_event_count':
      return <EventCountPanel params={params} cohortDefinitions={cohortDefinitions} />
    case 'gen_event_time_analysis':
      return <EventTimePanel params={params} cohortDefinitions={cohortDefinitions} />
    case 'tpl_pde_all':
      return <DemographicsPanel cohortDefinitions={cohortDefinitions} />
    default:
      return (
        <div className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">
          Analysis method <code className="font-mono">{fn}</code> is not yet implemented in this UI.
        </div>
      )
  }
}
