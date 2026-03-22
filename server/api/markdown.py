from __future__ import annotations

from fastapi import APIRouter

from server.schemas import (
    MarkdownContentModel,
    MarkdownTreeNodeModel,
    MessageResponse,
    ReorderMarkdownSiblingsRequest,
    UpdateMarkdownNodeAliasRequest,
)
from server.services import markdown as markdown_service


router = APIRouter(tags=["markdown"])


@router.get("/assets/{asset_name:path}/markdown/tree", response_model=list[MarkdownTreeNodeModel])
def get_markdown_tree(asset_name: str) -> list[MarkdownTreeNodeModel]:
    return markdown_service.build_markdown_tree(asset_name)


@router.get("/assets/{asset_name:path}/markdown/content", response_model=MarkdownContentModel)
def get_markdown_content(asset_name: str, path: str) -> MarkdownContentModel:
    return markdown_service.get_markdown_content(asset_name, path)


@router.patch("/assets/{asset_name:path}/markdown/nodes/alias", response_model=MessageResponse)
def update_markdown_node_alias(asset_name: str, request: UpdateMarkdownNodeAliasRequest) -> MessageResponse:
    result = markdown_service.set_markdown_node_alias(
        asset_name,
        request.nodeId,
        request.path,
        request.alias,
    )
    return MessageResponse(message=f"Updated alias for '{result['nodeId']}'.", details=result)


@router.post("/assets/{asset_name:path}/markdown/nodes/reorder", response_model=MessageResponse)
def reorder_markdown_siblings(asset_name: str, request: ReorderMarkdownSiblingsRequest) -> MessageResponse:
    result = markdown_service.reorder_markdown_siblings(
        asset_name,
        request.parentId,
        request.orderedNodeIds,
    )
    return MessageResponse(message="Reordered markdown siblings.", details=result)


__all__ = ["router"]
