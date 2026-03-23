from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from typing import Iterable, Sequence

import fitz

from exocortex_core.contracts import COORDINATE_SPACE_PAGE_FRACTION
from server.config import DEFAULT_RENDER_DPI
from server.domain.assets import (
    BlockData,
    BlockRecord,
    BlockRect,
    asset_root,
    asset_config_write_lock,
    create_group_record,
    delete_group_record,
    get_asset_dir,
    get_asset_pdf_path,
    get_asset_config,
    init_tutor,
    list_assets,
    load_block_data,
    load_group_records,
    save_asset_config,
    save_block_data,
)
from server.errors import ApiError
from server.legacy.assets import write_unified_content_list
from server.schemas import (
    AssetStateAssetModel,
    AssetStateModel,
    AssetSummaryModel,
    BlockModel,
    GroupModel,
    RectModel,
    TutorSessionModel,
    UiStateModel,
    SizeModel,
)


ASSETS_ROOT = asset_root()


def _safe_rmtree(path: Path) -> None:
    def _handle_remove_readonly(func, target, _exc_info):
        try:
            os.chmod(target, stat.S_IWRITE)
        except Exception:
            pass
        func(target)

    shutil.rmtree(path, onerror=_handle_remove_readonly)


def _normalize_asset_name(asset_name: str) -> str:
    normalized = asset_name.replace("\\", "/").strip().strip("/")
    parts = [part for part in normalized.split("/") if part]
    if not parts or any(part in {".", ".."} for part in parts) or ":" in normalized:
        raise ApiError(400, "invalid_asset_name", "Asset name is invalid.")
    return "/".join(parts)


def normalize_asset_name(asset_name: str) -> str:
    return _normalize_asset_name(asset_name)


def resolve_asset_dir(asset_name: str, *, must_exist: bool = True) -> Path:
    normalized = _normalize_asset_name(asset_name)
    asset_dir = get_asset_dir(normalized)
    try:
        resolved = asset_dir.resolve()
        root = ASSETS_ROOT.resolve()
    except Exception:
        resolved = asset_dir
        root = ASSETS_ROOT
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ApiError(400, "invalid_asset_name", "Asset path escapes the asset root.") from exc
    if must_exist and not resolved.is_dir():
        raise ApiError(404, "asset_not_found", f"Asset '{normalized}' not found.")
    return resolved


def relative_to_assets_root(path: Path) -> str:
    try:
        return path.resolve().relative_to(ASSETS_ROOT.resolve()).as_posix()
    except Exception:
        return str(path)


def resolve_relative_file(asset_name: str, raw_path: str) -> Path:
    if not raw_path.strip():
        raise ApiError(400, "invalid_path", "Path is required.")
    asset_dir = resolve_asset_dir(asset_name)
    candidate = Path(raw_path)
    if candidate.is_absolute():
        resolved = candidate.resolve()
    else:
        resolved = (asset_dir / candidate).resolve()
    try:
        resolved.relative_to(asset_dir.resolve())
    except ValueError as exc:
        raise ApiError(400, "invalid_path", "Path must stay inside the asset directory.") from exc
    if not resolved.is_file():
        raise ApiError(404, "file_not_found", f"File not found: {raw_path}")
    return resolved


def resolve_reference_file(asset_name: str, name: str) -> Path:
    if not name or "/" in name or "\\" in name or name in {".", ".."}:
        raise ApiError(400, "invalid_reference_name", "Reference file name is invalid.")
    path = resolve_asset_dir(asset_name) / "references" / name
    if not path.is_file():
        raise ApiError(404, "reference_not_found", f"Reference '{name}' not found.")
    return path


def _page_count(pdf_path: Path) -> int:
    if not pdf_path.is_file():
        return 0
    with fitz.open(str(pdf_path)) as doc:
        return doc.page_count


def _resolve_content_list_paths(asset_dir: Path) -> tuple[Path, Path]:
    return asset_dir / "content_list.json", asset_dir / "content_list_unified.json"


def _list_reference_names(asset_name: str) -> list[str]:
    references_dir = resolve_asset_dir(asset_name) / "references"
    if not references_dir.is_dir():
        return []
    return sorted(path.name for path in references_dir.iterdir() if path.is_file())


def _load_ui_state(asset_name: str, page_count: int) -> UiStateModel:
    config = get_asset_config(asset_name) or {}
    zoom_raw = config.get("zoom")
    try:
        zoom_value = float(zoom_raw) if zoom_raw is not None else 1.0
    except Exception:
        zoom_value = 1.0

    pdf_scroll_fraction_raw = config.get("pdf_scroll_fraction")
    try:
        pdf_scroll_fraction = float(pdf_scroll_fraction_raw) if pdf_scroll_fraction_raw is not None else 0.0
    except Exception:
        pdf_scroll_fraction = 0.0
    pdf_scroll_fraction = min(1.0, max(0.0, pdf_scroll_fraction))

    pdf_scroll_left_fraction_raw = config.get("pdf_scroll_left_fraction")
    try:
        pdf_scroll_left_fraction = (
            float(pdf_scroll_left_fraction_raw) if pdf_scroll_left_fraction_raw is not None else 0.0
        )
    except Exception:
        pdf_scroll_left_fraction = 0.0
    pdf_scroll_left_fraction = min(1.0, max(0.0, pdf_scroll_left_fraction))

    current_page_raw = config.get("current_page")
    current_page = 1
    if isinstance(current_page_raw, (int, float)):
        candidate = int(current_page_raw)
        if candidate >= 1:
            current_page = candidate
    elif page_count > 0:
        current_page = max(1, min(page_count, int(round(pdf_scroll_fraction * max(page_count - 1, 0))) + 1))

    markdown_path = config.get("markdown_path")
    current_markdown_path = markdown_path if isinstance(markdown_path, str) and markdown_path.strip() else None

    open_markdown_paths_raw = config.get("open_markdown_paths")
    open_markdown_paths: list[str] = []
    if isinstance(open_markdown_paths_raw, list):
        for item in open_markdown_paths_raw:
            if isinstance(item, str) and item and item not in open_markdown_paths:
                open_markdown_paths.append(item)

    sidebar_collapsed = bool(config.get("sidebar_collapsed", False))

    sidebar_collapsed_node_ids_raw = config.get("sidebar_collapsed_node_ids")
    sidebar_collapsed_node_ids: list[str] = []
    if isinstance(sidebar_collapsed_node_ids_raw, list):
        for item in sidebar_collapsed_node_ids_raw:
            if isinstance(item, str) and item and item not in sidebar_collapsed_node_ids:
                sidebar_collapsed_node_ids.append(item)

    markdown_scroll_fractions_raw = config.get("markdown_scroll_fractions")
    markdown_scroll_fractions: dict[str, float] = {}
    if isinstance(markdown_scroll_fractions_raw, dict):
        for raw_path, raw_fraction in markdown_scroll_fractions_raw.items():
            if not isinstance(raw_path, str) or not raw_path:
                continue
            try:
                fraction = float(raw_fraction)
            except Exception:
                continue
            markdown_scroll_fractions[raw_path] = min(1.0, max(0.0, fraction))

    sidebar_width_ratio_raw = config.get("sidebar_width_ratio")
    try:
        sidebar_width_ratio = (
            min(1.0, max(0.0, float(sidebar_width_ratio_raw)))
            if sidebar_width_ratio_raw is not None
            else None
        )
    except Exception:
        sidebar_width_ratio = None

    right_rail_width_ratio_raw = config.get("right_rail_width_ratio")
    try:
        right_rail_width_ratio = (
            min(1.0, max(0.0, float(right_rail_width_ratio_raw)))
            if right_rail_width_ratio_raw is not None
            else None
        )
    except Exception:
        right_rail_width_ratio = None

    return UiStateModel(
        currentPage=current_page,
        zoom=zoom_value,
        pdfScrollFraction=pdf_scroll_fraction,
        pdfScrollLeftFraction=pdf_scroll_left_fraction,
        currentMarkdownPath=current_markdown_path,
        openMarkdownPaths=open_markdown_paths,
        sidebarCollapsed=sidebar_collapsed,
        sidebarCollapsedNodeIds=sidebar_collapsed_node_ids,
        markdownScrollFractions=markdown_scroll_fractions,
        sidebarWidthRatio=sidebar_width_ratio,
        rightRailWidthRatio=right_rail_width_ratio,
    )


def _block_rect_to_fraction(record: BlockRecord, page_sizes: Sequence[SizeModel]) -> BlockRect:
    if record.page_index < 0 or record.page_index >= len(page_sizes):
        return record.rect
    page_size = page_sizes[record.page_index]
    width_ref = float(page_size.width)
    height_ref = float(page_size.height)
    if width_ref <= 0 or height_ref <= 0:
        return BlockRect(x=0.0, y=0.0, width=0.0, height=0.0)

    x0_ref = min(max(float(record.rect.x), 0.0), width_ref)
    y0_ref = min(max(float(record.rect.y), 0.0), height_ref)
    x1_ref = min(max(float(record.rect.x + record.rect.width), 0.0), width_ref)
    y1_ref = min(max(float(record.rect.y + record.rect.height), 0.0), height_ref)

    return BlockRect(
        x=x0_ref / width_ref,
        y=y0_ref / height_ref,
        width=max(0.0, x1_ref - x0_ref) / width_ref,
        height=max(0.0, y1_ref - y0_ref) / height_ref,
    )


def _ensure_fraction_block_data(block_data: BlockData, page_sizes: Sequence[SizeModel]) -> tuple[BlockData, bool]:
    if block_data.coordinate_space == COORDINATE_SPACE_PAGE_FRACTION:
        return block_data, False

    normalized_blocks: list[BlockRecord] = []
    for record in block_data.blocks:
        normalized_blocks.append(
            BlockRecord(
                block_id=record.block_id,
                page_index=record.page_index,
                rect=_block_rect_to_fraction(record, page_sizes),
                group_idx=record.group_idx,
            )
        )

    normalized_data = BlockData(
        blocks=normalized_blocks,
        merge_order=list(block_data.merge_order),
        next_block_id=block_data.next_block_id,
        coordinate_space=COORDINATE_SPACE_PAGE_FRACTION,
    )
    return normalized_data, True


def _load_page_sizes_at_reference_dpi(pdf_path: Path) -> list[SizeModel]:
    if not pdf_path.is_file():
        return []

    scale = DEFAULT_RENDER_DPI / 72.0
    page_sizes: list[SizeModel] = []
    with fitz.open(str(pdf_path)) as doc:
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            page_sizes.append(SizeModel(width=page.rect.width * scale, height=page.rect.height * scale))
    return page_sizes


def _load_fraction_block_data(asset_name: str, pdf_path: Path) -> BlockData:
    block_data = load_block_data(asset_name)
    if block_data.coordinate_space == COORDINATE_SPACE_PAGE_FRACTION:
        return block_data

    page_sizes = _load_page_sizes_at_reference_dpi(pdf_path)
    if not page_sizes:
        return block_data
    normalized_data, migrated = _ensure_fraction_block_data(block_data, page_sizes)
    if migrated:
        save_block_data(asset_name, normalized_data)
    return normalized_data


def build_asset_summary(asset_name: str) -> AssetSummaryModel:
    normalized = _normalize_asset_name(asset_name)
    pdf_path = get_asset_pdf_path(normalized)
    block_data = load_block_data(normalized)
    references = _list_reference_names(normalized)
    return AssetSummaryModel(
        name=normalized,
        pageCount=_page_count(pdf_path),
        hasReferences=bool(references),
        hasBlocks=bool(block_data.blocks),
    )


def list_asset_summaries() -> list[AssetSummaryModel]:
    return [build_asset_summary(asset_name) for asset_name in list_assets()]


def ensure_content_list_unified(asset_name: str) -> Path | None:
    normalized = _normalize_asset_name(asset_name)
    asset_dir = resolve_asset_dir(normalized)
    content_list_path, content_list_unified_path = _resolve_content_list_paths(asset_dir)
    if content_list_unified_path.is_file():
        return content_list_unified_path
    if not content_list_path.is_file():
        return None

    pdf_path = get_asset_pdf_path(normalized)
    if not pdf_path.is_file():
        raise ApiError(
            500,
            "content_list_unified_generation_failed",
            f"Failed to generate content_list_unified.json for asset '{normalized}': raw.pdf is missing.",
            details={"assetName": normalized, "pdfPath": str(pdf_path)},
        )

    try:
        write_unified_content_list(
            source_path=content_list_path,
            pdf_path=pdf_path,
            target_path=content_list_unified_path,
        )
    except ValueError as exc:
        raise ApiError(
            500,
            "content_list_unified_generation_failed",
            f"Failed to generate content_list_unified.json for asset '{normalized}'.",
            details={"assetName": normalized, "reason": str(exc)},
        ) from exc
    except OSError as exc:
        raise ApiError(
            500,
            "content_list_unified_generation_failed",
            f"Failed to generate content_list_unified.json for asset '{normalized}'.",
            details={"assetName": normalized, "reason": "filesystem_error"},
        ) from exc

    return content_list_unified_path


def build_asset_state(asset_name: str) -> AssetStateModel:
    normalized = _normalize_asset_name(asset_name)
    asset_dir = resolve_asset_dir(normalized)
    pdf_path = get_asset_pdf_path(normalized)
    ensure_content_list_unified(normalized)
    page_sizes = _load_page_sizes_at_reference_dpi(pdf_path)
    page_count = len(page_sizes)
    block_data = _load_fraction_block_data(normalized, pdf_path)
    group_records = load_group_records(normalized)
    blocks = [
        BlockModel(
            blockId=record.block_id,
            pageIndex=record.page_index,
            fractionRect=RectModel(
                x=record.rect.x,
                y=record.rect.y,
                width=record.rect.width,
                height=record.rect.height,
            ),
            groupIdx=record.group_idx,
        )
        for record in block_data.blocks
    ]
    groups = [GroupModel(groupIdx=record.group_idx, blockIds=list(record.block_ids)) for record in group_records]
    return AssetStateModel(
        asset=AssetStateAssetModel(
            name=normalized,
            pageCount=page_count,
            pdfPath=relative_to_assets_root(pdf_path if pdf_path.is_file() else asset_dir / "raw.pdf"),
        ),
        references=_list_reference_names(normalized),
        blocks=blocks,
        mergeOrder=list(block_data.merge_order),
        nextBlockId=block_data.next_block_id,
        groups=groups,
        uiState=_load_ui_state(normalized, page_count),
    )


def _next_block_id(data: BlockData) -> int:
    return max(data.next_block_id, max((record.block_id for record in data.blocks), default=0) + 1)


def _resolved_next_block_id(current_next: int, blocks: list[BlockRecord]) -> int:
    return max(current_next, max((record.block_id for record in blocks), default=0) + 1, 1)


def create_block(asset_name: str, page_index: int, fraction_rect: RectModel) -> AssetStateModel:
    normalized = _normalize_asset_name(asset_name)
    resolve_asset_dir(normalized)
    pdf_path = get_asset_pdf_path(normalized)
    data = _load_fraction_block_data(normalized, pdf_path)
    x = min(max(float(fraction_rect.x), 0.0), 1.0)
    y = min(max(float(fraction_rect.y), 0.0), 1.0)
    width = min(max(float(fraction_rect.width), 0.0), max(0.0, 1.0 - x))
    height = min(max(float(fraction_rect.height), 0.0), max(0.0, 1.0 - y))
    block_id = _next_block_id(data)
    blocks = list(data.blocks)
    blocks.append(
        BlockRecord(
            block_id=block_id,
            page_index=page_index,
            rect=BlockRect(x=x, y=y, width=width, height=height),
            group_idx=None,
        )
    )
    save_block_data(
        normalized,
        BlockData(
            blocks=blocks,
            merge_order=list(data.merge_order),
            next_block_id=block_id + 1,
            coordinate_space=COORDINATE_SPACE_PAGE_FRACTION,
        ),
    )
    return build_asset_state(normalized)


def update_selection(asset_name: str, merge_order: Iterable[int]) -> AssetStateModel:
    normalized = _normalize_asset_name(asset_name)
    resolve_asset_dir(normalized)
    pdf_path = get_asset_pdf_path(normalized)
    data = _load_fraction_block_data(normalized, pdf_path)
    valid_ids = {record.block_id for record in data.blocks if record.group_idx is None}
    filtered: list[int] = []
    for block_id in merge_order:
        block_value = int(block_id)
        if block_value in valid_ids and block_value not in filtered:
            filtered.append(block_value)
    save_block_data(
        normalized,
        BlockData(
            blocks=list(data.blocks),
            merge_order=filtered,
            next_block_id=data.next_block_id,
            coordinate_space=COORDINATE_SPACE_PAGE_FRACTION,
        ),
    )
    return build_asset_state(normalized)


def merge_group(
    asset_name: str,
    *,
    block_ids: list[int] | None = None,
    markdown_content: str | None = None,
    group_idx: int | None = None,
) -> AssetStateModel:
    normalized = _normalize_asset_name(asset_name)
    resolve_asset_dir(normalized)
    pdf_path = get_asset_pdf_path(normalized)
    data = _load_fraction_block_data(normalized, pdf_path)
    block_map = {record.block_id: record for record in data.blocks}
    selected = block_ids if block_ids else list(data.merge_order)
    if not selected:
        raise ApiError(400, "no_blocks_selected", "Select one or more blocks before merging.")
    resolved_ids: list[int] = []
    for block_id in selected:
        block = block_map.get(int(block_id))
        if block is None:
            raise ApiError(404, "block_not_found", f"Block {block_id} not found.")
        if block.group_idx is not None:
            raise ApiError(400, "block_already_grouped", f"Block {block_id} is already grouped.")
        if block.block_id not in resolved_ids:
            resolved_ids.append(block.block_id)
    record = create_group_record(normalized, resolved_ids, group_idx=group_idx)
    updated_blocks = [
        BlockRecord(
            block_id=block.block_id,
            page_index=block.page_index,
            rect=block.rect,
            group_idx=record.group_idx if block.block_id in resolved_ids else block.group_idx,
        )
        for block in data.blocks
    ]
    save_block_data(
        normalized,
        BlockData(
            blocks=updated_blocks,
            merge_order=[],
            next_block_id=data.next_block_id,
            coordinate_space=COORDINATE_SPACE_PAGE_FRACTION,
        ),
    )
    if markdown_content is not None:
        group_dir = resolve_asset_dir(normalized) / "group_data" / str(record.group_idx)
        group_dir.mkdir(parents=True, exist_ok=True)
        (group_dir / "content.md").write_text(markdown_content, encoding="utf-8", newline="\n")
    return build_asset_state(normalized)


def delete_group(asset_name: str, group_idx: int) -> AssetStateModel:
    normalized = _normalize_asset_name(asset_name)
    resolve_asset_dir(normalized)
    pdf_path = get_asset_pdf_path(normalized)
    data = _load_fraction_block_data(normalized, pdf_path)
    records = load_group_records(normalized)
    target = next((record for record in records if record.group_idx == group_idx), None)
    if target is None:
        raise ApiError(404, "group_not_found", f"Group {group_idx} not found.")
    doomed = set(target.block_ids)
    blocks = [record for record in data.blocks if record.block_id not in doomed]
    merge_order = [block_id for block_id in data.merge_order if block_id not in doomed]
    save_block_data(
        normalized,
        BlockData(
            blocks=blocks,
            merge_order=merge_order,
            next_block_id=_resolved_next_block_id(data.next_block_id, blocks),
            coordinate_space=COORDINATE_SPACE_PAGE_FRACTION,
        ),
    )
    delete_group_record(normalized, group_idx)
    return build_asset_state(normalized)


def delete_block(asset_name: str, block_id: int) -> AssetStateModel:
    normalized = _normalize_asset_name(asset_name)
    resolve_asset_dir(normalized)
    pdf_path = get_asset_pdf_path(normalized)
    data = _load_fraction_block_data(normalized, pdf_path)
    target = next((record for record in data.blocks if record.block_id == block_id), None)
    if target is None:
        raise ApiError(404, "block_not_found", f"Block {block_id} not found.")
    if target.group_idx is not None:
        return delete_group(normalized, target.group_idx)
    blocks = [record for record in data.blocks if record.block_id != block_id]
    merge_order = [value for value in data.merge_order if value != block_id]
    save_block_data(
        normalized,
        BlockData(
            blocks=blocks,
            merge_order=merge_order,
            next_block_id=_resolved_next_block_id(data.next_block_id, blocks),
            coordinate_space=COORDINATE_SPACE_PAGE_FRACTION,
        ),
    )
    return build_asset_state(normalized)


def update_ui_state(
    asset_name: str,
    *,
    current_page: int | None = None,
    zoom: float | None = None,
    pdf_scroll_fraction: float | None = None,
    pdf_scroll_left_fraction: float | None = None,
    current_markdown_path: str | None = None,
    open_markdown_paths: list[str] | None = None,
    sidebar_collapsed: bool | None = None,
    sidebar_collapsed_node_ids: list[str] | None = None,
    markdown_scroll_fractions: dict[str, float] | None = None,
    sidebar_width_ratio: float | None = None,
    right_rail_width_ratio: float | None = None,
) -> AssetStateModel:
    normalized = _normalize_asset_name(asset_name)
    resolve_asset_dir(normalized)
    with asset_config_write_lock(normalized):
        config = get_asset_config(normalized) or {}
        if current_page is not None:
            config["current_page"] = max(1, int(current_page))
        if zoom is not None:
            config["zoom"] = float(zoom)
        if pdf_scroll_fraction is not None:
            config["pdf_scroll_fraction"] = min(1.0, max(0.0, float(pdf_scroll_fraction)))
        if pdf_scroll_left_fraction is not None:
            config["pdf_scroll_left_fraction"] = min(1.0, max(0.0, float(pdf_scroll_left_fraction)))
        if current_markdown_path is not None:
            config["markdown_path"] = current_markdown_path
        if open_markdown_paths is not None:
            config["open_markdown_paths"] = [path for path in open_markdown_paths if isinstance(path, str) and path]
        if sidebar_collapsed is not None:
            config["sidebar_collapsed"] = bool(sidebar_collapsed)
        if sidebar_collapsed_node_ids is not None:
            deduped_node_ids: list[str] = []
            for node_id in sidebar_collapsed_node_ids:
                if isinstance(node_id, str) and node_id and node_id not in deduped_node_ids:
                    deduped_node_ids.append(node_id)
            config["sidebar_collapsed_node_ids"] = deduped_node_ids
        if markdown_scroll_fractions is not None:
            normalized_scroll_fractions: dict[str, float] = {}
            for path, raw_fraction in markdown_scroll_fractions.items():
                if not isinstance(path, str) or not path:
                    continue
                try:
                    fraction = float(raw_fraction)
                except Exception:
                    continue
                normalized_scroll_fractions[path] = min(1.0, max(0.0, fraction))
            config["markdown_scroll_fractions"] = normalized_scroll_fractions
        if sidebar_width_ratio is not None:
            config["sidebar_width_ratio"] = min(1.0, max(0.0, float(sidebar_width_ratio)))
        if right_rail_width_ratio is not None:
            config["right_rail_width_ratio"] = min(1.0, max(0.0, float(right_rail_width_ratio)))
        save_asset_config(normalized, config)
        return build_asset_state(normalized)


def delete_asset(asset_name: str) -> None:
    asset_dir = resolve_asset_dir(asset_name)
    _safe_rmtree(asset_dir)


def delete_question(asset_name: str, group_idx: int, tutor_idx: int, markdown_path: str) -> None:
    normalized = _normalize_asset_name(asset_name)
    candidate = resolve_relative_file(normalized, markdown_path)
    ask_history_dir = (
        resolve_asset_dir(normalized)
        / "group_data"
        / str(group_idx)
        / "tutor_data"
        / str(tutor_idx)
        / "ask_history"
    )
    try:
        resolved_candidate = candidate.resolve()
        resolved_candidate.relative_to(ask_history_dir.resolve())
    except ValueError as exc:
        raise ApiError(
            400,
            "invalid_question_path",
            "Question markdown must live inside the tutor ask_history directory.",
        ) from exc
    except Exception:
        if candidate.parent != ask_history_dir:
            raise ApiError(
                400,
                "invalid_question_path",
                "Question markdown must live inside the tutor ask_history directory.",
            )
        resolved_candidate = candidate

    if resolved_candidate.suffix.lower() != ".md":
        raise ApiError(400, "invalid_question_path", "Question markdown must be a .md file.")

    resolved_candidate.unlink(missing_ok=True)


def create_tutor_session(asset_name: str, group_idx: int, focus_markdown: str) -> TutorSessionModel:
    normalized = _normalize_asset_name(asset_name)
    focus_path = init_tutor(normalized, group_idx, focus_markdown)
    try:
        tutor_idx = int(focus_path.parent.name)
    except Exception as exc:
        raise ApiError(500, "invalid_tutor_session", "Failed to resolve tutor session index.") from exc
    return TutorSessionModel(
        tutorIdx=tutor_idx,
        markdownPath=focus_path.relative_to(resolve_asset_dir(normalized)).as_posix(),
    )


def delete_tutor_session(asset_name: str, group_idx: int, tutor_idx: int) -> None:
    normalized = _normalize_asset_name(asset_name)
    asset_dir = resolve_asset_dir(normalized)
    tutor_session_dir = asset_dir / "group_data" / str(group_idx) / "tutor_data" / str(tutor_idx)
    try:
        tutor_session_dir.resolve().relative_to(asset_dir.resolve())
    except ValueError as exc:
        raise ApiError(
            400,
            "invalid_tutor_session_path",
            "Tutor session path must stay inside the asset directory.",
        ) from exc
    if not tutor_session_dir.is_dir():
        raise ApiError(
            404,
            "tutor_session_not_found",
            f"Tutor session {group_idx}/{tutor_idx} not found for asset '{normalized}'.",
        )
    _safe_rmtree(tutor_session_dir)


__all__ = [
    "ASSETS_ROOT",
    "build_asset_state",
    "build_asset_summary",
    "create_block",
    "create_tutor_session",
    "delete_tutor_session",
    "delete_asset",
    "delete_question",
    "delete_block",
    "delete_group",
    "ensure_content_list_unified",
    "list_asset_summaries",
    "merge_group",
    "normalize_asset_name",
    "relative_to_assets_root",
    "resolve_asset_dir",
    "resolve_reference_file",
    "resolve_relative_file",
    "update_selection",
    "update_ui_state",
]
