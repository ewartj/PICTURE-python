# PICTURE — React Frontend

React + TypeScript + Vite frontend for the PICTURE clinical analytics platform.

## Stack

| Library | Purpose |
|---|---|
| React 18 | UI framework |
| TypeScript | Type safety |
| Vite 5 | Dev server + bundler |
| Tailwind CSS v3 | Utility-first styling |
| TanStack Query v5 | Server state / data fetching |
| React Router v6 | Client-side routing |
| react-plotly.js | Interactive charts |
| Vitest + RTL | Unit testing |

## Development

```bash
npm install
npm run dev        # dev server at http://localhost:5173 (proxies /api/* to :8000)
npm test           # run Vitest tests
npm run build      # production build to dist/
npm run lint       # ESLint
```

## Architecture

```
src/
├── api/
│   ├── client.ts       # all API calls (typed wrappers around fetch)
│   └── types.ts        # shared request/response types
├── components/
│   ├── ui/             # base primitives: Button, Badge, etc.
│   ├── analytics/      # per-analysis-function panels + MethodPanel router
│   ├── CohortEditor    # cohort builder with filter chains + live patient counts
│   ├── CohortSummaryBar# colour-coded cohort pills
│   ├── Header          # sticky frosted-glass navbar
│   └── PlotlyChart     # Plotly wrapper (title extracted to HTML)
├── pages/
│   ├── AppGallery.tsx  # landing page — app cards
│   └── AppView.tsx     # per-app view — cohort editor + tabbed analysis panels
└── test/
    ├── setup.ts        # @testing-library/jest-dom matchers
    ├── utils.tsx       # renderWithProviders (QueryClient + MemoryRouter)
    └── mocks/
        └── react-plotly.tsx  # lightweight stub for jsdom tests
```

## Production

In Docker, the frontend is built to static files and served by nginx. API calls to `/api/*` are proxied to the `backend` container. See [Dockerfile](Dockerfile) and [nginx.conf](nginx.conf).
