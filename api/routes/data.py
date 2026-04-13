"""Data introspection endpoints — list and describe available RDVs."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends

from api.deps import get_data_provider, get_rdvs
from api.schemas.analytics import RdvInfoResponse, RdvListResponse
from core.data.provider import DataProvider
from core.data.rdv import RDV_SCHEMAS

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/rdvs", response_model=RdvListResponse)
def list_rdvs(provider: DataProvider = Depends(get_data_provider)):
    """Return RDV names available from the configured data provider."""
    return RdvListResponse(available=list(provider.list_available_rdvs()))


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
