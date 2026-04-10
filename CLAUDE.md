# PICTURE — Python Port

**P**ersonalised **I**nformatics **C**onsul**T**ation **U**sing **R**eal-world **E**vidence

A Python port of the PICTURE R platform by GOSH DRIVE. Analyses structured hospital data to support paediatric clinical decision-making.

## Claude Code Setup

- Pre-commit hook runs 3 AI review agents (security/PHI, architecture, code quality) on every `git commit`
- `.claude/settings.json` — hooks that trigger agents on file edits within Claude Code
- `.mcp.json` — GitHub MCP server config (gitignored — copy from `.mcp.json.example` and add your PAT)

## Architecture

```
core/          — pure Python, no HTTP, no UI, no framework
  data/        — load RDVs from Parquet/CSV
  cohort/      — parse YAML filters, resolve cohorts (filters.py)
  analytics/   — compute results, produce Plotly figures (AnalysisBase interface)
  config/      — parse platform + app YAML config
  prepressr/   — Jinja2 report templating

api/           — FastAPI HTTP layer over core/ (Pydantic schemas, routing, JSON serialisation)
ui/            — Streamlit frontend (temporary, calls core/ directly, will be replaced by React)
app/           — App YAML configs
config/        — Platform config (config.yaml points to app YAMLs and RDV data dir)
tests/
```

- `core/` has no dependency on FastAPI or Streamlit — it is the only layer deployed server-side.
- Both `api/` and `ui/` call `core/` directly. Switching from Streamlit to React requires no backend changes.
- React (future) will call `api/` over HTTP. Streamlit (current) skips HTTP and calls `core/` directly.

## Key Concepts

**RDVs (Research Data Views)** — named tabular datasets from Parquet/CSV. Every RDV has a `project_id` column. Registered in `core/data/rdv.py`.

**App YAML** — defines a complete analysis: `initialCohorts` (filter chains), `analysis` (tabs → analytics functions), `outputs` (UI / PDF). See `app/sample_app.yaml`.

**Cohort resolution** — `core/cohort/filters.py` resolves YAML filter chains against RDVs, producing patient lists with `entry_date`/`exit_date` windows. Analytics modules receive pre-filtered, cohort-labelled RDVs via `apply_cohorts_to_rdv()`.

**Analytics interface** — every module in `core/analytics/` implements `AnalysisBase`:
- `compute()` — runs analysis, stores results
- `plot()` — returns a Plotly figure
- `to_dict()` — returns JSON-serialisable dict (what the API sends to React)

## API Endpoints (api/)

| Method | Path | Description |
|---|---|---|
| GET | `/apps` | List all app configs |
| GET | `/apps/{id}` | Full app config — cohorts + analysis tabs |
| POST | `/cohorts/resolve` | Resolve cohort definitions against loaded data |
| POST | `/analytics/frequency` | Run frequency analysis |
| GET | `/data/rdvs` | List available RDVs |
| GET | `/data/rdvs/{rdv}` | Preview an RDV |

## Analytics Modules

| Module | Function | Status |
|---|---|---|
| Frequency | `gen_frequency_analysis` | Implemented |
| Demographics | `tpl_pde_all` | Implemented |
| Distribution | `gen_distribution_plots` | Implemented |
| Correlation, Time series, Event time/count, Hierarchical, Location | various | Stub (501) |

## Stack

- Python 3.11+
- FastAPI + Uvicorn, Pydantic v2 (API layer)
- Streamlit (temporary UI)
- pandas, polars, scipy, lifelines, prophet, plotly, geopandas
- PyYAML, structlog
- Tests: pytest + pytest-asyncio, httpx (AsyncClient for FastAPI tests)
- Formatting: black (line-length 100, py311), mypy (non-strict)

## Code Standards

- Keep `core/` free of FastAPI, Streamlit, and HTTP imports
- Analytics modules must implement the full `AnalysisBase` interface
- API layer does no computation — delegate everything to `core/`
- Use Pydantic v2 schemas for all API request/response validation
- Line length: 100, target Python 3.11
- Run `black .` and `mypy` before committing
