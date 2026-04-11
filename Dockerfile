# Single image used by backend, frontend, and migrate services.
# The command is overridden per-service in docker-compose.yml.
#
# System packages:
#   libgeos-dev / libproj-dev / libgdal-dev  — required by geopandas/shapely
#   libpq-dev / gcc                          — required to compile psycopg2
#                                              (not needed for psycopg2-binary,
#                                              but kept for flexibility)

FROM python:3.11-slim

# Install system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgeos-dev \
        libproj-dev \
        libgdal-dev \
        gdal-bin \
        libpq-dev \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dependency layer (rebuilt only when pyproject.toml changes) ──────────────
COPY pyproject.toml .

# Install all declared dependencies directly (no editable install needed in
# Docker — source is copied below and made importable via PYTHONPATH).
# prophet is excluded: its pystan dependency requires a full build toolchain
# and is not needed for the core analytics. Add it back if required.
RUN pip install --no-cache-dir \
    "pandas>=2.0" \
    "pyarrow>=14.0" \
    "polars-lts-cpu>=1.33.1" \
    "scipy>=1.11" \
    "lifelines>=0.27" \
    "plotly>=5.18" \
    "matplotlib>=3.8" \
    "seaborn>=0.13" \
    "geopandas>=0.14" \
    "shapely>=2.0" \
    "folium>=0.15" \
    "python-dateutil>=2.8" \
    "fastapi>=0.110" \
    "uvicorn[standard]>=0.27" \
    "pydantic>=2.6" \
    "pydantic-settings>=2.2" \
    "streamlit>=1.32" \
    "pyyaml>=6.0" \
    "structlog>=24.1" \
    "python-multipart>=0.0.9" \
    "sqlalchemy>=2.0" \
    "psycopg2-binary>=2.9"

# ── Application source ────────────────────────────────────────────────────────
COPY . .

# Make local packages (core, api, ui) importable without editable install
ENV PYTHONPATH=/app
