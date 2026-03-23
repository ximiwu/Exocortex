from __future__ import annotations

from fastapi import APIRouter

from exocortex_core.paths import exocortex_assets_root
from server.schemas import AppConfigModel, AssetRootResponse, UpdateAppConfigRequest
from server.services import system as system_service


router = APIRouter(tags=["system"])


@router.get("/system/asset-root", response_model=AssetRootResponse)
def get_asset_root() -> AssetRootResponse:
    return AssetRootResponse(assetRoot=str(exocortex_assets_root()))


@router.get("/system/config", response_model=AppConfigModel)
def get_app_config() -> AppConfigModel:
    return system_service.get_app_config()


@router.put("/system/config", response_model=AppConfigModel)
def update_app_config(request: UpdateAppConfigRequest) -> AppConfigModel:
    return system_service.update_app_config(
        theme_mode=request.themeMode,
        sidebar_text_line_clamp=request.sidebarTextLineClamp,
        sidebar_font_size_px=request.sidebarFontSizePx,
        tutor_reasoning_effort=request.tutorReasoningEffort,
        tutor_with_global_context=request.tutorWithGlobalContext,
    )


__all__ = ["router"]
