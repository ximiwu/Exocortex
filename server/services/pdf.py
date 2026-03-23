from __future__ import annotations

import json
import math
import threading
from pathlib import Path
from typing import Any

import fitz

from server.config import DEFAULT_RENDER_DPI, MAX_RENDER_DPI, MIN_RENDER_DPI
from server.domain.assets import get_asset_pdf_path
from server.errors import ApiError
from server.schemas import PdfMetadataModel, PdfPageTextBoxesModel, PdfTextBoxModel, RectModel, SizeModel

from .assets import ensure_content_list_unified, normalize_asset_name, resolve_asset_dir

_CONTENT_LIST_CACHE_LOCK = threading.Lock()
_CONTENT_LIST_CACHE: dict[tuple[str, int, int], dict[int, tuple[PdfTextBoxModel, ...]]] = {}


def _resolve_pdf_path(asset_name: str) -> Path:
    normalized = normalize_asset_name(asset_name)
    resolve_asset_dir(normalized)
    pdf_path = get_asset_pdf_path(normalized)
    if not pdf_path.is_file():
        raise ApiError(404, "pdf_not_found", f"PDF not found for asset '{normalized}'.")
    return pdf_path


def resolve_pdf_path(asset_name: str) -> Path:
    return _resolve_pdf_path(asset_name)


def _resolve_content_list_unified_path(asset_name: str) -> Path:
    normalized = normalize_asset_name(asset_name)
    asset_dir = resolve_asset_dir(normalized)
    return asset_dir / "content_list_unified.json"


def _invalid_content_list_unified(asset_name: str, message: str, details: Any = None) -> ApiError:
    return ApiError(
        500,
        "invalid_content_list_unified",
        f"Invalid content_list_unified.json for asset '{asset_name}': {message}",
        details=details,
    )


def _require_number(
    value: object,
    *,
    field_name: str,
    item_index: int,
    asset_name: str,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _invalid_content_list_unified(
            asset_name,
            f"Entry {item_index} field '{field_name}' must be numeric.",
            details={"itemIndex": item_index, "field": field_name},
        )

    numeric = float(value)
    if not math.isfinite(numeric):
        raise _invalid_content_list_unified(
            asset_name,
            f"Entry {item_index} field '{field_name}' must be finite.",
            details={"itemIndex": item_index, "field": field_name},
        )
    return numeric


def _require_page_index_1_based(value: object, *, item_index: int, asset_name: str) -> int:
    numeric = _require_number(
        value,
        field_name="page_idx",
        item_index=item_index,
        asset_name=asset_name,
    )
    page_idx = int(round(numeric))
    if abs(numeric - page_idx) > 1e-9 or page_idx <= 0:
        raise _invalid_content_list_unified(
            asset_name,
            f"Entry {item_index} field 'page_idx' must be a positive integer.",
            details={"itemIndex": item_index, "field": "page_idx"},
        )
    return page_idx


def _parse_text_boxes_by_page(asset_name: str, path: Path) -> dict[int, tuple[PdfTextBoxModel, ...]]:
    try:
        raw_text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise _invalid_content_list_unified(asset_name, "Failed to read unified content list.") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise _invalid_content_list_unified(asset_name, "JSON parsing failed.") from exc

    if not isinstance(payload, list):
        raise _invalid_content_list_unified(
            asset_name,
            "Top-level JSON must be an array.",
            details={"topLevelType": type(payload).__name__},
        )

    per_page: dict[int, list[PdfTextBoxModel]] = {}
    for item_index, raw_item in enumerate(payload, start=1):
        if not isinstance(raw_item, dict):
            raise _invalid_content_list_unified(
                asset_name,
                f"Entry {item_index} must be an object.",
                details={"itemIndex": item_index},
            )

        page_index = _require_page_index_1_based(
            raw_item.get("page_idx"),
            item_index=item_index,
            asset_name=asset_name,
        ) - 1

        rect = RectModel(
            x=_require_number(raw_item.get("x"), field_name="x", item_index=item_index, asset_name=asset_name),
            y=_require_number(raw_item.get("y"), field_name="y", item_index=item_index, asset_name=asset_name),
            width=_require_number(
                raw_item.get("width"),
                field_name="width",
                item_index=item_index,
                asset_name=asset_name,
            ),
            height=_require_number(
                raw_item.get("height"),
                field_name="height",
                item_index=item_index,
                asset_name=asset_name,
            ),
        )

        per_page.setdefault(page_index, []).append(
            PdfTextBoxModel(
                pageIndex=page_index,
                fractionRect=rect,
            )
        )

    return {
        page_index: tuple(items)
        for page_index, items in per_page.items()
    }


def _load_text_boxes_by_page(asset_name: str, path: Path) -> dict[int, tuple[PdfTextBoxModel, ...]]:
    if not path.is_file():
        return {}

    resolved = path.resolve()
    try:
        stats = resolved.stat()
    except OSError as exc:
        raise _invalid_content_list_unified(asset_name, "Failed to stat unified content list.") from exc

    cache_key = (str(resolved), int(stats.st_mtime_ns), int(stats.st_size))

    with _CONTENT_LIST_CACHE_LOCK:
        cached = _CONTENT_LIST_CACHE.get(cache_key)
    if cached is not None:
        return cached

    parsed = _parse_text_boxes_by_page(asset_name, resolved)

    with _CONTENT_LIST_CACHE_LOCK:
        stale_keys = [key for key in _CONTENT_LIST_CACHE if key[0] == cache_key[0] and key != cache_key]
        for stale_key in stale_keys:
            _CONTENT_LIST_CACHE.pop(stale_key, None)
        _CONTENT_LIST_CACHE[cache_key] = parsed

    return parsed


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


def get_page_text_boxes(asset_name: str, page_index: int) -> PdfPageTextBoxesModel:
    if page_index < 0:
        raise ApiError(400, "invalid_page_index", "Page index must be non-negative.")

    unified_path = _resolve_content_list_unified_path(asset_name)
    if not unified_path.is_file():
        ensured_path = ensure_content_list_unified(asset_name)
        if ensured_path is not None:
            unified_path = ensured_path
    text_boxes_by_page = _load_text_boxes_by_page(asset_name, unified_path)

    return PdfPageTextBoxesModel(
        pageIndex=page_index,
        items=list(text_boxes_by_page.get(page_index, ())),
    )


__all__ = ["get_pdf_metadata", "get_page_text_boxes", "resolve_pdf_path"]
