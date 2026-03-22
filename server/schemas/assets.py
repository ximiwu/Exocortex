from __future__ import annotations

from pydantic import BaseModel, Field

from .common import RectModel, SizeModel


class AssetSummaryModel(BaseModel):
    name: str
    pageCount: int
    hasReferences: bool
    hasBlocks: bool


class AssetStateAssetModel(BaseModel):
    name: str
    pageCount: int
    pdfPath: str


class BlockModel(BaseModel):
    blockId: int
    pageIndex: int
    rect: RectModel
    groupIdx: int | None = None


class GroupModel(BaseModel):
    groupIdx: int
    blockIds: list[int] = Field(default_factory=list)


class UiStateModel(BaseModel):
    currentPage: int = 1
    zoom: float = 1.0
    pdfScrollFraction: float = 0.0
    pdfScrollLeftFraction: float = 0.0
    currentMarkdownPath: str | None = None
    openMarkdownPaths: list[str] = Field(default_factory=list)
    sidebarCollapsed: bool = False
    sidebarCollapsedNodeIds: list[str] = Field(default_factory=list)
    markdownScrollFractions: dict[str, float] = Field(default_factory=dict)


class AssetStateModel(BaseModel):
    asset: AssetStateAssetModel
    references: list[str] = Field(default_factory=list)
    blocks: list[BlockModel] = Field(default_factory=list)
    mergeOrder: list[int] = Field(default_factory=list)
    nextBlockId: int = 1
    groups: list[GroupModel] = Field(default_factory=list)
    uiState: UiStateModel = Field(default_factory=UiStateModel)


class MarkdownTreeNodeModel(BaseModel):
    id: str
    kind: str
    title: str
    path: str | None = None
    children: list["MarkdownTreeNodeModel"] = Field(default_factory=list)


class MarkdownContentModel(BaseModel):
    path: str
    title: str
    markdown: str
    html: str
    bodyHtml: str
    headHtml: str


class PdfMetadataModel(BaseModel):
    pageCount: int
    pageSizes: list[SizeModel]
    defaultDpi: int
    minDpi: int
    maxDpi: int


class CreateBlockRequest(BaseModel):
    pageIndex: int
    rect: RectModel


class UpdateSelectionRequest(BaseModel):
    mergeOrder: list[int] = Field(default_factory=list)


class MergeGroupRequest(BaseModel):
    blockIds: list[int] | None = None
    markdownContent: str | None = None
    groupIdx: int | None = None


class UpdateUiStateRequest(BaseModel):
    currentPage: int | None = None
    zoom: float | None = None
    pdfScrollFraction: float | None = None
    pdfScrollLeftFraction: float | None = None
    currentMarkdownPath: str | None = None
    openMarkdownPaths: list[str] | None = None
    sidebarCollapsed: bool | None = None
    sidebarCollapsedNodeIds: list[str] | None = None
    markdownScrollFractions: dict[str, float] | None = None


class CreateTutorRequest(BaseModel):
    focusMarkdown: str


class TutorSessionModel(BaseModel):
    tutorIdx: int
    markdownPath: str


class UpdateMarkdownNodeAliasRequest(BaseModel):
    nodeId: str
    path: str | None = None
    alias: str


class ReorderMarkdownSiblingsRequest(BaseModel):
    parentId: str | None = None
    orderedNodeIds: list[str] = Field(default_factory=list)


MarkdownTreeNodeModel.model_rebuild()


__all__ = [
    "AssetStateAssetModel",
    "AssetStateModel",
    "AssetSummaryModel",
    "BlockModel",
    "CreateBlockRequest",
    "CreateTutorRequest",
    "GroupModel",
    "MarkdownContentModel",
    "MarkdownTreeNodeModel",
    "MergeGroupRequest",
    "PdfMetadataModel",
    "ReorderMarkdownSiblingsRequest",
    "TutorSessionModel",
    "UiStateModel",
    "UpdateMarkdownNodeAliasRequest",
    "UpdateSelectionRequest",
    "UpdateUiStateRequest",
]
