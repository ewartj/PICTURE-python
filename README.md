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
│  data/       — load RDVs from Parquet/CSV            │
│  cohort/     — parse YAML filters, resolve cohorts   │
│  analytics/  — compute results, produce Plotly figs  │
│  config/     — parse platform + app YAML config      │
│  prepressr/  — Jinja2 report templating              │
└──────────────────┬──────────────────────┬────────────┘
                   │                      │
       calls directly                calls directly
                   │                      │
┌──────────────────▼──────┐  ┌────────────▼───────────┐
│        api/              │  │        ui/              │
│  (FastAPI — HTTP layer)  │  │  (Streamlit — temp UI)  │
│                          │  │                         │
│  routes/analytics.py     │  │  app.py                 │
│  routes/apps.py          │  │  pages/frequency.py     │
│  routes/cohorts.py       │  │  pages/demographics.py  │
│  routes/data.py          │  │  pages/distribution.py  │
│  deps.py                 │  │                         │
│  schemas/                │  │  calls core/ directly   │
│                          │  │  (skips HTTP)           │
└──────────────────────────┘  └─────────────────────────┘
         ▲
         │  HTTP (JSON)
         ▼
┌─────────────────────┐
│   React (future)    │
│   frontend          │
└─────────────────────┘
```

### `core/` — backend business logic
The backend. No dependency on FastAPI, Streamlit, or HTTP — pure computation. Both `api/` and `ui/` call into it directly. This is the layer that would be deployed on a server.

### `api/` — HTTP interface to `core/`
Exposes `core/` over REST so a decoupled frontend (React) can call it. Handles request validation (Pydantic schemas), dependency injection, routing, and JSON serialisation. Does no computation itself.

| Endpoint | Description |
|---|---|
| `GET /apps` | List all app configs (card gallery data) |
| `GET /apps/{id}` | Full app config — cohorts + analysis tabs |
| `POST /cohorts/resolve` | Resolve cohort definitions against loaded data |
| `POST /analytics/frequency` | Run frequency analysis |
| `GET /data/rdvs` | List available RDVs |
| `GET /data/rdvs/{rdv}` | Preview an RDV |

### `ui/` — temporary Streamlit frontend
Calls `core/` directly (no HTTP) for speed of development. Will be replaced by React, which will call `api/` instead. Because both the UI and the future React frontend use the same `core/` functions (one directly, one via HTTP), switching to React requires no backend changes.

---

## Key concepts

### RDVs (Research Data Views)
Named tabular datasets loaded from Parquet or CSV files. Every RDV has a `project_id` column identifying the patient. The standard RDVs are registered in `core/data/rdv.py`.

### App YAML
A YAML file that defines a complete analysis for a study cohort — see `app/sample_app.yaml` for an example. It specifies:
- **`initialCohorts`** — one or more patient cohorts defined by filter chains (e.g. `sex_name == "Female"`)
- **`analysis`** — tabs and sub-tabs, each pointing to an analytics function and its parameters
- **`outputs`** — whether to produce an interactive UI and/or a PDF report

The platform config (`config/config.yaml`) points to the directory containing app YAMLs and the RDV data directory. These are kept separate so app configs can live locally while data is loaded from a remote/cloud location.

### Cohort resolution
Cohorts are defined in the app YAML as filter chains and resolved against the loaded RDVs at startup. Resolution (`core/cohort/filters.py`) produces a patient list with `entry_date` / `exit_date` windows per patient. Every analytics module then receives the RDV pre-filtered and labelled with cohort names via `apply_cohorts_to_rdv()`.

### Analytics modules
Each module in `core/analytics/` follows the same interface (defined by `AnalysisBase`):
- `compute()` — runs the analysis, stores results
- `plot()` — returns a Plotly figure
- `to_dict()` — returns a JSON-serialisable dict (what the API returns to React)

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

### Install
```bash
pip install -e ".[dev]"
```

### Enable git hooks
```bash
git config core.hooksPath hooks/
```

This activates the pre-commit pipeline (ruff, mypy, AI review). To skip on a single commit: `git commit --no-verify`.

### Configure
Edit `config/config.yaml`:
```yaml
default:
  data_dir: /path/to/rdv/data      # folder containing Parquet/CSV RDV files
  app_dir:  /path/to/app/yamls     # folder containing app YAML definitions
```

### Streamlit UI (temporary)
```bash
streamlit run ui/app.py
```
Opens at `http://localhost:8501`. The sidebar is pre-populated from `config.yaml`. The home screen shows a card for each app YAML found in `app_dir`; clicking **Open** resolves cohorts and renders the analysis tabs.

### API server
```bash
uvicorn api.main:app --reload --port 8000
```
Interactive docs at `http://localhost:8000/docs`.

### Tests
```bash
pytest
```

---

## Project layout

```
picture-python/
├── config/
│   └── config.yaml          # platform config (data_dir, app_dir, etc.)
├── app/
│   └── sample_app.yaml      # example app YAML definition
├── core/
│   ├── analytics/           # analytics modules (AnalysisBase subclasses)
│   ├── cohort/              # cohort models + filter resolution engine
│   ├── config/              # app YAML + platform config parsers
│   ├── data/                # RDV loader + schema registry
│   └── prepressr/           # Jinja2 report template preprocessor
├── api/
│   ├── main.py              # FastAPI app factory
│   ├── deps.py              # dependency injection (config, data loading)
│   ├── routes/              # endpoint handlers
│   └── schemas/             # Pydantic request/response models
├── ui/
│   ├── app.py               # Streamlit app (home screen + analysis view)
│   └── pages/               # one file per analytics module
├── tests/
│   ├── core/                # unit tests for analytics + cohort filters
│   └── api/                 # integration tests using FastAPI TestClient
└── pyproject.toml
```

## AI Agents

Three specialist agents are defined in `.claude/agents/` and are available in any Claude Code session:

| Agent | Triggers on |
|---|---|
| `code-reviewer` | "review this file", "check for security issues" |
| `backend-architect` | "design an endpoint", "how should I structure this module" |
| `ui-designer` | "improve this component", "plan the React migration" |

Claude automatically routes to the right agent based on your prompt, or you can call one explicitly: *"Use the code-reviewer agent to check `core/analytics/frequency.py`"*.

### Automated code review (`review.sh`)

Three agents (security/PHI, architecture, code quality) run in parallel against your changes. The pre-commit hook calls `review.sh --block-on-issues` automatically on every `git commit`, blocking the commit if any BLOCK-level issue is found.

Run manually at any time:

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