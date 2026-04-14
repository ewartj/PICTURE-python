import { Link, useLocation } from 'react-router-dom'
import { Activity } from 'lucide-react'

export function Header() {
  const location = useLocation()
  const isHome = location.pathname === '/'

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-white/80 backdrop-blur-sm">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center gap-4">
        <Link to="/" className="flex items-center gap-2.5 shrink-0">
          <div className="h-7 w-7 rounded-lg bg-primary flex items-center justify-center">
            <Activity className="h-4 w-4 text-white" />
          </div>
          <span className="font-bold text-base tracking-tight">PICTURE</span>
        </Link>

        <div className="h-4 w-px bg-border mx-1" />

        <span className="text-sm text-muted-foreground hidden sm:block">
          {isHome ? 'App Gallery' : 'Analytics'}
        </span>
      </div>
    </header>
  )
}
