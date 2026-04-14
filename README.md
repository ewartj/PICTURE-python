# PICTURE — Python Port

**P**ersonalised **I**nformatics **C**onsul**T**ation **U**sing **R**eal-world **E**vidence

A Python port of the [PICTURE R platform](https://github.com/gosh-dre/picture.platform) developed by GOSH DRIVE (Great Ormond Street Hospital's Data Research, Innovation and Virtual Environments unit). PICTURE analyses structured hospital data to support paediatric clinical decision-making.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                     core/                            │
│  (pure Python — no HTTP, no UI, no framework)        │
│                                                      │
│  data/       — load RDVs from Parquet/CSV/Postgres   │
│  cohort/     — parse YAML filters, resolve cohorts   │
│  analytics/  — compute results, produce Plotly figs  │
│  config/     — parse platform + app YAML config      │
│  prepressr/  — Jinja2 report templating              │
└──────────────────────────┬──────────────────────────┘
                           │
                    calls directly
                           │
           ┌───────────────▼───────────────┐
           │            api/               │
           │   (FastAPI — HTTP layer)       │
           │                               │
           │   routes/analytics.py         │
           │   routes/apps.py              │
           │   routes/cohorts.py           │
           │   routes/data.py              │
           │   deps.py                     │
           │   schemas/                    │
           └───────────────┬───────────────┘
                           │ HTTP (JSON)
                           │
           ┌───────────────▼───────────────┐
           │          frontend/            │
           │  React + TypeScript + Vite    │
           │                               │
           │  App gallery → app view       │
           │  Cohort editor                │
           │  Analytics panels             │
           └───────────────────────────────┘
```

### `core/` — backend business logic
The backend. No dependency on FastAPI or HTTP — pure computation. This is the layer that runs on the server.

### `api/` — HTTP interface to `core/`
Exposes `core/` over REST. Handles request validation (Pydantic schemas), dependency injection, routing, and JSON serialisation.

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `GET /apps` | List all app configs (card gallery data) |
| `GET /apps/{id}` | Full app config — cohorts + analysis tabs |
| `POST /cohorts/resolve` | Resolve cohort definitions against loaded data |
| `POST /analytics/frequency` | Run frequency analysis |
| `POST /analytics/demographics` | Run demographics analysis |
| `POST /analytics/distribution` | Run distribution plots |
| `GET /data/rdvs` | List available RDVs |
| `GET /data/rdvs/{rdv}` | Column names + preview rows for an RDV |

### `frontend/` — React UI
A TypeScript single-page application built with Vite. It calls `api/` over HTTP and renders an interactive analytics explorer.

**Stack:** React 18 · TypeScript · Vite 5 · Tailwind CSS · shadcn-style components · TanStack Query · React Router · react-plotly.js

Key features:
- App gallery — colour-coded cards with hover animation
- Per-app analysis view with tabbed panels
- Cohort editor — build patient cohorts from filter chains, with live patient counts and column dropdowns populated from the API
- Plotly charts rendered with titles extracted to prevent overlap
- Cohort colour pills shown across all panels

---

## Key concepts

### RDVs (Research Data Views)
Named tabular datasets loaded from Parquet, CSV, or Postgres. Every RDV has a `project_id` column identifying the patient. The standard RDVs are registered in `core/data/rdv.py`.

### App YAML
A YAML file that defines a complete analysis for a study — see `app/sample_app.yaml` for an example. It specifies:
- **`initialCohorts`** — one or more patient cohorts defined by filter chains (e.g. `sex_name == "Female"`)
- **`analysis`** — tabs and sub-tabs, each pointing to an analytics function and its parameters
- **`outputs`** — whether to produce an interactive UI and/or a PDF report

The platform config (`config/config.yaml`) points to the directory containing app YAMLs and the RDV data directory.

### Cohort resolution
Cohorts are defined in the app YAML as filter chains and resolved against the loaded RDVs at startup. Resolution (`core/cohort/filters.py`) produces a patient list with `entry_date` / `exit_date` windows per patient. Every analytics module receives the RDV pre-filtered and labelled with cohort names via `apply_cohorts_to_rdv()`.

### Analytics modules
Each module in `core/analytics/` follows the same interface (defined by `AnalysisBase`):
- `compute()` — runs the analysis, stores results
- `plot()` — returns a Plotly figure
- `to_dict()` — returns a JSON-serialisable dict (what the API returns to the frontend)

| Module | Function name | Status |
|---|---|---|
| Frequency | `gen_frequency_analysis` | Implemented |
| Demographics template | `tpl_pde_all` | Implemented |
| Distribution plots | `gen_distribution_plots` | Implemented |
| Correlation | `gen_correlation_analysis` | Stub (501) |
| Time series | `gen_timeseries_analysis` | Stub (501) |
| Time series decomposition | `gen_timeseries_decomposition` | Stub (501) |
| Event time | `gen_event_time_analysis` | Stub (501) |
| Event count | `gen_event_count` | Stub (501) |
| Hierarchical | `gen_hierarchical_data_plots` | Stub (501) |
| Location | `gen_location_analysis` | Stub (501) |
| Recurrence | `gen_recurrence_analysis` | Stub (501) |
| Value variability | `gen_value_variability_analysis` | Stub (501) |

---

## Running the app

### Option A — Docker (recommended)

The full stack runs as three containers (React frontend, FastAPI backend, Postgres) orchestrated by Docker Compose.

#### First-time setup

```bash
# 1. Configure environment
cp .env.example .env          # edit POSTGRES_PASSWORD if needed

# 2. Build and load RDV data into Postgres
docker compose --profile migrate up --exit-code-from migrate migrate

# 3. Start the app
docker compose up
```

| Service | URL |
|---|---|
| React frontend | http://localhost:3000 |
| FastAPI (REST + docs) | http://localhost:8000/docs |

Postgres is not exposed outside the Docker network. To connect directly:
```bash
docker compose exec db psql -U picture -d picture
```

#### Every subsequent run

```bash
docker compose up
```

The `postgres_data` volume persists the database between restarts. Only `docker compose down -v` deletes it.

#### Re-loading data (new CSV/Parquet files)

```bash
docker compose --profile migrate up --exit-code-from migrate migrate
```

---

### Option B — Local (development)

#### Install Python dependencies
```bash
pip install -e ".[dev]"
```

#### Install frontend dependencies
```bash
cd frontend && npm install
```

#### Enable git hooks
```bash
git config core.hooksPath hooks/
```

This activates the pre-commit pipeline (black, mypy, AI review). To skip on a single commit: `git commit --no-verify`.

#### Configure
Edit `config/config.yaml`:
```yaml
default:
  data_dir: /path/to/rdv/data      # folder containing Parquet/CSV RDV files
  app_dir:  /path/to/app/yamls     # folder containing app YAML definitions
```

To use Postgres instead of flat files, set `backend: postgres` and `db_url` in `config/config.yaml`, or use environment variables:
```bash
export PICTURE_BACKEND=postgres
export DATABASE_URL=postgresql://user:pass@localhost:5432/picture
```

Load flat files into Postgres once with:
```bash
python scripts/load_to_postgres.py --data-dir data/dmv/csv --db-url $DATABASE_URL
```

#### API server
```bash
uvicorn api.main:app --reload --port 8000
```
Interactive docs at `http://localhost:8000/docs`.

#### Frontend dev server
```bash
cd frontend && npm run dev
```
Opens at `http://localhost:5173`. API calls are proxied to `http://localhost:8000`.

---

## Testing

### Python tests

The Python test suite uses in-memory DataFrames — no database or running server needed.

```bash
# Run all tests
pytest

# With coverage
pytest --cov=core --cov=api

# A specific file
pytest tests/test_integration.py
```

| Test file | What it covers |
|---|---|
| `tests/test_integration.py` | Full pipeline: YAML cohort → resolve → analytics → `to_dict()` |
| `tests/api/test_analytics_routes.py` | FastAPI routes via TestClient + cohort resolve |
| `tests/core/test_frequency.py` | Frequency analysis computation |
| `tests/core/test_event_count.py` | Event count distribution |
| `tests/core/test_event_time.py` | Event timing analysis |
| `tests/core/test_cohort_filters.py` | Cohort filter resolution |
| `tests/core/test_cohort_filters_window.py` | Temporal window filters |
| `tests/core/test_categorical_ratios.py` | Categorical ratio computation |
| `tests/core/test_cohort_formatting.py` | Cohort output formatting |
| `tests/core/test_result_formatting.py` | Analytics result formatting |
| `tests/core/test_analytics_runner.py` | Service layer orchestration |
| `tests/core/test_app_config.py` | App YAML parsing |
| `tests/core/test_rdv_lookups.py` | RDV schema registry |

### Frontend tests

Frontend tests use Vitest + React Testing Library with a jsdom environment. react-plotly.js is stubbed so charts render without a real DOM canvas.

```bash
cd frontend && npm test
```

| Test file | What it covers |
|---|---|
| `src/api/client.test.ts` | API client — correct field names, error handling |
| `src/components/PlotlyChart.test.tsx` | Chart title extraction (string/object/absent) |
| `src/components/CohortSummaryBar.test.tsx` | Loading/empty/resolved states, colour cycling |
| `src/components/analytics/MethodPanel.test.tsx` | Analytics panel routing by `fn` value |

### Running tests inside Docker

```bash
docker compose exec backend pytest
```

### Smoke-testing the running stack

**Check the API is up:**
```bash
curl -s http://localhost:8000/health
```

**List available RDVs:**
```bash
curl -s http://localhost:8000/data/rdvs | python -m json.tool
```

**Run a frequency analysis:**
```bash
curl -s -X POST http://localhost:8000/analytics/frequency \
  -H "Content-Type: application/json" \
  -d '{
    "rdv": "dia",
    "event_col": "diag_name",
    "cohort_definitions": []
  }' | python -m json.tool
```

---

## CI / CD

GitHub Actions runs two parallel jobs on every push and pull request to `main`/`master`:

| Job | Steps |
|---|---|
| `test` (Python) | black formatting check · mypy type check · pytest |
| `frontend-test` | ESLint · tsc type check · vitest · production build |

Both jobs must pass before a PR can be merged.

---

## Project layout

```
picture-python/
├── config/
│   └── config.yaml          # platform config (data_dir, backend, db_url, etc.)
├── app/
│   └── sample_app.yaml      # example app YAML definition
├── core/
│   ├── analytics/           # analytics modules (AnalysisBase subclasses)
│   ├── cohort/              # cohort models + filter resolution engine
│   ├── config/              # app YAML + platform config parsers
│   ├── data/
│   │   ├── provider.py      # DataProvider protocol (backend-agnostic interface)
│   │   ├── loader.py        # CSV/Parquet loading helpers
│   │   ├── rdv.py           # RDV schema registry
│   │   └── providers/
│   │       ├── file.py      # FileProvider  — reads CSV/Parquet files
│   │       └── postgres.py  # PostgresProvider — reads from Postgres via SQLAlchemy
│   └── prepressr/           # Jinja2 report template preprocessor
├── api/
│   ├── main.py              # FastAPI app factory
│   ├── deps.py              # dependency injection (config, provider factory)
│   ├── routes/              # endpoint handlers
│   └── schemas/             # Pydantic request/response models
├── frontend/
│   ├── src/
│   │   ├── api/             # typed API client (client.ts + types.ts)
│   │   ├── components/      # shared UI components (charts, cohort editor, etc.)
│   │   ├── components/ui/   # base UI primitives (Button, Badge, etc.)
│   │   ├── pages/           # AppGallery and AppView page components
│   │   └── test/            # Vitest setup, render helpers, mocks
│   ├── Dockerfile           # multi-stage build (Node 20 → nginx)
│   ├── nginx.conf           # serves React + proxies /api/* to backend
│   ├── vite.config.ts       # build config, path aliases, test config
│   └── package.json
├── db/
│   └── schema.sql           # Postgres DDL for all RDV tables + indexes
├── scripts/
│   └── load_to_postgres.py  # one-time migration: flat files → Postgres
├── tests/
│   ├── core/                # unit tests for analytics + cohort filters
│   └── api/                 # integration tests using FastAPI TestClient
├── .github/
│   └── workflows/
│       └── tests.yml        # CI: parallel Python + frontend jobs
├── Dockerfile               # Python image used by backend + migrate services
├── docker-compose.yml       # backend + frontend + db + migrate (profile)
├── .env.example             # environment variable template
└── pyproject.toml
```

---

## AI Agents

Three specialist agents are defined in `.claude/agents/` and are available in any Claude Code session:

| Agent | Triggers on |
|---|---|
| `code-reviewer` | "review this file", "check for security issues" |
| `backend-architect` | "design an endpoint", "how should I structure this module" |
| `ui-designer` | "improve this component", "plan a new page" |

Claude automatically routes to the right agent based on your prompt, or you can call one explicitly: *"Use the code-reviewer agent to check `core/analytics/frequency.py`"*.

### Automated code review (`review.sh`)

Three agents (security/PHI, architecture, code quality) run in parallel against your changes. The pre-commit hook calls `review.sh --block-on-issues` automatically on every `git commit`, blocking the commit if any BLOCK-level issue is found.

```bash
# Review staged changes
git add <file>
./review.sh

# Review a specific commit
./review.sh --commit <sha>

# Review a branch vs master
./review.sh --branch <branch-name>

# Review all Python files in a folder
./review.sh --folder core/analytics/
```

To skip the review in an emergency:
```bash
git commit --no-verify -m "emergency fix"
```
