from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"


class MessageResponse(BaseModel):
    ok: bool = True
    message: str
    details: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: Any = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class AssetRootResponse(BaseModel):
    assetRoot: str


class RectModel(BaseModel):
    x: float
    y: float
    width: float
    height: float


class SizeModel(BaseModel):
    width: float
    height: float


class FileArtifactModel(BaseModel):
    path: str
    name: str
    sizeBytes: int | None = None


__all__ = [
    "AssetRootResponse",
    "ErrorBody",
    "ErrorResponse",
    "FileArtifactModel",
    "HealthResponse",
    "MessageResponse",
    "RectModel",
    "SizeModel",
]
