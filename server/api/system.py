from __future__ import annotations

from fastapi import APIRouter

from exocortex_core.paths import exocortex_assets_root
from server.schemas import AssetRootResponse


router = APIRouter(tags=["system"])


@router.get("/system/asset-root", response_model=AssetRootResponse)
def get_asset_root() -> AssetRootResponse:
    return AssetRootResponse(assetRoot=str(exocortex_assets_root()))


__all__ = ["router"]
