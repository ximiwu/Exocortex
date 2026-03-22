from __future__ import annotations

from pathlib import Path

import fitz

from server.config import DEFAULT_RENDER_DPI, MAX_RENDER_DPI, MIN_RENDER_DPI
from server.domain.assets import get_asset_pdf_path
from server.errors import ApiError
from server.schemas import PdfMetadataModel, SizeModel

from .assets import normalize_asset_name, resolve_asset_dir


def _resolve_pdf_path(asset_name: str) -> Path:
    normalized = normalize_asset_name(asset_name)
    resolve_asset_dir(normalized)
    pdf_path = get_asset_pdf_path(normalized)
    if not pdf_path.is_file():
        raise ApiError(404, "pdf_not_found", f"PDF not found for asset '{normalized}'.")
    return pdf_path


def get_pdf_metadata(asset_name: str) -> PdfMetadataModel:
    pdf_path = _resolve_pdf_path(asset_name)
    page_sizes: list[SizeModel] = []
    with fitz.open(str(pdf_path)) as doc:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            scale = DEFAULT_RENDER_DPI / 72.0
            page_sizes.append(SizeModel(width=page.rect.width * scale, height=page.rect.height * scale))
        return PdfMetadataModel(
            pageCount=doc.page_count,
            pageSizes=page_sizes,
            defaultDpi=DEFAULT_RENDER_DPI,
            minDpi=MIN_RENDER_DPI,
            maxDpi=MAX_RENDER_DPI,
        )


def render_pdf_page_png(asset_name: str, page_index: int, *, dpi: int = DEFAULT_RENDER_DPI) -> bytes:
    pdf_path = _resolve_pdf_path(asset_name)
    dpi_value = max(MIN_RENDER_DPI, min(MAX_RENDER_DPI, int(dpi)))
    with fitz.open(str(pdf_path)) as doc:
        if page_index < 0 or page_index >= doc.page_count:
            raise ApiError(404, "page_not_found", f"Page {page_index} not found.")
        page = doc.load_page(page_index)
        scale = dpi_value / 72.0
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
        return pix.tobytes("png")


__all__ = ["get_pdf_metadata", "render_pdf_page_png"]
