import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { User, Database, ArrowRight, LayoutGrid } from 'lucide-react'
import { listApps } from '@/api/client'
import type { AppConfigSummary } from '@/api/types'
import { Badge } from '@/components/ui/badge'
import { Spinner } from '@/components/ui/spinner'
import { cn } from '@/lib/utils'

// One accent colour per card (cycles through)
const CARD_ACCENTS = [
  'from-blue-500 to-indigo-600',
  'from-emerald-500 to-teal-600',
  'from-violet-500 to-purple-600',
  'from-orange-500 to-amber-600',
  'from-rose-500 to-pink-600',
  'from-cyan-500 to-sky-600',
]

export function AppGallery() {
  const navigate = useNavigate()
  const { data: apps, isLoading, error } = useQuery({
    queryKey: ['apps'],
    queryFn: listApps,
  })

  return (
    <div>
      {/* Hero banner */}
      <div className="bg-gradient-to-br from-primary/90 via-primary to-indigo-700 text-white">
        <div className="max-w-6xl mx-auto px-6 py-14">
          <p className="text-primary-foreground/70 text-sm font-medium uppercase tracking-widest mb-3">
            GOSH DRIVE · Clinical Analytics
          </p>
          <h1 className="text-4xl font-bold mb-3 leading-tight">
            Personalised Informatics<br />Consultation
          </h1>
          <p className="text-primary-foreground/80 text-base max-w-xl">
            Explore real-world evidence from hospital records. Select a study app below to begin.
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-6 py-10">

        {/* Section header */}
        <div className="flex items-center gap-2 mb-6">
          <LayoutGrid className="h-4 w-4 text-muted-foreground" />
          <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
            Available Apps
          </h2>
          {apps && (
            <span className="ml-auto text-xs text-muted-foreground">{apps.length} apps</span>
          )}
        </div>

        {/* States */}
        {isLoading && (
          <div className="flex items-center gap-3 text-muted-foreground py-12 justify-center">
            <Spinner />
            <span>Loading apps…</span>
          </div>
        )}

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
            <strong>Could not connect to backend.</strong>
            <p className="mt-1 text-red-600">{(error as Error).message}</p>
          </div>
        )}

        {apps && apps.length === 0 && (
          <div className="text-center py-16 text-muted-foreground">
            <LayoutGrid className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p className="font-medium">No apps found</p>
            <p className="text-sm mt-1">Add YAML files to the app directory to get started.</p>
          </div>
        )}

        {/* App grid */}
        {apps && apps.length > 0 && (
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {apps.map((app, i) => (
              <AppCard
                key={app.id}
                app={app}
                accent={CARD_ACCENTS[i % CARD_ACCENTS.length]}
                onOpen={() => navigate(`/apps/${app.id}`)}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

interface AppCardProps {
  app: AppConfigSummary
  accent: string
  onOpen: () => void
}

function AppCard({ app, accent, onOpen }: AppCardProps) {
  // Initials from title for the avatar
  const initials = app.title
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase()

  return (
    <button
      onClick={onOpen}
      className={cn(
        'group text-left bg-white rounded-xl border shadow-sm overflow-hidden',
        'hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
      )}
    >
      {/* Coloured accent bar + avatar */}
      <div className={cn('h-2 w-full bg-gradient-to-r', accent)} />

      <div className="p-5">
        {/* Title row */}
        <div className="flex items-start gap-3 mb-3">
          <div className={cn('h-9 w-9 rounded-lg bg-gradient-to-br shrink-0 flex items-center justify-center text-white text-sm font-bold', accent)}>
            {initials}
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-sm leading-snug text-foreground group-hover:text-primary transition-colors line-clamp-2">
              {app.title}
            </h3>
          </div>
        </div>

        {/* Description */}
        {app.description && (
          <p className="text-xs text-muted-foreground line-clamp-3 mb-4 leading-relaxed">
            {app.description}
          </p>
        )}

        {/* Meta + CTA */}
        <div className="flex items-center justify-between mt-auto">
          <div className="flex flex-col gap-1">
            {app.creator && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <User className="h-3 w-3" />
                <span className="truncate max-w-[120px]">{app.creator}</span>
              </div>
            )}
            {app.dataset && (
              <div className="flex items-center gap-1">
                <Database className="h-3 w-3 text-muted-foreground" />
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">{app.dataset}</Badge>
              </div>
            )}
          </div>
          <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all shrink-0" />
        </div>
      </div>
    </button>
  )
}
