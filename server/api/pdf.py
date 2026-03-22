from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import Response

from server.config import DEFAULT_RENDER_DPI
from server.schemas import PdfMetadataModel
from server.services import pdf as pdf_service


router = APIRouter(tags=["pdf"])


@router.get("/assets/{asset_name:path}/pdf/metadata", response_model=PdfMetadataModel)
def get_pdf_metadata(asset_name: str) -> PdfMetadataModel:
    return pdf_service.get_pdf_metadata(asset_name)


@router.get("/assets/{asset_name:path}/pdf/pages/{page_index}/image")
def get_pdf_page_image(
    asset_name: str,
    page_index: int,
    dpi: int = Query(DEFAULT_RENDER_DPI, ge=72, le=1200),
) -> Response:
    png_bytes = pdf_service.render_pdf_page_png(asset_name, page_index, dpi=dpi)
    return Response(content=png_bytes, media_type="image/png")


__all__ = ["router"]
