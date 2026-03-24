from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import FileResponse
from server.schemas import PdfMetadataModel, PdfPageTextBoxesModel, PdfSearchRequest, PdfSearchResponse
from server.services import pdf as pdf_service


router = APIRouter(tags=["pdf"])


@router.get("/assets/{asset_name:path}/pdf/metadata", response_model=PdfMetadataModel)
def get_pdf_metadata(asset_name: str) -> PdfMetadataModel:
    return pdf_service.get_pdf_metadata(asset_name)


@router.get("/assets/{asset_name:path}/pdf/file")
def get_pdf_file(asset_name: str) -> FileResponse:
    pdf_path = pdf_service.resolve_pdf_path(asset_name)
    return FileResponse(pdf_path, media_type="application/pdf", filename=pdf_path.name)


@router.get(
    "/assets/{asset_name:path}/pdf/pages/{page_index}/text-boxes",
    response_model=PdfPageTextBoxesModel,
)
def get_page_text_boxes(asset_name: str, page_index: int) -> PdfPageTextBoxesModel:
    return pdf_service.get_page_text_boxes(asset_name, page_index)


@router.post(
    "/assets/{asset_name:path}/pdf/search",
    response_model=PdfSearchResponse,
)
def search_pdf_content(asset_name: str, request: PdfSearchRequest) -> PdfSearchResponse:
    return pdf_service.search_pdf_content(asset_name, request.query)


__all__ = ["router"]
