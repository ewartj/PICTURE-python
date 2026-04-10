"""Data introspection endpoints — list and describe available RDVs."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from api.deps import get_data_dir, get_rdvs
from api.schemas.analytics import RdvInfoResponse, RdvListResponse
from core.data.rdv import RDV_FILE_MAP, RDV_SCHEMAS

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/rdvs", response_model=RdvListResponse)
def list_rdvs(data_dir: Path = Depends(get_data_dir)):
    """Return RDV names that have a data file in data_dir."""
    available = []
    for rdv, stem in RDV_FILE_MAP.items():
        if (data_dir / f"{stem}.parquet").exists() or (
            data_dir / f"{stem}.csv"
        ).exists():
            available.append(rdv)
    return RdvListResponse(available=available)


@router.get("/rdvs/{rdv}", response_model=RdvInfoResponse)
def describe_rdv(
    rdv: str,
    rdvs: dict = Depends(get_rdvs),
):
    """Return row count and column names for a specific RDV."""
    if rdv not in rdvs:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail=f"RDV '{rdv}' not available.")

    df = rdvs[rdv]
    schema = RDV_SCHEMAS.get(rdv)
    return RdvInfoResponse(
        name=rdv,
        label=schema.label if schema else rdv,
        n_rows=len(df),
        columns=list(df.columns),
    )
