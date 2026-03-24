from __future__ import annotations

import json
import logging
import math
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fitz

from server.config import DEFAULT_RENDER_DPI, MAX_RENDER_DPI, MIN_RENDER_DPI
from server.domain.assets import get_asset_pdf_path
from server.errors import ApiError
from server.schemas import (
    PdfMetadataModel,
    PdfPageTextBoxesModel,
    PdfTextBoxModel,
    PreviewMergeMarkdownResponse,
    RectModel,
    SizeModel,
)

from .assets import build_asset_state, ensure_content_list_unified, normalize_asset_name, resolve_asset_dir

logger = logging.getLogger(__name__)

_CONTENT_LIST_CACHE_LOCK = threading.Lock()
_CONTENT_LIST_CACHE: dict[tuple[str, int, int], tuple["_UnifiedContentListEntry", ...]] = {}
_CONTENT_LIST_CONTAINMENT_EPSILON = 1e-6
_TEXT_LIKE_ENTRY_TYPES = {
    "text",
    "title",
}


@dataclass(frozen=True)
class _UnifiedContentListEntry:
    item_index: int
    page_index: int
    rect: RectModel
    item: dict[str, Any]


@dataclass(frozen=True)
class _RenderedMarkdownFragment:
    markdown: str
    warning: str | None = None


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


def _invalid_markdown_preview_source(asset_name: str, message: str, details: Any = None) -> ApiError:
    return ApiError(
        500,
        "invalid_markdown_preview_source",
        f"Cannot generate markdown preview for asset '{asset_name}': {message}",
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


def _parse_unified_content_list_entries(asset_name: str, path: Path) -> tuple[_UnifiedContentListEntry, ...]:
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

    entries: list[_UnifiedContentListEntry] = []
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

        entries.append(
            _UnifiedContentListEntry(
                item_index=item_index,
                page_index=page_index,
                rect=rect,
                item=dict(raw_item),
            )
        )

    return tuple(entries)


def _load_unified_content_list_entries(asset_name: str, path: Path) -> tuple[_UnifiedContentListEntry, ...]:
    if not path.is_file():
        return ()

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

    parsed = _parse_unified_content_list_entries(asset_name, resolved)

    with _CONTENT_LIST_CACHE_LOCK:
        stale_keys = [key for key in _CONTENT_LIST_CACHE if key[0] == cache_key[0] and key != cache_key]
        for stale_key in stale_keys:
            _CONTENT_LIST_CACHE.pop(stale_key, None)
        _CONTENT_LIST_CACHE[cache_key] = parsed

    return parsed


def _resolve_available_content_list_unified_path(asset_name: str) -> Path | None:
    unified_path = _resolve_content_list_unified_path(asset_name)
    if unified_path.is_file():
        return unified_path

    ensured_path = ensure_content_list_unified(asset_name)
    if ensured_path is not None and ensured_path.is_file():
        return ensured_path

    return None


def _load_preview_source_entries(asset_name: str) -> tuple[_UnifiedContentListEntry, ...]:
    try:
        unified_path = _resolve_available_content_list_unified_path(asset_name)
    except ApiError as exc:
        raise _invalid_markdown_preview_source(asset_name, exc.message, details=exc.details) from exc

    if unified_path is None:
        raise _invalid_markdown_preview_source(
            asset_name,
            "content_list_unified.json is missing.",
            details={"assetName": asset_name},
        )

    try:
        return _load_unified_content_list_entries(asset_name, unified_path)
    except ApiError as exc:
        raise _invalid_markdown_preview_source(asset_name, exc.message, details=exc.details) from exc


def _rect_fully_contains(container: RectModel, candidate: RectModel, epsilon: float = _CONTENT_LIST_CONTAINMENT_EPSILON) -> bool:
    container_right = container.x + container.width
    container_bottom = container.y + container.height
    candidate_right = candidate.x + candidate.width
    candidate_bottom = candidate.y + candidate.height

    return (
        candidate.x >= container.x - epsilon
        and candidate.y >= container.y - epsilon
        and candidate_right <= container_right + epsilon
        and candidate_bottom <= container_bottom + epsilon
    )


def _resolve_selected_blocks(asset_name: str, block_ids: list[int]) -> list[Any]:
    asset_state = build_asset_state(asset_name)
    block_map = {block.blockId: block for block in asset_state.blocks}

    if not block_ids:
        raise ApiError(400, "no_blocks_selected", "Select one or more blocks before generating markdown.")

    resolved_blocks: list[Any] = []
    resolved_ids: set[int] = set()
    for raw_block_id in block_ids:
        block_id = int(raw_block_id)
        block = block_map.get(block_id)
        if block is None:
            raise ApiError(404, "block_not_found", f"Block {block_id} not found.")
        if block.groupIdx is not None:
            raise ApiError(400, "block_already_grouped", f"Block {block_id} is already grouped.")
        if block_id in resolved_ids:
            continue
        resolved_ids.add(block_id)
        resolved_blocks.append(block)

    return resolved_blocks


def _normalize_entry_type(value: object) -> str:
    return str(value).strip().lower() if isinstance(value, str) else ""


def _coerce_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        items = [str(item).strip() for item in value if isinstance(item, str) and item.strip()]
        return "\n".join(items)
    return ""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if isinstance(item, str) and item.strip()]


def _coerce_positive_int(value: object, default: int | None = None) -> int | None:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value if value > 0 else default
    if isinstance(value, float) and math.isfinite(value):
        rounded = int(round(value))
        return rounded if rounded > 0 and abs(value - rounded) <= 1e-9 else default
    return default


def _join_nonempty(parts: list[str], separator: str) -> str:
    return separator.join(part for part in parts if part.strip())


def _render_text_item(item: dict[str, Any]) -> str:
    text = _coerce_text(item.get("text"))
    if not text:
        return ""

    title_level = _coerce_positive_int(item.get("text_level"))
    if title_level is None and _normalize_entry_type(item.get("type")) == "title":
        title_level = _coerce_positive_int(item.get("level"), default=1)

    if title_level is not None:
        return f"{'#' * max(1, min(4, title_level))} {text}"
    return text


def _render_list_item(item: dict[str, Any]) -> str:
    list_items = _string_list(item.get("list_items"))
    return _join_nonempty(list_items, "  \n")


def _render_image_item(item: dict[str, Any], *, item_index: int | None = None) -> _RenderedMarkdownFragment:
    explanation = _coerce_text(item.get("image_explaination"))
    image_path = _coerce_text(item.get("img_path"))
    warning: str | None = None
    if explanation:
        body = explanation
    else:
        body = f"![]({image_path})" if image_path else ""
        index_label = f" {item_index}" if item_index is not None else ""
        warning = (
            f"Image item{index_label} is missing image_explaination. "
            "The markdown preview fell back to img_path."
        )
    captions = _join_nonempty(_string_list(item.get("image_caption")), "  \n")
    footnotes = _join_nonempty(_string_list(item.get("image_footnote")), "  \n")

    if footnotes:
        return _RenderedMarkdownFragment(
            markdown=_join_nonempty([captions, body, footnotes], "  \n"),
            warning=warning,
        )
    return _RenderedMarkdownFragment(markdown=_join_nonempty([body, captions], "  \n"), warning=warning)


def _render_table_item(item: dict[str, Any]) -> str:
    captions = _join_nonempty(_string_list(item.get("table_caption")), "  \n")
    footnotes = _join_nonempty(_string_list(item.get("table_footnote")), "  \n")
    body = _coerce_text(item.get("table_body"))
    if not body:
        image_path = _coerce_text(item.get("img_path"))
        if image_path:
            body = f"![]({image_path})"
    return _join_nonempty([captions, body, footnotes], "\n")


def _render_code_item(item: dict[str, Any]) -> str:
    captions = _join_nonempty(_string_list(item.get("code_caption")), "  \n")
    sub_type = _normalize_entry_type(item.get("sub_type"))
    if sub_type == "algorithm" or _normalize_entry_type(item.get("type")) == "algorithm":
        body = _coerce_text(item.get("code_body")) or _coerce_text(item.get("algorithm_content"))
        return _join_nonempty([captions, body], "  \n")

    body = _coerce_text(item.get("code_body")) or _coerce_text(item.get("code_content"))
    if not body:
        return captions

    guess_lang = _coerce_text(item.get("guess_lang")) or _coerce_text(item.get("code_language"))
    fenced = f"```{guess_lang}\n{body}\n```" if guess_lang else f"```\n{body}\n```"
    return _join_nonempty([captions, fenced], "  \n")


def _render_equation_item(item: dict[str, Any]) -> str:
    return _coerce_text(item.get("text"))


def _render_markdown_fragment(item: dict[str, Any], *, item_index: int | None = None) -> _RenderedMarkdownFragment:
    entry_type = _normalize_entry_type(item.get("type"))
    text_format = _normalize_entry_type(item.get("text_format"))

    if entry_type in _TEXT_LIKE_ENTRY_TYPES:
        return _RenderedMarkdownFragment(markdown=_render_text_item(item))
    if entry_type == "list":
        return _RenderedMarkdownFragment(markdown=_render_list_item(item))
    if entry_type == "image":
        return _render_image_item(item, item_index=item_index)
    if entry_type == "table":
        return _RenderedMarkdownFragment(markdown=_render_table_item(item))
    if entry_type in {"code", "algorithm"} or _normalize_entry_type(item.get("sub_type")) in {"code", "algorithm"}:
        return _RenderedMarkdownFragment(markdown=_render_code_item(item))
    if entry_type in {"equation", "interline_equation"} or text_format == "latex":
        return _RenderedMarkdownFragment(markdown=_render_equation_item(item))

    logger.warning("Skipping unsupported content_list_unified entry type %r.", item.get("type"))
    return _RenderedMarkdownFragment(markdown="")


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

    unified_path = _resolve_available_content_list_unified_path(asset_name)
    entries = _load_unified_content_list_entries(asset_name, unified_path) if unified_path is not None else ()

    return PdfPageTextBoxesModel(
        pageIndex=page_index,
        items=[
            PdfTextBoxModel(
                itemIndex=entry.item_index,
                pageIndex=entry.page_index,
                fractionRect=entry.rect,
            )
            for entry in entries
            if entry.page_index == page_index
        ],
    )


def preview_merge_markdown(asset_name: str, block_ids: list[int]) -> PreviewMergeMarkdownResponse:
    selected_blocks = _resolve_selected_blocks(asset_name, block_ids)
    asset_state = build_asset_state(asset_name)
    disabled_item_indexes = set(asset_state.disabledContentItemIndexes)
    entries = _load_preview_source_entries(asset_name)

    fragments: list[str] = []
    warnings: list[str] = []
    for entry in entries:
        if entry.item_index in disabled_item_indexes:
            continue
        if not any(
            block.pageIndex == entry.page_index and _rect_fully_contains(block.fractionRect, entry.rect)
            for block in selected_blocks
        ):
            continue

        rendered = _render_markdown_fragment(entry.item, item_index=entry.item_index)
        if rendered.markdown.strip():
            fragments.append(rendered.markdown.strip())
        if rendered.warning:
            warnings.append(rendered.warning)

    warning = "\n".join(dict.fromkeys(warnings)) or None
    return PreviewMergeMarkdownResponse(markdown="\n\n".join(fragments), warning=warning)


__all__ = ["get_pdf_metadata", "get_page_text_boxes", "preview_merge_markdown", "resolve_pdf_path"]
