from __future__ import annotations

from fastapi import APIRouter

from server.schemas import (
    AssetStateModel,
    CreateBlockRequest,
    MergeGroupRequest,
    PreviewMergeMarkdownRequest,
    PreviewMergeMarkdownResponse,
    UpdateSelectionRequest,
    UpdateUiStateRequest,
)
from server.services import assets as asset_service
from server.services import pdf as pdf_service


router = APIRouter(tags=["blocks"])


@router.post("/assets/{asset_name:path}/blocks", response_model=AssetStateModel)
def create_block(asset_name: str, request: CreateBlockRequest) -> AssetStateModel:
    return asset_service.create_block(asset_name, request.pageIndex, request.fractionRect)


@router.delete("/assets/{asset_name:path}/blocks/{block_id}", response_model=AssetStateModel)
def delete_block(asset_name: str, block_id: int) -> AssetStateModel:
    return asset_service.delete_block(asset_name, block_id)


@router.post("/assets/{asset_name:path}/blocks/selection", response_model=AssetStateModel)
def update_selection(asset_name: str, request: UpdateSelectionRequest) -> AssetStateModel:
    return asset_service.update_selection(asset_name, request.mergeOrder)


@router.post("/assets/{asset_name:path}/groups/merge", response_model=AssetStateModel)
def merge_group(asset_name: str, request: MergeGroupRequest) -> AssetStateModel:
    return asset_service.merge_group(
        asset_name,
        block_ids=request.blockIds,
        markdown_content=request.markdownContent,
        group_idx=request.groupIdx,
    )


@router.post(
    "/assets/{asset_name:path}/groups/markdown-preview",
    response_model=PreviewMergeMarkdownResponse,
)
def preview_merge_markdown(
    asset_name: str,
    request: PreviewMergeMarkdownRequest,
) -> PreviewMergeMarkdownResponse:
    return pdf_service.preview_merge_markdown(asset_name, request.blockIds)


@router.delete("/assets/{asset_name:path}/groups/{group_idx}", response_model=AssetStateModel)
def delete_group(asset_name: str, group_idx: int) -> AssetStateModel:
    return asset_service.delete_group(asset_name, group_idx)


@router.put("/assets/{asset_name:path}/ui-state", response_model=AssetStateModel)
def update_ui_state(asset_name: str, request: UpdateUiStateRequest) -> AssetStateModel:
    return asset_service.update_ui_state(
        asset_name,
        current_page=request.currentPage,
        zoom=request.zoom,
        pdf_scroll_fraction=request.pdfScrollFraction,
        pdf_scroll_left_fraction=request.pdfScrollLeftFraction,
        current_markdown_path=request.currentMarkdownPath,
        open_markdown_paths=request.openMarkdownPaths,
        sidebar_collapsed=request.sidebarCollapsed,
        sidebar_collapsed_node_ids=request.sidebarCollapsedNodeIds,
        markdown_scroll_fractions=request.markdownScrollFractions,
        sidebar_width_ratio=request.sidebarWidthRatio,
        right_rail_width_ratio=request.rightRailWidthRatio,
    )


__all__ = ["router"]
