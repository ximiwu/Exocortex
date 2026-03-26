from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable

try:
    import genanki
except ImportError:  # pragma: no cover - dependency guard
    genanki = None

from exocortex_core.contracts import (
    AssetInitResult,
    BlockData,
    BlockRecord,
    BlockRect,
    GroupRecord,
    COORDINATE_SPACE_PAGE_FRACTION,
)
from exocortex_core.fs import atomic_write_text
from exocortex_core.markdown_viewer import anki_markdown_viewer_assets, render_markdown_viewer_document
from exocortex_core.markdown_web import render_markdown_asset_to_pdf
from exocortex_core.pdf_images import (
    crop_blocks_to_images,
    get_page_pixel_sizes,
    render_pdf_to_png_files,
    stack_images_vertically,
)
from exocortex_core.settings import (
    ASSETS_ROOT,
    BUG_FINDER_GEMINI_PROMPT,
    CODEX_MODEL,
    CODEX_REASONING_HIGH,
    CODEX_REASONING_LOW,
    CODEX_REASONING_MEDIUM,
    CODEX_REASONING_XHIGH,
    ENHANCER_CODEX_PROMPT,
    EXTRACTOR_PROMPTS,
    FLASHCARD_CODEX_PROMPT,
    GEMINI_MODEL,
    IMG2MD_GEMINI_PROMPT,
    IMG_EXPLAINER_CODEX_2_PROMPT,
    IMG_EXPLAINER_CODEX_PROMPT,
    INTEGRATOR_CODEX_PROMPT,
    LATEX_FIXER_CODEX_PROMPT,
    MANUSCRIPT_GEMINI_PROMPT,
    MD_EXPLAINER_CODEX_2_PROMPT,
    MD_EXPLAINER_CODEX_PROMPT,
    RE_TUTOR_GEMINI_PROMPT,
    TUTOR_CODEX_PROMPT,
    relative_to_repo,
)
from exocortex_core.workflow_events import WorkflowEventCallback, WorkflowEventType, emit_workflow_event

from agent_manager import (
    AgentJob,
    RunnerConfig,
    clean_markdown_file as _agent_clean_markdown_file,
    create_workspace,
    merge_outputs,
    run_agent_job,
    run_agent_jobs,
    run_codex_capture_last_message,
)


logger = logging.getLogger(__name__)

_UNIFIED_TEXT_LIKE_ENTRY_TYPES = {
    "text",
    "title",
}
_UNIFIED_SUPPORTED_ENTRY_TYPES = (
    _UNIFIED_TEXT_LIKE_ENTRY_TYPES
    | {
        "list",
        "image",
        "table",
        "code",
        "algorithm",
        "equation",
        "interline_equation",
    }
)

if TYPE_CHECKING:
    from PIL import Image


def _relative_to_repo(path: Path) -> Path:
    return relative_to_repo(path)


REFERENCE_RENDER_DPI = 130

EXTRACTOR_AGENTS: tuple[str, ...] = ("background", "concept", "formula")

IMG2MD_MISSING_RETRY_LIMIT = 1145142778

EXTRACTOR_OUTPUT_NAMES = {
    "background": "background.md",
    "concept": "concept.md",
    "formula": "formula.md",
}


def _emit_asset_event(
    event_callback: WorkflowEventCallback | None,
    event_type: WorkflowEventType,
    message: str,
    *,
    progress: float | None = None,
    artifact_path: str | Path | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    emit_workflow_event(
        event_callback,
        event_type,
        message,
        progress=progress,
        artifact_path=artifact_path,
        payload=payload,
    )


def _asset_payload(
    asset_name: str,
    *,
    group_idx: int | None = None,
    tutor_idx: int | None = None,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {"asset_name": asset_name}
    if group_idx is not None:
        payload["group_idx"] = group_idx
    if tutor_idx is not None:
        payload["tutor_idx"] = tutor_idx
    if extra:
        payload.update(extra)
    return payload


def get_asset_dir(asset_name: str) -> Path:
    """Return the on-disk directory for an asset (not validated)."""
    return ASSETS_ROOT / asset_name


def get_asset_config_path(asset_name: str) -> Path:
    """Return the path to the per-asset UI config JSON (not validated)."""
    return get_asset_dir(asset_name) / "config.json"


def load_asset_config(asset_name: str) -> dict[str, object]:
    """
    Load per-asset UI config. Returns empty dict if missing/invalid.
    """
    path = get_asset_config_path(asset_name)
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Failed to load asset config for '%s': %s", asset_name, exc)
        return {}
    if isinstance(raw, dict):
        return raw
    return {}


def save_asset_config(asset_name: str, data: dict[str, object]) -> Path:
    """
    Persist per-asset UI config using an atomic replace.
    """
    path = get_asset_config_path(asset_name)
    serialized = json.dumps(data, ensure_ascii=False, indent=2)
    return atomic_write_text(path, serialized)


def get_group_data_dir(asset_name: str) -> Path:
    """Return the path where group data is stored for an asset."""
    return ASSETS_ROOT / asset_name / "group_data"


def get_group_record_path(asset_name: str, group_idx: int) -> Path:
    """Return the JSON path for a specific group record."""
    return get_group_data_dir(asset_name) / str(group_idx) / "group.json"


def load_group_records(asset_name: str) -> list[GroupRecord]:
    """Load all group records for an asset."""
    base_dir = get_group_data_dir(asset_name)
    if not base_dir.is_dir():
        return []
    records: list[GroupRecord] = []
    for entry in base_dir.iterdir():
        if not entry.is_dir():
            continue
        try:
            group_idx = int(entry.name)
        except Exception:  # pragma: no cover - defensive parsing
            continue
        data_path = entry / "group.json"
        if not data_path.is_file():
            continue
        try:
            payload = json.loads(data_path.read_text(encoding="utf-8"))
            records.append(GroupRecord.from_dict(payload, default_idx=group_idx))
        except Exception as exc:  # pragma: no cover - defensive parsing
            logging.warning("Skipping invalid group data for '%s' at %s: %s", asset_name, data_path, exc)
    return sorted(records, key=lambda record: record.group_idx)


def next_group_idx(asset_name: str, existing: Iterable[GroupRecord] | None = None) -> int:
    """Return the next available group index for an asset."""
    records = list(existing) if existing is not None else load_group_records(asset_name)
    max_idx = max((record.group_idx for record in records), default=0)
    return max_idx + 1


def save_group_record(asset_name: str, record: GroupRecord) -> Path:
    """
    Persist a group record for an asset using an atomic replace.
    """
    path = get_group_record_path(asset_name, record.group_idx)
    serialized = json.dumps(record.to_dict(), ensure_ascii=False, indent=2)
    return atomic_write_text(path, serialized)


def create_group_record(asset_name: str, block_ids: list[int], group_idx: int | None = None) -> GroupRecord:
    """
    Create and persist a group record for the given block ids.
    """
    if not block_ids:
        raise ValueError("No block ids provided to group.")
    records = load_group_records(asset_name) if group_idx is None else None
    resolved_idx = group_idx if group_idx is not None else next_group_idx(asset_name, records)
    record = GroupRecord(group_idx=resolved_idx, block_ids=list(dict.fromkeys(block_ids)))
    save_group_record(asset_name, record)
    return record


def delete_group_record(asset_name: str, group_idx: int) -> None:
    """Delete a group record directory (and all contents) if it exists."""
    path = get_group_record_path(asset_name, group_idx)
    try:
        parent = path.parent
        if parent.is_dir():
            _safe_rmtree(parent)
        elif path.is_file():
            path.unlink()
    except Exception as exc:  # pragma: no cover - defensive cleanup
        logging.warning("Failed to delete group record for '%s' (group %s): %s", asset_name, group_idx, exc)


def _dir_has_content(path: Path) -> bool:
    """Return True if the directory exists and contains any entries."""
    return path.is_dir() and any(path.iterdir())
        
def _clean_markdown_file(file_path: Path) -> None:
    _agent_clean_markdown_file(file_path)
    content = file_path.read_text(encoding="utf-8-sig").lstrip("\ufeff")
    pattern = re.compile(r"([^\n])\n(\s*(?:[-+*]|\d+\.)\s+)")
    content = pattern.sub(r"\1\n\n\2", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    file_path.write_text(content, encoding="utf-8", newline="\n")


def _clean_directory(directory: Path) -> None:
    """Remove all files/subdirectories under the given directory."""
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.iterdir():
        if path.is_file() or path.is_symlink():
            path.unlink()
        else:
            _safe_rmtree(path)


def _render_markdown_to_pdf(markdown_path: Path, output_pdf: Path) -> Path:
    return render_markdown_asset_to_pdf(markdown_path, output_pdf)


def convert_pdf_to_images(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    dpi: int = 300,
    prefix: str | None = None,
) -> list[Path]:
    """
    Render a PDF into page-level PNG images.

    Args:
        pdf_path: PDF file to render.
        output_dir: Directory where images will be saved.
        dpi: Target resolution for the rendered images.
        prefix: Optional file name prefix (defaults to the PDF stem).

    Returns:
        List of saved image paths in page order.
    """
    return render_pdf_to_png_files(pdf_path, output_dir, dpi=dpi, prefix=prefix)


def _next_markdown_index(directory: Path) -> int:
    """Return the next numeric filename (1-based) under directory for *.md files."""
    if not directory.is_dir():
        return 1
    max_index = 0
    for path in directory.iterdir():
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        stem = path.stem
        if stem.isdigit():
            try:
                max_index = max(max_index, int(stem))
            except ValueError:  # pragma: no cover - defensive
                continue
    return max_index + 1


def _next_directory_index(directory: Path) -> int:
    """Return the next numeric directory name (1-based) under directory."""
    if not directory.is_dir():
        return 1
    max_index = 0
    for path in directory.iterdir():
        if not path.is_dir():
            continue
        name = path.name
        if not name.isdigit():
            continue
        try:
            max_index = max(max_index, int(name))
        except ValueError:  # pragma: no cover - defensive
            continue
    return max_index + 1


_MARKDOWN_ALIAS_SUFFIX = ".alias"


def _markdown_alias_path(markdown_path: Path) -> Path:
    return markdown_path.with_name(markdown_path.name + _MARKDOWN_ALIAS_SUFFIX)


def _atomic_write_text(path: Path, text: str) -> None:
    atomic_write_text(path, text, newline="\n")


def _set_markdown_alias(markdown_path: Path, alias: str) -> None:
    alias_path = _markdown_alias_path(markdown_path)
    cleaned = alias.strip()
    if not cleaned or cleaned == markdown_path.name:
        try:
            alias_path.unlink()
        except FileNotFoundError:
            pass
        return
    _atomic_write_text(alias_path, cleaned)


def _first_line_alias(markdown_text: str) -> str:
    normalized = markdown_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")
    if not lines:
        return ""
    first_line = lines[0].strip()
    if first_line:
        return first_line
    for line in lines[1:]:
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _flatten_prompt_text(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "").strip()


def _normalize_reasoning_effort(reasoning_effort: str) -> str:
    if reasoning_effort in {
        CODEX_REASONING_LOW,
        CODEX_REASONING_MEDIUM,
        CODEX_REASONING_HIGH,
        CODEX_REASONING_XHIGH,
    }:
        return reasoning_effort
    return CODEX_REASONING_MEDIUM


def _numeric_path_sort_key(path: Path) -> tuple[int, str]:
    stem = path.stem
    if stem.isdigit():
        return int(stem), stem
    return 1_000_000, stem.lower()


def _safe_rmtree(path: Path) -> None:
    """Remove a directory tree, clearing read-only flags on Windows if needed."""

    def _handle_remove_readonly(func, target, exc_info):
        try:
            os.chmod(target, stat.S_IWRITE)
        except Exception:
            pass
        try:
            func(target)
        except Exception:
            raise

    shutil.rmtree(path, onerror=_handle_remove_readonly)


def _prepare_working_directories() -> None:
    """Deprecated: workspaces are now isolated per agent run."""
    return


def _copy_raw_pdf(pdf_path: Path, asset_dir: Path) -> Path:
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / "raw.pdf"
    try:
        if pdf_path.resolve() == target.resolve():
            return target
    except Exception:
        pass
    shutil.copy2(pdf_path, target)
    return target


def move_all_files(src_dir: Path, dst_dir: Path, rename: dict[str, str] | None = None) -> list[Path]:
    """Move all files from src_dir into dst_dir, optionally renaming selected files."""
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)
    moved_files: list[Path] = []

    for path in src_dir.iterdir():
        if not path.is_file():
            continue
        target_name = (rename or {}).get(path.name, path.name)
        destination = dst_dir / target_name
        destination.unlink(missing_ok=True)
        moved_files.append(Path(shutil.move(str(path), destination)))

    if not moved_files:
        raise FileNotFoundError(f"No files found to move in {src_dir}")

    return moved_files


def copy_all_files(
    src_dir: Path, dst_dirs: Iterable[Path], rename: dict[str, str] | None = None
) -> list[Path]:
    """Copy all files from src_dir into each dst_dir, optionally renaming selected files."""
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_dir}")

    destinations = list(dst_dirs)
    if not destinations:
        raise ValueError("No destination directories provided.")

    for dst_dir in destinations:
        dst_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[Path] = []
    source_files = [path for path in src_dir.iterdir() if path.is_file()]
    if not source_files:
        raise FileNotFoundError(f"No files found to copy in {src_dir}")

    for path in source_files:
        target_name = (rename or {}).get(path.name, path.name)
        data = path.read_bytes()
        for dst_dir in destinations:
            destination = dst_dir / target_name
            destination.unlink(missing_ok=True)
            destination.write_bytes(data)
            copied_files.append(destination)
        path.unlink()

    return copied_files


def _load_group_record(asset_name: str, group_idx: int) -> GroupRecord:
    """Load a single group record or raise if missing/invalid."""
    path = get_group_record_path(asset_name, group_idx)
    if not path.is_file():
        raise FileNotFoundError(f"Group record not found for asset '{asset_name}', group {group_idx}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return GroupRecord.from_dict(payload, default_idx=group_idx)
    except Exception as exc:
        raise ValueError(f"Invalid group record at {path}") from exc


def _select_blocks_for_group(asset_name: str, group_idx: int) -> list[BlockRecord]:
    """Return blocks for the group in the stored selection order."""
    block_data = load_block_data(asset_name)
    if not block_data.blocks:
        raise FileNotFoundError(f"No block data found for asset '{asset_name}'.")

    group_record = _load_group_record(asset_name, group_idx)
    block_map = {block.block_id: block for block in block_data.blocks}

    missing: list[int] = []
    selected: list[BlockRecord] = []
    for block_id in group_record.block_ids:
        block = block_map.get(block_id)
        if not block:
            missing.append(block_id)
            continue
        selected.append(block)

    if missing:
        raise ValueError(f"Missing block(s) for asset '{asset_name}', group {group_idx}: {missing}")
    if not selected:
        raise ValueError(f"No blocks found for asset '{asset_name}', group {group_idx}.")

    return selected


def _render_blocks_to_images(
    pdf_path: Path,
    blocks: list[BlockRecord],
    dpi: int = 300,
    reference_dpi: int = REFERENCE_RENDER_DPI,
) -> list["Image.Image"]:
    """
    Render each block rect to a Pillow image cropped from its page(s).

    Block coordinates are stored as per-page fractions and are converted back into the
    reference render space before cropping.
    """
    return crop_blocks_to_images(
        pdf_path,
        blocks,
        dpi=dpi,
        reference_dpi=reference_dpi,
    )


def _stack_images_vertically(images: list["Image.Image"]) -> "Image.Image":
    """Stack images vertically into one combined Pillow image."""
    return stack_images_vertically(images)


def get_asset_pdf_path(asset_name: str) -> Path:
    """Return the path to the stored raw PDF for an asset (not validated)."""
    return ASSETS_ROOT / asset_name / "raw.pdf"


def get_block_data_path(asset_name: str) -> Path:
    """Return the path to the block data JSON for an asset (not validated)."""
    return ASSETS_ROOT / asset_name / "block_data" / "blocks.json"


def list_assets() -> list[str]:
    """List existing asset names (directories under ASSETS_ROOT)."""
    if not ASSETS_ROOT.is_dir():
        return []
    assets: list[str] = []
    for raw_pdf in ASSETS_ROOT.rglob("raw.pdf"):
        if not raw_pdf.is_file():
            continue
        try:
            relative_dir = raw_pdf.parent.relative_to(ASSETS_ROOT)
        except Exception:  # pragma: no cover - defensive
            continue
        assets.append(relative_dir.as_posix())
    return sorted(dict.fromkeys(assets))


def _block_rect_to_fraction(record: BlockRecord, page_sizes: list[tuple[int, int]]) -> BlockRect:
    if record.page_index < 0 or record.page_index >= len(page_sizes):
        return record.rect

    width_ref, height_ref = page_sizes[record.page_index]
    width_ref_value = float(width_ref)
    height_ref_value = float(height_ref)
    if width_ref_value <= 0 or height_ref_value <= 0:
        return BlockRect(x=0.0, y=0.0, width=0.0, height=0.0)

    x0_ref = min(max(float(record.rect.x), 0.0), width_ref_value)
    y0_ref = min(max(float(record.rect.y), 0.0), height_ref_value)
    x1_ref = min(max(float(record.rect.x + record.rect.width), 0.0), width_ref_value)
    y1_ref = min(max(float(record.rect.y + record.rect.height), 0.0), height_ref_value)

    return BlockRect(
        x=x0_ref / width_ref_value,
        y=y0_ref / height_ref_value,
        width=max(0.0, x1_ref - x0_ref) / width_ref_value,
        height=max(0.0, y1_ref - y0_ref) / height_ref_value,
    )


def _parse_content_list_items(payload: object) -> list[object]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        items = payload.get("items")
        if isinstance(items, list):
            return items
    raise ValueError("content list JSON must be an array of items or an object with an 'items' array.")


def _require_content_list_number(value: object, *, field_name: str, item_index: int) -> float:
    try:
        return float(value)
    except Exception as exc:
        raise ValueError(f"content list item {item_index} has an invalid {field_name} value.") from exc


def _normalize_content_list_type(value: object) -> str:
    return str(value).strip().lower() if isinstance(value, str) else ""


def _is_supported_unified_content_list_entry(entry: dict[str, object]) -> bool:
    entry_type = _normalize_content_list_type(entry.get("type"))
    sub_type = _normalize_content_list_type(entry.get("sub_type"))
    return entry_type in _UNIFIED_SUPPORTED_ENTRY_TYPES or sub_type in {"code", "algorithm"}


def _normalize_content_list_entry(
    entry: object,
    *,
    item_index: int,
    page_count: int,
) -> dict[str, object] | None:
    if not isinstance(entry, dict):
        raise ValueError(f"content list item {item_index} must be an object.")
    if not _is_supported_unified_content_list_entry(entry):
        logger.info("Skipping unsupported content list item %s with type=%r.", item_index, entry.get("type"))
        return None

    try:
        page_index = int(entry["page_idx"])
    except Exception as exc:
        raise ValueError(f"content list item {item_index} must include an integer page_idx field.") from exc

    if page_index < 0 or page_index >= page_count:
        raise ValueError(
            f"content list item {item_index} references page_idx {page_index}, which is outside the PDF page range."
        )

    bbox = entry.get("bbox")
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise ValueError(f"content list item {item_index} must include a bbox array with four numbers.")

    left = _require_content_list_number(bbox[0], field_name="bbox[0]", item_index=item_index)
    top = _require_content_list_number(bbox[1], field_name="bbox[1]", item_index=item_index)
    right = _require_content_list_number(bbox[2], field_name="bbox[2]", item_index=item_index)
    bottom = _require_content_list_number(bbox[3], field_name="bbox[3]", item_index=item_index)
    if right < left or bottom < top:
        raise ValueError(f"content list item {item_index} has an invalid bbox ordering.")

    normalized_entry = dict(entry)
    normalized_entry["page_idx"] = page_index + 1
    normalized_entry.pop("bbox", None)
    normalized_entry["x"] = left / 1000.0
    normalized_entry["y"] = top / 1000.0
    normalized_entry["width"] = (right - left) / 1000.0
    normalized_entry["height"] = (bottom - top) / 1000.0
    return normalized_entry


def write_unified_content_list(
    *,
    source_path: str | Path,
    pdf_path: str | Path,
    target_path: str | Path,
) -> int:
    resolved_source_path = Path(source_path)
    resolved_pdf_path = Path(pdf_path)
    resolved_target_path = Path(target_path)
    if not resolved_pdf_path.is_file():
        raise ValueError("Cannot normalize content list without a readable PDF.")
    payload = json.loads(resolved_source_path.read_text(encoding="utf-8-sig"))
    page_count = len(get_page_pixel_sizes(resolved_pdf_path, dpi=REFERENCE_RENDER_DPI))
    if page_count <= 0:
        raise ValueError("Cannot normalize content list without a readable PDF.")

    normalized_items = [
        _normalize_content_list_entry(entry, item_index=item_index, page_count=page_count)
        for item_index, entry in enumerate(_parse_content_list_items(payload), start=1)
    ]
    normalized_items = [entry for entry in normalized_items if entry is not None]
    serialized = json.dumps(normalized_items, ensure_ascii=False, indent=2)
    atomic_write_text(resolved_target_path, serialized)
    return len(normalized_items)


def save_asset_content_lists(
    *,
    asset_dir: str | Path,
    source_path: str | Path,
    pdf_path: str | Path,
) -> tuple[Path, Path, int]:
    resolved_asset_dir = Path(asset_dir)
    resolved_source_path = Path(source_path)
    content_list_path = resolved_asset_dir / "content_list.json"
    content_list_unified_path = resolved_asset_dir / "content_list_unified.json"
    atomic_write_text(content_list_path, resolved_source_path.read_text(encoding="utf-8-sig"))
    item_count = write_unified_content_list(
        source_path=resolved_source_path,
        pdf_path=pdf_path,
        target_path=content_list_unified_path,
    )
    return content_list_path, content_list_unified_path, item_count


def _normalize_block_data_coordinate_space(asset_name: str, data: BlockData) -> BlockData:
    if data.coordinate_space == COORDINATE_SPACE_PAGE_FRACTION:
        return data

    pdf_path = get_asset_pdf_path(asset_name)
    if not pdf_path.is_file():
        return data

    page_sizes = get_page_pixel_sizes(pdf_path, dpi=REFERENCE_RENDER_DPI)
    normalized_blocks = [
        BlockRecord(
            block_id=record.block_id,
            page_index=record.page_index,
            rect=_block_rect_to_fraction(record, page_sizes),
            group_idx=record.group_idx,
        )
        for record in data.blocks
    ]
    normalized_data = BlockData(
        blocks=normalized_blocks,
        merge_order=list(data.merge_order),
        next_block_id=data.next_block_id,
        coordinate_space=COORDINATE_SPACE_PAGE_FRACTION,
    )
    save_block_data(asset_name, normalized_data)
    return normalized_data


def load_block_data(asset_name: str) -> BlockData:
    """
    Load block data for an asset. Returns empty data if file is missing or invalid.
    """
    path = get_block_data_path(asset_name)
    if not path.is_file():
        return BlockData.empty()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        data = BlockData.from_dict(raw)
        return _normalize_block_data_coordinate_space(asset_name, data)
    except Exception as exc:  # pragma: no cover - defensive path
        logging.warning("Failed to load block data for '%s': %s", asset_name, exc)
        return BlockData.empty()


def save_block_data(asset_name: str, data: BlockData) -> Path:
    """
    Persist block data for an asset using an atomic replace.
    """
    path = get_block_data_path(asset_name)
    serialized = json.dumps(data.to_dict(), ensure_ascii=False, indent=2)
    return atomic_write_text(path, serialized)


def _resolve_asset_img2md_output_markdown(asset_name: str) -> Path:
    candidates = (
        ASSETS_ROOT / asset_name / "img2md_output" / "output.md",
        ASSETS_ROOT / asset_name / "img2mg_output" / "output.md",
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"img2md output.md not found for asset '{asset_name}'; tried: "
        + ", ".join(str(path) for path in candidates)
    )


def _collect_reference_files(
    asset_name: str,
    *,
    reference_filenames: Iterable[str] | None = None,
    include_entire_content: bool = False,
    entire_content_filename: str = "entire_content.md",
) -> tuple[list[Path], dict[str, str]]:
    asset_reference_dir = ASSETS_ROOT / asset_name / "references"
    if not asset_reference_dir.is_dir():
        raise FileNotFoundError(
            f"References directory not found for asset '{asset_name}': {asset_reference_dir}"
        )

    sources: list[Path] = []
    if reference_filenames is None:
        for path in asset_reference_dir.iterdir():
            if path.is_file():
                sources.append(path)
    else:
        for filename in reference_filenames:
            source = asset_reference_dir / filename
            if not source.is_file():
                raise FileNotFoundError(
                    f"Missing reference file for asset '{asset_name}': {source}"
                )
            sources.append(source)

    rename: dict[str, str] = {}
    if include_entire_content:
        entire_content_source = _resolve_asset_img2md_output_markdown(asset_name)
        sources.append(entire_content_source)
        if entire_content_source.name != entire_content_filename:
            rename[entire_content_source.name] = entire_content_filename

    if not sources:
        raise FileNotFoundError(f"No reference files found in {asset_reference_dir}")

    return sources, rename


def group_dive_in(
    asset_name: str,
    group_idx: int,
    *,
    on_secondary_ready: Callable[[Path], None] | None = None,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    """
    Generate explainer output for a group, archive initial outputs, and run enhancer.
    """
    _emit_asset_event(
        event_callback,
        "started",
        f"Starting group dive for asset '{asset_name}', group {group_idx}.",
        payload=_asset_payload(asset_name, group_idx=group_idx),
    )
    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    target_dir = group_dir / "img_explainer_data"
    initial_dir = target_dir / "initial"
    enhanced_md = target_dir / "enhanced.md"
    content_md = group_dir / "content.md"
    use_markdown_input = content_md.is_file()

    legacy_output = target_dir / "output.md"
    legacy_output_2 = target_dir / "output_2.md"
    legacy_secondary_compat_output = target_dir / "output_gemini.md"
    initial_output = initial_dir / "output.md"
    initial_output_2 = initial_dir / "output_2.md"
    initial_secondary_compat_output = initial_dir / "output_gemini.md"

    def _run_enhancer() -> Path:
        job = AgentJob(
            name="enhancer",
            runners=[
                RunnerConfig(
                    runner="codex",
                    prompt_path=ENHANCER_CODEX_PROMPT,
                    model=CODEX_MODEL,
                    reasoning_effort=CODEX_REASONING_XHIGH,
                    new_console=True,
                    extra_message="Use @/output/main.md as the primary draft, incrementally insert suitable parts from @/input/supplement.md into it, and save back to @/output/main.md without deleting existing content.",
                )
            ],
            input_files=[initial_output_2],
            input_rename={initial_output_2.name: "supplement.md"},
            output_seed_files=[initial_output],
            output_rename={initial_output.name: "main.md"},
            deliver_dir=_relative_to_repo(target_dir),
            deliver_rename={"main.md": "enhanced.md"},
            clean_markdown=True,
        )
        run_agent_job(
            job,
            event_callback=event_callback,
        )
        if not enhanced_md.is_file():
            raise FileNotFoundError(f"enhancer output not found: {enhanced_md}")
        _clean_markdown_file(enhanced_md)
        _emit_asset_event(
            event_callback,
            "completed",
            f"Completed group dive for asset '{asset_name}', group {group_idx}.",
            artifact_path=enhanced_md,
            payload=_asset_payload(asset_name, group_idx=group_idx),
        )
        return enhanced_md

    if enhanced_md.is_file():
        _clean_markdown_file(enhanced_md)
        logger.info(
            "enhanced.md already exists for asset '%s', group %s; skipping regeneration.",
            asset_name,
            group_idx,
        )
        _emit_asset_event(
            event_callback,
            "completed",
            f"Reused existing explainer output for asset '{asset_name}', group {group_idx}.",
            artifact_path=enhanced_md,
            payload=_asset_payload(asset_name, group_idx=group_idx),
        )
        return enhanced_md

    if legacy_output.is_file() or legacy_output_2.is_file() or legacy_secondary_compat_output.is_file():
        initial_dir.mkdir(parents=True, exist_ok=True)
        if legacy_output.is_file() and not initial_output.is_file():
            shutil.move(str(legacy_output), str(initial_output))
        if legacy_output_2.is_file() and not initial_output_2.is_file():
            shutil.move(str(legacy_output_2), str(initial_output_2))
        if legacy_secondary_compat_output.is_file() and not initial_output_2.is_file():
            shutil.move(str(legacy_secondary_compat_output), str(initial_output_2))
        elif legacy_secondary_compat_output.is_file() and not initial_secondary_compat_output.is_file():
            shutil.move(str(legacy_secondary_compat_output), str(initial_secondary_compat_output))

    # Migrate older secondary explainer outputs that were written as output_gemini.md.
    if initial_secondary_compat_output.is_file() and not initial_output_2.is_file():
        shutil.move(str(initial_secondary_compat_output), str(initial_output_2))

    if initial_output.is_file():
        _clean_markdown_file(initial_output)
    if initial_output_2.is_file():
        try:
            _clean_markdown_file(initial_output_2)
        except Exception as exc:  # pragma: no cover - defensive cleanup
            logger.warning(
                "Failed to clean existing secondary explainer output for '%s' (group %s): %s",
                asset_name,
                group_idx,
                exc,
            )
    if initial_output.is_file() and initial_output_2.is_file():
        logger.info(
            "Found initial explainer outputs for asset '%s', group %s; running enhancer only.",
            asset_name,
            group_idx,
        )
        return _run_enhancer()

    if _dir_has_content(target_dir):
        logger.info(
            "img_explainer_data exists for asset '%s', group %s but enhanced.md is missing; regenerating.",
            asset_name,
            group_idx,
        )

    _clean_directory(target_dir)
    initial_dir.mkdir(parents=True, exist_ok=True)

    reference_files, reference_rename = _collect_reference_files(
        asset_name,
        include_entire_content=True,
    )

    if use_markdown_input:
        if not content_md.read_text(encoding="utf-8-sig").strip():
            raise ValueError(f"Markdown content is empty: {content_md}")
        explainer_name = "md_explainer"
        codex_prompt = MD_EXPLAINER_CODEX_PROMPT
        codex_2_prompt = MD_EXPLAINER_CODEX_2_PROMPT
        thesis_input_path = content_md
        thesis_input_name = "thesis.md"
        codex_extra_message = "Explain input/thesis.md and save to output.md."
        codex_2_extra_message = "Explain input/thesis.md and save to output_2.md."
    else:
        pdf_path = get_asset_pdf_path(asset_name)
        if not pdf_path.is_file():
            raise FileNotFoundError(f"PDF not found for asset '{asset_name}': {pdf_path}")

        blocks = _select_blocks_for_group(asset_name, group_idx)
        images = _render_blocks_to_images(pdf_path, blocks, dpi=300)
        merged_image = _stack_images_vertically(images)

        thesis_image_path = target_dir / "thesis.png"
        thesis_image_path.parent.mkdir(parents=True, exist_ok=True)
        merged_image.save(thesis_image_path)
        if not thesis_image_path.is_file():
            raise RuntimeError(f"Failed to save rendered image to {thesis_image_path}")
        explainer_name = "img_explainer"
        codex_prompt = IMG_EXPLAINER_CODEX_PROMPT
        codex_2_prompt = IMG_EXPLAINER_CODEX_2_PROMPT
        thesis_input_path = thesis_image_path
        thesis_input_name = "thesis.png"
        codex_extra_message = "Explain input/thesis.png and save to output.md."
        codex_2_extra_message = "Explain input/thesis.png and save to output_2.md."

    def _build_explainer_job(prompt_path: Path, output_name: str, extra_message: str, job_name: str) -> AgentJob:
        return AgentJob(
            name=job_name,
            runners=[
                RunnerConfig(
                    runner="codex",
                    prompt_path=prompt_path,
                    model=CODEX_MODEL,
                    reasoning_effort=CODEX_REASONING_XHIGH,
                    new_console=True,
                    extra_message=extra_message,
                )
            ],
            input_files=[thesis_input_path],
            input_rename={thesis_input_path.name: thesis_input_name},
            reference_files=reference_files,
            reference_rename=reference_rename,
            deliver_dir=_relative_to_repo(initial_dir),
            deliver_rename={output_name: output_name},
            clean_markdown=True,
        )

    explainer_jobs = [
        _build_explainer_job(codex_prompt, "output.md", codex_extra_message, explainer_name),
        _build_explainer_job(codex_2_prompt, "output_2.md", codex_2_extra_message, f"{explainer_name}_2"),
    ]
    run_agent_jobs(
        explainer_jobs,
        max_workers=len(explainer_jobs),
        event_callback=event_callback,
    )

    secondary_output = initial_output_2
    if on_secondary_ready is not None:
        on_secondary_ready(secondary_output)
    _emit_asset_event(
        event_callback,
        "artifact",
        f"Secondary explainer draft is ready for asset '{asset_name}', group {group_idx}.",
        artifact_path=secondary_output,
        payload=_asset_payload(asset_name, group_idx=group_idx),
    )

    if not initial_output.is_file():
        raise FileNotFoundError(f"Explainer output not found: {initial_output}")
    if not initial_output_2.is_file():
        raise FileNotFoundError(f"Explainer secondary output not found: {initial_output_2}")

    return _run_enhancer()

def _resolve_img_explainer_markdown(img_explainer_dir: Path) -> Path:
    candidates = (
        img_explainer_dir / "enhanced.md",
        img_explainer_dir / "output.md",
        img_explainer_dir / "initial" / "output.md",
    )
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"No img_explainer markdown found under {img_explainer_dir}")


def _build_flashcard_reference_markdown(group_dir: Path, *, target_path: Path) -> int:
    tutor_root = group_dir / "tutor_data"
    if not tutor_root.is_dir():
        raise FileNotFoundError(f"tutor_data directory not found: {tutor_root}")

    ask_history_files: list[Path] = []
    for tutor_dir in sorted(
        [path for path in tutor_root.iterdir() if path.is_dir() and path.name.isdigit()],
        key=lambda path: int(path.name),
    ):
        ask_history_dir = tutor_dir / "ask_history"
        if not ask_history_dir.is_dir():
            continue
        ask_history_files.extend(
            sorted(
                [path for path in ask_history_dir.glob("*.md") if path.is_file()],
                key=_numeric_path_sort_key,
            )
        )

    if not ask_history_files:
        raise FileNotFoundError(f"No ask_history markdown files found under {tutor_root}")

    segments = [path.read_text(encoding="utf-8").rstrip() for path in ask_history_files]
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("\n\n".join(segment for segment in segments if segment) + "\n", encoding="utf-8", newline="\n")
    return len(ask_history_files)


def _stage_flashcard_reference_files(source_dir: Path, *, target_dir: Path) -> list[Path]:
    if not source_dir.is_dir():
        return []

    staged_files: list[Path] = []
    for source in sorted(
        [path for path in source_dir.rglob("*") if path.is_file()],
        key=lambda path: path.relative_to(source_dir).as_posix(),
    ):
        relative_path = source.relative_to(source_dir)
        staged_path = target_dir / relative_path
        staged_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, staged_path)
        staged_files.append(staged_path)
    return staged_files


@dataclass(frozen=True)
class _FlashcardExportRecord:
    source_path: Path
    asset_relative_path: str
    front_markdown: str
    back_markdown: str
    front_html: str
    back_html: str


def _directory_uri(path: Path) -> str:
    uri = path.resolve().as_uri()
    return uri if uri.endswith("/") else f"{uri}/"


def _clear_directory(path: Path) -> None:
    if path.exists():
        _safe_rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def _extract_flashcard_sections(markdown: str) -> tuple[str, str]:
    lines = markdown.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    question_idx: int | None = None
    answer_idx: int | None = None

    for index, line in enumerate(lines):
        if line.strip() == "question:":
            question_idx = index
            break

    if question_idx is not None:
        for index in range(question_idx + 1, len(lines)):
            if lines[index].strip() == "answer:":
                answer_idx = index
                break

    if question_idx is None or answer_idx is None or answer_idx <= question_idx:
        fallback = markdown.strip()
        return fallback, fallback

    front = "\n".join(lines[question_idx + 1 : answer_idx]).strip()
    back = "\n".join(lines[answer_idx + 1 :]).strip()
    if not front or not back:
        fallback = markdown.strip()
        return fallback, fallback
    return front, back


def _stable_anki_id(seed: str) -> int:
    digest = hashlib.sha1(seed.encode("utf-8")).digest()[:8]
    raw_value = int.from_bytes(digest, byteorder="big", signed=False)
    return (raw_value % 2147483646) + 1


def _flashcard_group_alias(group_dir: Path, *, group_idx: int) -> str:
    alias_path = group_dir / "group.alias"
    try:
        group_alias = alias_path.read_text(encoding="utf-8").strip()
    except Exception:
        group_alias = ""
    return group_alias or f"Group {group_idx}"


def _flashcard_deck_name(asset_name: str, *, group_idx: int, group_dir: Path) -> str:
    return f"{asset_name}::{_flashcard_group_alias(group_dir, group_idx=group_idx)}"


def _iter_flashcard_markdown_files(asset_dir: Path, source_dir: Path) -> list[tuple[Path, str]]:
    if not source_dir.is_dir():
        return []
    files = [path for path in source_dir.rglob("*.md") if path.is_file()]
    ordered = sorted(
        ((path, path.relative_to(asset_dir).as_posix()) for path in files),
        key=lambda item: item[1],
    )
    return ordered


def _export_flashcard_html(asset_dir: Path, source_dir: Path, *, target_dir: Path) -> list[_FlashcardExportRecord]:
    _clear_directory(target_dir)
    exports: list[_FlashcardExportRecord] = []
    for source_path, asset_relative_path in _iter_flashcard_markdown_files(asset_dir, source_dir):
        markdown = source_path.read_text(encoding="utf-8")
        front_markdown, back_markdown = _extract_flashcard_sections(markdown)
        front_document = render_markdown_viewer_document(front_markdown, base_url=_directory_uri(source_path.parent))
        back_document = render_markdown_viewer_document(back_markdown, base_url=_directory_uri(source_path.parent))

        relative_path = source_path.relative_to(source_dir)
        target_parent = target_dir / relative_path.parent
        target_parent.mkdir(parents=True, exist_ok=True)
        front_path = target_parent / f"{source_path.stem}.front.html"
        back_path = target_parent / f"{source_path.stem}.back.html"
        front_path.write_text(front_document.full_html, encoding="utf-8", newline="\n")
        back_path.write_text(back_document.full_html, encoding="utf-8", newline="\n")

        exports.append(
            _FlashcardExportRecord(
                source_path=source_path,
                asset_relative_path=asset_relative_path,
                front_markdown=front_markdown,
                back_markdown=back_markdown,
                front_html=front_document.body_html,
                back_html=back_document.body_html,
            )
        )

    return exports


def _build_flashcard_anki_package(
    *,
    asset_name: str,
    group_idx: int,
    group_dir: Path,
    exports: list[_FlashcardExportRecord],
    target_dir: Path,
) -> Path:
    if genanki is None:
        raise RuntimeError("Missing 'genanki' package.")
    if not exports:
        raise FileNotFoundError("No flashcard markdown files found for APKG export.")

    _clear_directory(target_dir)

    viewer_assets = anki_markdown_viewer_assets()
    group_alias = _flashcard_group_alias(group_dir, group_idx=group_idx)
    deck_name = _flashcard_deck_name(asset_name, group_idx=group_idx, group_dir=group_dir)
    deck_id = _stable_anki_id(f"exocortex|anki-deck|v1|{asset_name}|{group_alias}")
    model_id = _stable_anki_id("exocortex|anki-model|v1")

    model = genanki.Model(
        model_id,
        "Exocortex Flashcard",
        fields=[
            {"name": "SourcePath"},
            {"name": "FrontHtml"},
            {"name": "BackHtml"},
        ],
        templates=[
            {
                "name": "Card 1",
                "qfmt": (
                    '<div class="markdown-rendered card-face" data-source-path="{{SourcePath}}">{{FrontHtml}}</div>'
                    f"{viewer_assets.scripts_html}"
                ),
                "afmt": (
                    "{{FrontSide}}"
                    '<hr id="answer">'
                    '<div class="markdown-rendered card-face card-face--back">{{BackHtml}}</div>'
                    f"{viewer_assets.scripts_html}"
                ),
            }
        ],
        css=(
            viewer_assets.css
            + "\n\n"
            + "#answer { margin: 18px 0; border: none; border-top: 1px solid var(--border-default); }\n"
            + ".card-face { min-height: 1px; }\n"
        ),
    )

    deck = genanki.Deck(deck_id, deck_name)
    for export in exports:
        note = genanki.Note(
            model=model,
            fields=[export.asset_relative_path, export.front_html, export.back_html],
            guid=genanki.guid_for("exocortex|anki-note|v1", asset_name, export.asset_relative_path),
        )
        deck.add_note(note)

    package_path = target_dir / "deck.apkg"
    package = genanki.Package(deck, media_files=[str(path) for path in viewer_assets.media_files])
    package.write_to_file(str(package_path), timestamp=1.0)
    return package_path


def init_tutor(asset_name: str, group_idx: int, focus_markdown: str) -> Path:
    if not focus_markdown.strip():
        raise ValueError("Focus markdown is required.")

    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    tutor_data_dir = group_dir / "tutor_data"
    tutor_data_dir.mkdir(parents=True, exist_ok=True)
    tutor_idx = _next_directory_index(tutor_data_dir)
    session_dir = tutor_data_dir / str(tutor_idx)
    while session_dir.exists():
        tutor_idx += 1
        session_dir = tutor_data_dir / str(tutor_idx)
    session_dir.mkdir(parents=True, exist_ok=False)

    focus_path = session_dir / "focus.md"
    focus_path.write_text(focus_markdown, encoding="utf-8", newline="\n")
    try:
        _set_markdown_alias(focus_path, _first_line_alias(focus_markdown))
    except Exception as exc:  # pragma: no cover - best-effort UX
        logger.warning("Failed to write focus.md alias at %s: %s", focus_path, exc)
    return focus_path


def flashcard(
    asset_name: str,
    group_idx: int,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    _emit_asset_event(
        event_callback,
        "started",
        f"Starting flashcard flow for asset '{asset_name}', group {group_idx}.",
        payload=_asset_payload(asset_name, group_idx=group_idx),
    )

    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    content_md = group_dir / "content.md"
    if not content_md.is_file():
        raise FileNotFoundError(f"content.md not found at {content_md}")

    deliver_dir = group_dir / "flashcard" / "md"
    html_dir = group_dir / "flashcard" / "html"
    apkg_dir = group_dir / "flashcard" / "apkg"
    temp_dir = Path(tempfile.mkdtemp(prefix="exocortex_flashcard_"))
    try:
        qa_path = temp_dir / "QA.md"
        qa_count = _build_flashcard_reference_markdown(group_dir, target_path=qa_path)
        staged_flashcard_references = _stage_flashcard_reference_files(
            deliver_dir,
            target_dir=temp_dir / "flashcards",
        )
        reference_files = [qa_path, *staged_flashcard_references]
        reference_rename = {str(qa_path): "QA.md"}
        for staged_path in staged_flashcard_references:
            reference_rename[str(staged_path)] = (
                Path("flashcards") / staged_path.relative_to(temp_dir / "flashcards")
            ).as_posix()

        job = AgentJob(
            name="flashcard",
            runners=[
                RunnerConfig(
                    runner="codex",
                    prompt_path=FLASHCARD_CODEX_PROMPT,
                    model=CODEX_MODEL,
                    reasoning_effort=CODEX_REASONING_XHIGH,
                    new_console=True,
                )
            ],
            input_files=[content_md],
            input_rename={content_md.name: "content.md"},
            reference_files=reference_files,
            reference_rename=reference_rename,
            deliver_dir=_relative_to_repo(deliver_dir),
            deliver_all_output_files=True,
            preserve_existing_delivery=True,
            clean_markdown=True,
        )
        run_agent_job(job, event_callback=event_callback)

        delivered_files = [path for path in deliver_dir.rglob("*") if path.is_file()]
        if not delivered_files:
            raise FileNotFoundError(f"flashcard output not found under {deliver_dir}")
        markdown_exports = _export_flashcard_html(get_asset_dir(asset_name), deliver_dir, target_dir=html_dir)
        if not markdown_exports:
            raise FileNotFoundError(f"flashcard markdown output not found under {deliver_dir}")
        apkg_path = _build_flashcard_anki_package(
            asset_name=asset_name,
            group_idx=group_idx,
            group_dir=group_dir,
            exports=markdown_exports,
            target_dir=apkg_dir,
        )

        _emit_asset_event(
            event_callback,
            "completed",
            f"Completed flashcard flow for asset '{asset_name}', group {group_idx}.",
            artifact_path=deliver_dir,
            payload=_asset_payload(
                asset_name,
                group_idx=group_idx,
                extra={
                    "flashcard_dir": str(deliver_dir),
                    "delivered_count": len(delivered_files),
                    "qa_count": qa_count,
                    "html_dir": str(html_dir),
                    "apkg_dir": str(apkg_dir),
                    "apkg_path": str(apkg_path),
                    "card_count": len(markdown_exports),
                },
            ),
        )
        return deliver_dir
    finally:
        _safe_rmtree(temp_dir)


def ask_tutor(
    question: str,
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    *,
    reasoning_effort: str = CODEX_REASONING_MEDIUM,
    with_global_context: bool = True,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    """
    Run the tutor agent for a given question and tutor session, archive the response, and return it.

    Steps:
    1) Build input.md from focus.md + ask_history.
    2) Invoke tutor agent with the question.
    3) Move output.md into ask_history as the next sequential markdown (1, 2, ...), clean it, and prefix with Q/A headings.
    """
    normalized_question = _flatten_prompt_text(question)
    if not normalized_question:
        raise ValueError("Question is required.")
    resolved_reasoning_effort = _normalize_reasoning_effort(reasoning_effort)
    _emit_asset_event(
        event_callback,
        "started",
        f"Starting tutor flow for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
        payload=_asset_payload(
            asset_name,
            group_idx=group_idx,
            tutor_idx=tutor_idx,
            extra={"question": normalized_question},
        ),
    )

    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")
    focus_md = tutor_session_dir / "focus.md"
    if not focus_md.is_file():
        raise FileNotFoundError(f"tutor focus.md not found: {focus_md}")

    tutor_input_path = tutor_session_dir / "input.md"
    tutor_input_path.write_text(
        focus_md.read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )

    ask_history_dir = tutor_session_dir / "ask_history"
    if ask_history_dir.is_dir():
        def _order_key(path: Path) -> tuple[int, str]:
            stem = path.stem
            try:
                return int(stem), stem
            except Exception:
                return 1_000_000, stem

        history_files = sorted(
            [path for path in ask_history_dir.glob("*.md") if path.is_file()],
            key=_order_key,
        )
        with tutor_input_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n\n# 历史对话：\n")
            for history_path in history_files:
                try:
                    history_text = history_path.read_text(encoding="utf-8")
                except Exception:  # pragma: no cover - defensive
                    continue
                handle.write("\n\n")
                handle.write(history_text.rstrip())

    ask_history_dir.mkdir(parents=True, exist_ok=True)
    next_idx = _next_markdown_index(ask_history_dir)
    output_name = f"{next_idx}.md"
    moved_output = ask_history_dir / output_name

    if not with_global_context:
        _emit_asset_event(
            event_callback,
            "log",
            f"Running tutor without global context for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
            payload=_asset_payload(
                asset_name,
                group_idx=group_idx,
                tutor_idx=tutor_idx,
                extra={"reasoning_effort": resolved_reasoning_effort, "with_global_context": False},
            ),
        )
        workspace = create_workspace()
        prompt = _flatten_prompt_text(tutor_input_path.read_text(encoding="utf-8")) + normalized_question
        answer = run_codex_capture_last_message(
            prompt,
            workspace,
            output_last_message_path=workspace / "last_message.md",
            model=CODEX_MODEL,
            model_reasoning_effort=resolved_reasoning_effort,
            new_console=True,
        )
        moved_output.write_text(answer, encoding="utf-8", newline="\n")
        _clean_markdown_file(moved_output)
        answer = moved_output.read_text(encoding="utf-8")
        header = f"## 提问：\n\n{normalized_question}\n\n## 回答：\n\n"
        moved_output.write_text(header + answer.lstrip(), encoding="utf-8", newline="\n")
        try:
            _set_markdown_alias(moved_output, normalized_question)
        except Exception as exc:  # pragma: no cover - best-effort UX
            logger.warning("Failed to write ask_history alias at %s: %s", moved_output, exc)
        _emit_asset_event(
            event_callback,
            "completed",
            f"Completed tutor flow for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
            artifact_path=moved_output,
            payload=_asset_payload(
                asset_name,
                group_idx=group_idx,
                tutor_idx=tutor_idx,
                extra={"question": normalized_question},
            ),
        )
        return moved_output

    reference_files, reference_rename = _collect_reference_files(
        asset_name,
        include_entire_content=True,
    )

    job = AgentJob(
        name="tutor",
        runners=[
            RunnerConfig(
                runner="codex",
                prompt_path=TUTOR_CODEX_PROMPT,
                model=CODEX_MODEL,
                reasoning_effort=resolved_reasoning_effort,
                new_console=True,
                extra_message=f"{normalized_question}把讲解保存至 output/output.md",
            )
        ],
        input_files=[tutor_input_path],
        input_rename={tutor_input_path.name: "input.md"},
        reference_files=reference_files,
        reference_rename=reference_rename,
        deliver_dir=_relative_to_repo(ask_history_dir),
        deliver_rename={"output.md": output_name},
        clean_markdown=True,
    )
    run_agent_job(job, event_callback=event_callback)

    moved_output = ask_history_dir / output_name
    if not moved_output.is_file():
        raise FileNotFoundError(f"tutor output not found at {moved_output}")

    answer = moved_output.read_text(encoding="utf-8")
    header = f"## 提问：\n\n{normalized_question}\n\n## 回答：\n\n"
    moved_output.write_text(header + answer.lstrip(), encoding="utf-8", newline="\n")
    try:
        _set_markdown_alias(moved_output, normalized_question)
    except Exception as exc:  # pragma: no cover - best-effort UX
        logger.warning("Failed to write ask_history alias at %s: %s", moved_output, exc)
    _emit_asset_event(
        event_callback,
        "completed",
        f"Completed tutor flow for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
        artifact_path=moved_output,
        payload=_asset_payload(
            asset_name,
            group_idx=group_idx,
            tutor_idx=tutor_idx,
            extra={"question": normalized_question},
        ),
    )
    return moved_output



def integrate(
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    """
    Run the integrator agent for a tutor session, save a note, and insert it back into enhanced.md.

    Steps:
    1) Concatenate focus.md + ask_history into input.md.
    2) Invoke integrator agent.
    3) Clean markdown output and move it to tutor_data/<tutor_idx>/note.md.
    4) Wrap note.md in a <details class="note"> block.
    5) Insert the wrapped note block into img_explainer_data/enhanced.md at the end of the focus region.
    """
    _emit_asset_event(
        event_callback,
        "started",
        f"Starting integrate flow for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
        payload=_asset_payload(asset_name, group_idx=group_idx, tutor_idx=tutor_idx),
    )
    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")
    focus_md = tutor_session_dir / "focus.md"
    if not focus_md.is_file():
        raise FileNotFoundError(f"tutor focus.md not found: {focus_md}")

    integrator_input_path = tutor_session_dir / "integrator_input.md"
    integrator_input_path.write_text(
        focus_md.read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )

    ask_history_dir = tutor_session_dir / "ask_history"
    if ask_history_dir.is_dir():
        def _order_key(path: Path) -> tuple[int, str]:
            stem = path.stem
            try:
                return int(stem), stem
            except Exception:
                return 1_000_000, stem

        history_files = sorted(
            [path for path in ask_history_dir.glob("*.md") if path.is_file()],
            key=_order_key,
        )
        with integrator_input_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write("\n\n# 历史对话：\n")
            for history_path in history_files:
                try:
                    history_text = history_path.read_text(encoding="utf-8")
                except Exception:  # pragma: no cover - defensive
                    continue
                handle.write("\n\n")
                handle.write(history_text.rstrip())

    existing_input = integrator_input_path.read_text(encoding="utf-8")
    integrator_input_path.write_text(
        f"# 原始教学内容\n\n{existing_input}",
        encoding="utf-8",
        newline="\n",
    )

    reference_files, reference_rename = _collect_reference_files(
        asset_name,
        reference_filenames=("formula.md", "concept.md"),
    )

    note_path = tutor_session_dir / "note.md"

    job = AgentJob(
        name="integrator",
        runners=[
            RunnerConfig(
                runner="codex",
                prompt_path=INTEGRATOR_CODEX_PROMPT,
                model=CODEX_MODEL,
                reasoning_effort=CODEX_REASONING_XHIGH,
                new_console=True,
            )
        ],
        input_files=[integrator_input_path],
        input_rename={integrator_input_path.name: "input.md"},
        reference_files=reference_files,
        reference_rename=reference_rename,
        deliver_dir=_relative_to_repo(tutor_session_dir),
        deliver_rename={"output.md": "note.md"},
        clean_markdown=True,
    )
    run_agent_job(job, event_callback=event_callback)

    if not note_path.is_file():
        raise FileNotFoundError(f"integrator output not found at {note_path}")

    note_content = note_path.read_text(encoding="utf-8").lstrip("\ufeff")
    note_lines = note_content.splitlines(keepends=True)
    summary_line = ""
    summary_index = None
    for idx, line in enumerate(note_lines):
        if not line.strip():
            continue
        summary_line = re.sub(r"^[#\s]+", "", line).strip()
        summary_index = idx
        if summary_line:
            break
    if not summary_line:
        summary_line = "笔记标题"
    if summary_index is not None:
        del note_lines[summary_index]
    note_body = "".join(note_lines)
    note_wrapped = (
        '\n\n<details class="note"> \n'
        f"<summary>{summary_line}</summary> \n"
        '<div markdown="1">\n\n'
        f"{note_body}"
        "\n\n</div> \n</details>\n\n"
    )
    note_path.write_text(note_wrapped, encoding="utf-8", newline="\n")

    img_explainer_dir = group_dir / "img_explainer_data"
    enhanced_md = img_explainer_dir / "enhanced.md"
    if not enhanced_md.is_file():
        raise FileNotFoundError(f"enhanced.md not found at {enhanced_md}")

    enhanced_content = enhanced_md.read_text(encoding="utf-8")
    focus_content = focus_md.read_text(encoding="utf-8")
    if not focus_content.strip():
        raise ValueError(f"focus.md is empty: {focus_md}")

    match_start = -1
    match_text = ""
    for candidate in (focus_content, focus_content.rstrip("\n"), focus_content.strip()):
        if not candidate:
            continue
        match_start = enhanced_content.find(candidate)
        if match_start >= 0:
            match_text = candidate
            break
    if match_start < 0:
        raise ValueError("focus.md content not found in enhanced.md for insertion.")

    insert_at = match_start + len(match_text)
    updated_enhanced = enhanced_content[:insert_at] + note_wrapped + enhanced_content[insert_at:]
    enhanced_md.write_text(updated_enhanced, encoding="utf-8", newline="\n")
    _emit_asset_event(
        event_callback,
        "completed",
        f"Completed integrate flow for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
        artifact_path=enhanced_md,
        payload=_asset_payload(asset_name, group_idx=group_idx, tutor_idx=tutor_idx),
    )
    return enhanced_md


_MANUSCRIPT_IMAGE_RE = re.compile(r"^manuscript_(\d+)\.png$", re.IGNORECASE)


def _list_tutor_manuscript_images(tutor_session_dir: Path) -> list[Path]:
    indexed: list[tuple[int, Path]] = []
    if tutor_session_dir.is_dir():
        for entry in tutor_session_dir.iterdir():
            if not entry.is_file():
                continue
            match = _MANUSCRIPT_IMAGE_RE.match(entry.name)
            if not match:
                continue
            try:
                idx = int(match.group(1))
            except (TypeError, ValueError):
                continue
            indexed.append((idx, entry))

    if indexed:
        indexed.sort(key=lambda item: item[0])
        return [path for _, path in indexed]

    single = tutor_session_dir / "manuscript.png"
    if single.is_file():
        return [single]

    legacy = tutor_session_dir / "student.png"
    if legacy.is_file():
        return [legacy]

    return []


def bug_finder(
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    """
    Review manuscript images against note.md for a tutor session and write bugs.md.

    Uses prompts/bug_finder with:
    - input/manuscript_1.png (and manuscript_2.png, ...)
    - references/original.md (renamed from note.md)
    - output/bugs.md (delivered to tutor_data/<tutor_idx>/bugs.md)
    """
    _emit_asset_event(
        event_callback,
        "started",
        f"Starting bug finder for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
        payload=_asset_payload(asset_name, group_idx=group_idx, tutor_idx=tutor_idx),
    )
    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")

    manuscript_images = _list_tutor_manuscript_images(tutor_session_dir)
    if not manuscript_images:
        raise FileNotFoundError(
            f"No manuscript images found in {tutor_session_dir} (expected manuscript_*.png)"
        )

    note_path = tutor_session_dir / "note.md"
    if not note_path.is_file():
        raise FileNotFoundError(f"note.md not found: {note_path}")

    bugs_path = tutor_session_dir / "bugs.md"

    manuscript_refs = " ".join(
        f"@input/manuscript_{idx}.png" for idx in range(1, len(manuscript_images) + 1)
    )
    extra_message = f"{manuscript_refs} 是手稿笔记，开始"
    input_rename = {
        image.name: f"manuscript_{idx}.png" for idx, image in enumerate(manuscript_images, start=1)
    }

    job = AgentJob(
        name="bug_finder",
        runners=[
            RunnerConfig(
                runner="gemini",
                prompt_path=BUG_FINDER_GEMINI_PROMPT,
                model=GEMINI_MODEL,
                new_console=True,
                extra_message=extra_message,
            )
        ],
        input_files=manuscript_images,
        input_rename=input_rename,
        reference_files=[note_path],
        reference_rename={note_path.name: "original.md"},
        deliver_dir=_relative_to_repo(tutor_session_dir),
        deliver_rename={"bugs.md": "bugs.md"},
        clean_markdown=True,
    )
    run_agent_job(job, event_callback=event_callback)

    if not bugs_path.is_file():
        raise FileNotFoundError(f"bug_finder output not found at {bugs_path}")
    _emit_asset_event(
        event_callback,
        "completed",
        f"Completed bug finder for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
        artifact_path=bugs_path,
        payload=_asset_payload(asset_name, group_idx=group_idx, tutor_idx=tutor_idx),
    )
    return bugs_path


def ask_re_tutor(
    question: str,
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    """
    Run the re_tutor agent in Feynman mode and append Q/A to tutor_data/<tutor_idx>/bugs.md.

    Uses prompts/re_tutor with:
    - input/manuscript_1.png (and manuscript_2.png, ...)
    - input/bugs.md
    - references/original.md (renamed from note.md)
    - output/output.md (delivered as re_tutor_output.md)
    """
    normalized_question = (
        question.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "").strip()
    )
    if not normalized_question:
        raise ValueError("Question is required.")
    _emit_asset_event(
        event_callback,
        "started",
        f"Starting re-tutor flow for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
        payload=_asset_payload(
            asset_name,
            group_idx=group_idx,
            tutor_idx=tutor_idx,
            extra={"question": normalized_question},
        ),
    )

    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")

    manuscript_images = _list_tutor_manuscript_images(tutor_session_dir)
    if not manuscript_images:
        raise FileNotFoundError(
            f"No manuscript images found in {tutor_session_dir} (expected manuscript_*.png)"
        )

    note_path = tutor_session_dir / "note.md"
    if not note_path.is_file():
        raise FileNotFoundError(f"note.md not found: {note_path}")

    bugs_path = tutor_session_dir / "bugs.md"
    if not bugs_path.is_file():
        raise FileNotFoundError(f"bugs.md not found: {bugs_path}")

    input_rename = {
        image.name: f"manuscript_{idx}.png" for idx, image in enumerate(manuscript_images, start=1)
    }
    input_rename[bugs_path.name] = "bugs.md"

    re_tutor_output_name = "re_tutor_output.md"
    job = AgentJob(
        name="re_tutor",
        runners=[
            RunnerConfig(
                runner="gemini",
                prompt_path=RE_TUTOR_GEMINI_PROMPT,
                model=GEMINI_MODEL,
                new_console=True,
                extra_message=f"{normalized_question}把解答保存至 output/output.md",
            )
        ],
        input_files=[*manuscript_images, bugs_path],
        input_rename=input_rename,
        reference_files=[note_path],
        reference_rename={note_path.name: "original.md"},
        deliver_dir=_relative_to_repo(tutor_session_dir),
        deliver_rename={"output.md": re_tutor_output_name},
        clean_markdown=True,
    )
    run_agent_job(job, event_callback=event_callback)

    answer_path = tutor_session_dir / re_tutor_output_name
    if not answer_path.is_file():
        raise FileNotFoundError(f"re_tutor output not found at {answer_path}")

    bugs_text = bugs_path.read_text(encoding="utf-8-sig").lstrip("\ufeff").rstrip()
    answer_text = answer_path.read_text(encoding="utf-8-sig").lstrip("\ufeff").lstrip()

    separator = "\n\n" if bugs_text else ""
    appended = (
        f"{bugs_text}{separator}"
        f"## 提问\n\n{normalized_question}\n\n"
        f"## 回答\n\n{answer_text}\n"
    )
    bugs_path.write_text(appended, encoding="utf-8", newline="\n")
    _clean_markdown_file(bugs_path)
    _emit_asset_event(
        event_callback,
        "completed",
        f"Completed re-tutor flow for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
        artifact_path=bugs_path,
        payload=_asset_payload(
            asset_name,
            group_idx=group_idx,
            tutor_idx=tutor_idx,
            extra={"question": normalized_question},
        ),
    )
    return bugs_path


def insert_feynman_original_image(asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    """
    Insert a "student original image" note block into img_explainer_data/enhanced.md for the given tutor session.

    Copies tutor_data/<tutor_idx>/manuscript_*.png to img_explainer_data/manuscript_<tutor_idx>*.png and references
    them from the inserted markdown block.
    """
    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")

    manuscript_images = _list_tutor_manuscript_images(tutor_session_dir)
    if not manuscript_images:
        raise FileNotFoundError(
            f"No manuscript images found in {tutor_session_dir} (expected manuscript_*.png)"
        )

    focus_md = tutor_session_dir / "focus.md"
    if not focus_md.is_file():
        raise FileNotFoundError(f"tutor focus.md not found: {focus_md}")

    img_explainer_dir = group_dir / "img_explainer_data"
    enhanced_md = img_explainer_dir / "enhanced.md"
    if not enhanced_md.is_file():
        raise FileNotFoundError(f"enhanced.md not found at {enhanced_md}")

    target_names: list[str] = []
    for idx, source in enumerate(manuscript_images, start=1):
        target_name = (
            f"manuscript_{tutor_idx}.png" if idx == 1 else f"manuscript_{tutor_idx}_{idx}.png"
        )
        target_image = img_explainer_dir / target_name
        target_image.unlink(missing_ok=True)
        shutil.copy2(source, target_image)
        target_names.append(target_name)

    image_markdown = "\n\n".join(
        f"![你的推导](img_explainer_data/{name})" for name in target_names
    )
    original_block = (
        "\n\n<details class=\"note\">\n"
        "<summary>原图</summary> \n"
        "<div markdown=\"1\">\n\n"
        f"{image_markdown}\n\n\n"
        "</div>\n"
        "</details>\n\n"
    )
    "\n\n".join(
        f"![你的推导](./img_explainer_data/{name})" for name in target_names
    )

    enhanced_content = enhanced_md.read_text(encoding="utf-8")

    focus_content = focus_md.read_text(encoding="utf-8")
    if not focus_content.strip():
        raise ValueError(f"focus.md is empty: {focus_md}")

    match_start = -1
    match_text = ""
    for candidate in (focus_content, focus_content.rstrip("\n"), focus_content.strip()):
        if not candidate:
            continue
        match_start = enhanced_content.find(candidate)
        if match_start >= 0:
            match_text = candidate
            break
    if match_start < 0:
        raise ValueError("focus.md content not found in enhanced.md for insertion.")

    insert_at = match_start + len(match_text)

    note_path = tutor_session_dir / "note.md"
    note_wrapped = ""
    if note_path.is_file():
        try:
            note_wrapped = note_path.read_text(encoding="utf-8").lstrip("\ufeff")
        except Exception:  # pragma: no cover - defensive
            note_wrapped = ""
    if note_wrapped:
        note_pos = enhanced_content.find(note_wrapped, insert_at)
        if note_pos >= 0:
            insert_at = note_pos + len(note_wrapped)
        else:
            enhanced_content = (
                enhanced_content[:insert_at] + note_wrapped + enhanced_content[insert_at:]
            )
            insert_at += len(note_wrapped)

    updated_enhanced = (
        enhanced_content[:insert_at] + original_block + enhanced_content[insert_at:]
    )
    enhanced_md.write_text(updated_enhanced, encoding="utf-8", newline="\n")
    return enhanced_md


def create_student_note(
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    """
    Convert tutor_data/<tutor_idx>/manuscript_1.png (and manuscript_2.png, ...) into note_student.md via the
    manuscript prompt, then insert it into
    img_explainer_data/enhanced.md.
    """
    _emit_asset_event(
        event_callback,
        "started",
        f"Starting student note flow for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
        payload=_asset_payload(asset_name, group_idx=group_idx, tutor_idx=tutor_idx),
    )
    group_dir = get_group_data_dir(asset_name) / str(group_idx)
    if not group_dir.is_dir():
        raise FileNotFoundError(
            f"Group data directory not found for asset '{asset_name}', group {group_idx}: {group_dir}"
        )

    tutor_session_dir = group_dir / "tutor_data" / str(tutor_idx)
    if not tutor_session_dir.is_dir():
        raise FileNotFoundError(f"tutor session directory not found: {tutor_session_dir}")

    manuscript_images = _list_tutor_manuscript_images(tutor_session_dir)
    if not manuscript_images:
        raise FileNotFoundError(
            f"No manuscript images found in {tutor_session_dir} (expected manuscript_*.png)"
        )

    focus_md = tutor_session_dir / "focus.md"
    if not focus_md.is_file():
        raise FileNotFoundError(f"tutor focus.md not found: {focus_md}")

    img_explainer_dir = group_dir / "img_explainer_data"
    enhanced_md = img_explainer_dir / "enhanced.md"
    if not enhanced_md.is_file():
        raise FileNotFoundError(f"enhanced.md not found at {enhanced_md}")

    note_student_path = tutor_session_dir / "note_student.md"

    job = AgentJob(
        name="manuscript",
        runners=[
            RunnerConfig(
                runner="gemini",
                prompt_path=MANUSCRIPT_GEMINI_PROMPT,
                model=GEMINI_MODEL,
                new_console=True,
                extra_message=(
                    " ".join(
                        f"@input/manuscript_{idx}.png"
                        for idx in range(1, len(manuscript_images) + 1)
                    )
                    + " 是手稿笔记，开始"
                ),
            )
        ],
        input_files=manuscript_images,
        input_rename={
            image.name: f"manuscript_{idx}.png"
            for idx, image in enumerate(manuscript_images, start=1)
        },
        deliver_dir=_relative_to_repo(tutor_session_dir),
        deliver_rename={"output.md": "note_student.md"},
        clean_markdown=True,
    )
    run_agent_job(job, event_callback=event_callback)

    if not note_student_path.is_file():
        raise FileNotFoundError(f"manuscript output not found at {note_student_path}")

    raw_note_student = note_student_path.read_text(encoding="utf-8").lstrip("\ufeff")
    note_student_wrapped = (
        '\n\n<details class="note"> \n'
        "<summary>你的推导</summary>\n"
        '<div markdown="1">\n\n'
        f"{raw_note_student}"
        "\n\n</div> \n</details>\n\n"
    )
    note_student_path.write_text(note_student_wrapped, encoding="utf-8", newline="\n")

    enhanced_content = enhanced_md.read_text(encoding="utf-8")

    focus_content = focus_md.read_text(encoding="utf-8")
    if not focus_content.strip():
        raise ValueError(f"focus.md is empty: {focus_md}")

    match_start = -1
    match_text = ""
    for candidate in (focus_content, focus_content.rstrip("\n"), focus_content.strip()):
        if not candidate:
            continue
        match_start = enhanced_content.find(candidate)
        if match_start >= 0:
            match_text = candidate
            break
    if match_start < 0:
        raise ValueError("focus.md content not found in enhanced.md for insertion.")

    insert_at = match_start + len(match_text)

    note_path = tutor_session_dir / "note.md"
    note_wrapped = ""
    if note_path.is_file():
        try:
            note_wrapped = note_path.read_text(encoding="utf-8").lstrip("\ufeff")
        except Exception:  # pragma: no cover - defensive
            note_wrapped = ""
    if note_wrapped:
        note_pos = enhanced_content.find(note_wrapped, insert_at)
        if note_pos >= 0:
            insert_at = note_pos + len(note_wrapped)
        else:
            enhanced_content = (
                enhanced_content[:insert_at] + note_wrapped + enhanced_content[insert_at:]
            )
            insert_at += len(note_wrapped)

    target_names = [
        f"manuscript_{tutor_idx}.png" if idx == 1 else f"manuscript_{tutor_idx}_{idx}.png"
        for idx in range(1, len(manuscript_images) + 1)
    ]

    image_markdown = "\n\n".join(
        f"![你的推导](img_explainer_data/{name})" for name in target_names
    )
    original_block = (
        "\n\n<details class=\"note\">\n"
        "<summary>原图</summary> \n"
        "<div markdown=\"1\">\n\n"
        f"{image_markdown}\n\n\n"
        "</div>\n"
        "</details>\n\n"
    )
    legacy_image_markdown = "\n\n".join(
        f"![你的推导](./img_explainer_data/{name})" for name in target_names
    )
    legacy_original_block = (
        "\n\n<details class=\"note\">\n"
        "<summary>原图</summary> \n"
        "<div markdown=\"1\">\n\n"
        f"{legacy_image_markdown}\n\n\n"
        "</div>\n"
        "</details>\n\n"
    )

    def _find_last_end(content: str, block: str, start: int) -> int | None:
        pos = content.find(block, start)
        if pos < 0:
            return None
        last_end = pos + len(block)
        while True:
            next_pos = content.find(block, last_end)
            if next_pos < 0:
                return last_end
            last_end = next_pos + len(block)

    for block in (original_block, legacy_original_block):
        end_pos = _find_last_end(enhanced_content, block, insert_at)
        if end_pos is not None:
            insert_at = max(insert_at, end_pos)

    updated_enhanced = (
        enhanced_content[:insert_at] + note_student_wrapped + enhanced_content[insert_at:]
    )
    enhanced_md.write_text(updated_enhanced, encoding="utf-8", newline="\n")
    _emit_asset_event(
        event_callback,
        "completed",
        f"Completed student note flow for asset '{asset_name}', group {group_idx}, tutor {tutor_idx}.",
        artifact_path=enhanced_md,
        payload=_asset_payload(asset_name, group_idx=group_idx, tutor_idx=tutor_idx),
    )
    return enhanced_md


def fix_latex(
    markdown_path: str | Path,
    *,
    event_callback: WorkflowEventCallback | None = None,
) -> Path:
    path = Path(markdown_path)
    if not path.is_file():
        raise FileNotFoundError(f"Markdown not found: {path}")
    if path.suffix.lower() != ".md":
        raise ValueError(f"fix_latex only supports markdown files: {path}")
    _emit_asset_event(
        event_callback,
        "started",
        f"Starting latex fix for {path.name}.",
        payload={"markdown_path": str(path)},
    )

    job = AgentJob(
        name="latex_fixer",
        runners=[
            RunnerConfig(
                runner="codex",
                prompt_path=LATEX_FIXER_CODEX_PROMPT,
                model=CODEX_MODEL,
                reasoning_effort=CODEX_REASONING_MEDIUM,
                new_console=True,
                extra_message="Fix latex in @output/output.md and save to output/output.md.",
            )
        ],
        output_seed_files=[path],
        output_rename={path.name: "output.md"},
        deliver_dir=path.parent,
        deliver_rename={"output.md": path.name},
        clean_markdown=True,
    )
    run_agent_job(job, event_callback=event_callback)

    if not path.is_file():
        raise FileNotFoundError(f"Latex fixer output not found at {path}")
    _emit_asset_event(
        event_callback,
        "completed",
        f"Completed latex fix for {path.name}.",
        artifact_path=path,
        payload={"markdown_path": str(path)},
    )
    return path


def asset_init(
    pdf_path: str | Path,
    asset_name: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
    *,
    rendered_pdf_path: str | Path | None = None,
    content_list_path: str | Path | None = None,
    event_callback: WorkflowEventCallback | None = None,
) -> AssetInitResult:
    """
    Run the PDF -> image -> markdown -> extractor pipeline for a given asset.

    If the source is a markdown file, skip img2md and use the markdown as output.md.

    Args:
        pdf_path: Source PDF (or Markdown) to process.
        asset_name: Name of the asset directory (defaults to source stem).

    Returns:
        AssetInitResult describing generated files and asset locations.
    """
    source_path = Path(pdf_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")

    is_markdown = source_path.suffix.lower() == ".md"
    resolved_asset_name = asset_name or source_path.stem
    asset_dir = ASSETS_ROOT / resolved_asset_name
    references_dir = asset_dir / "references"
    img2md_output_dir = asset_dir / "img2md_output"
    img2md_output_dir.mkdir(parents=True, exist_ok=True)
    _emit_asset_event(
        event_callback,
        "started",
        f"Starting asset initialization for '{resolved_asset_name}'.",
        payload=_asset_payload(
            resolved_asset_name,
            extra={
                "source_path": str(source_path),
                "is_markdown": is_markdown,
            },
        ),
    )

    def _notify(
        message: str,
        *,
        event_type: WorkflowEventType = "log",
        progress: float | None = None,
        artifact_path: str | Path | None = None,
    ) -> None:
        if progress_callback:
            try:
                progress_callback(message)
            except Exception:  # pragma: no cover - defensive
                pass
        _emit_asset_event(
            event_callback,
            event_type,
            message,
            progress=progress,
            artifact_path=artifact_path,
            payload=_asset_payload(
                resolved_asset_name,
                extra={
                    "source_path": str(source_path),
                    "is_markdown": is_markdown,
                },
            ),
        )

    if is_markdown:
        _notify("Preparing markdown asset...", progress=0.05)
        logger.info("Preparing markdown asset '%s' from %s", resolved_asset_name, source_path)
        asset_dir.mkdir(parents=True, exist_ok=True)
        _clean_directory(references_dir)

        output_md = img2md_output_dir / "output.md"
        output_md.write_text(
            source_path.read_text(encoding="utf-8-sig"),
            encoding="utf-8",
            newline="\n",
        )
        _clean_markdown_file(output_md)

        if rendered_pdf_path is not None:
            rendered_pdf_path = Path(rendered_pdf_path)
            if not rendered_pdf_path.is_file():
                raise FileNotFoundError(f"Rendered PDF not found: {rendered_pdf_path}")
            _notify("Copying rendered PDF...", progress=0.2)
            raw_pdf_path = _copy_raw_pdf(rendered_pdf_path, asset_dir)
        else:
            _notify("Rendering markdown to PDF...", progress=0.2)
            raw_pdf_path = _render_markdown_to_pdf(output_md, asset_dir / "raw.pdf")
        if content_list_path is not None:
            _notify("Saving content list JSON...", progress=0.24)
            saved_path, unified_path, item_count = save_asset_content_lists(
                asset_dir=asset_dir,
                source_path=content_list_path,
                pdf_path=raw_pdf_path,
            )
            _notify(f"Stored {saved_path.name}.")
            _notify(f"Stored {unified_path.name} with {item_count} item(s).")
    else:
        _notify("Copying PDF and preparing directories...", progress=0.05)
        logger.info("Preparing asset '%s' from %s", resolved_asset_name, source_path)
        raw_pdf_path = _copy_raw_pdf(source_path, asset_dir)
        if content_list_path is not None:
            _notify("Saving content list JSON...", progress=0.08)
            saved_path, unified_path, item_count = save_asset_content_lists(
                asset_dir=asset_dir,
                source_path=content_list_path,
                pdf_path=raw_pdf_path,
            )
            _notify(f"Stored {saved_path.name}.")
            _notify(f"Stored {unified_path.name} with {item_count} item(s).")
        _clean_directory(references_dir)

        images_dir = asset_dir / "img2md_images"
        _clean_directory(images_dir)

        _notify("Converting PDF pages to images...", progress=0.15)
        image_paths = convert_pdf_to_images(source_path, images_dir, dpi=300)
        if not image_paths:
            raise RuntimeError(f"No images rendered from {source_path}")
        logger.info("Converted %d page(s) to %s", len(image_paths), images_dir)

        _notify("Running img2md...", progress=0.3)
        img2md_output_dir.mkdir(parents=True, exist_ok=True)

        image_pattern = re.compile(r".*_(\d{3})\.png$", re.IGNORECASE)
        def _image_sort_key(path: Path) -> tuple[int, int | str]:
            match = image_pattern.match(path.name)
            if match:
                return 0, int(match.group(1))
            return 1, path.name.lower()

        sorted_images = sorted(image_paths, key=_image_sort_key)

        jobs_by_output_name: dict[str, AgentJob] = {}
        expected_output_names: list[str] = []
        used_suffixes: set[str] = set()

        for idx, image_path in enumerate(sorted_images):
            match = image_pattern.match(image_path.name)
            raw_suffix = match.group(1) if match else f"{idx + 1:03d}"
            suffix = raw_suffix if raw_suffix not in used_suffixes else f"{idx + 1:03d}"
            used_suffixes.add(suffix)
            output_name = f"output_{suffix}.md"
            expected_output_names.append(output_name)
            jobs_by_output_name[output_name] = AgentJob(
                name=f"img2md_{suffix}",
                runners=[
                    RunnerConfig(
                        runner="gemini",
                        prompt_path=IMG2MD_GEMINI_PROMPT,
                        model=GEMINI_MODEL,
                        new_console=True,
                    )
                ],
                input_files=[image_path],
                input_rename={image_path.name: "input.png"},
                deliver_dir=_relative_to_repo(img2md_output_dir),
                deliver_rename={"output.md": output_name},
                clean_markdown=True,
            )

        expected_output_set = set(expected_output_names)
        stale_pattern = re.compile(r"output_(\d{3})\.md$", re.IGNORECASE)
        for path in img2md_output_dir.iterdir():
            if path.is_file() and stale_pattern.match(path.name) and path.name not in expected_output_set:
                path.unlink(missing_ok=True)

        def _is_valid_img2md_page(path: Path) -> bool:
            if not path.is_file():
                return False
            try:
                return path.stat().st_size >= 5
            except OSError:  # pragma: no cover - filesystem race/permission
                return False

        def _missing_outputs() -> list[str]:
            missing: list[str] = []
            for name in expected_output_names:
                if not _is_valid_img2md_page(img2md_output_dir / name):
                    missing.append(name)
            return missing

        attempt = 0
        while True:
            missing = _missing_outputs()
            if not missing:
                break
            if attempt > IMG2MD_MISSING_RETRY_LIMIT:
                break
            attempt += 1
            if attempt > 1:
                _notify(f"Retrying img2md for {len(missing)} missing page(s)...", progress=0.45)
            for name in missing:
                (img2md_output_dir / name).unlink(missing_ok=True)
            jobs = [jobs_by_output_name[name] for name in missing]
            try:
                run_agent_jobs(jobs, max_workers=len(jobs), event_callback=event_callback)
            except Exception as exc:
                logger.warning("img2md attempt %d failed: %s", attempt, exc)

        missing = _missing_outputs()
        if missing:
            raise FileNotFoundError(
                f"img2md missing outputs under {img2md_output_dir}: {', '.join(missing)}"
            )

        merged_output = merge_outputs(
            img2md_output_dir,
            r"output_(\d{3})\.md",
            "output.md",
        )
        _clean_markdown_file(merged_output)

        try:
            _safe_rmtree(images_dir)
        except Exception:
            logger.warning("Failed to remove temp images directory: %s", images_dir)

    output_md = img2md_output_dir / "output.md"
    if not output_md.is_file():
        raise FileNotFoundError(f"img2md output.md not found for asset '{resolved_asset_name}'")

    _notify("Running extractors...", progress=0.75)
    extractor_jobs: list[AgentJob] = []
    for agent_name in EXTRACTOR_AGENTS:
        prompt_path = EXTRACTOR_PROMPTS.get(agent_name)
        output_name = EXTRACTOR_OUTPUT_NAMES[agent_name]
        if prompt_path is None:
            raise FileNotFoundError(f"Missing extractor prompt for {agent_name}")
        extractor_jobs.append(
            AgentJob(
                name=f"extractor_{agent_name}",
                runners=[
                    RunnerConfig(
                        runner="codex",
                        prompt_path=prompt_path,
                        model=CODEX_MODEL,
                        reasoning_effort=CODEX_REASONING_XHIGH,
                        new_console=True,
                    )
                ],
                input_files=[output_md],
                input_rename={output_md.name: "input.md"},
                deliver_dir=_relative_to_repo(references_dir),
                deliver_rename={output_name: output_name},
                clean_markdown=True,
            )
        )

    extractor_results = run_agent_jobs(
        extractor_jobs,
        max_workers=len(extractor_jobs),
        event_callback=event_callback,
    )
    reference_files: list[Path] = [
        path for result in extractor_results for path in result.delivered
    ]
    if not reference_files:
        raise FileNotFoundError("Extractor produced no reference files")

    logger.info("Moved %d file(s) to %s", len(reference_files), references_dir)
    result = AssetInitResult(
        asset_dir=asset_dir,
        references_dir=references_dir,
        raw_pdf_path=raw_pdf_path,
        reference_files=reference_files,
    )
    _notify(
        f"Asset '{resolved_asset_name}' initialized.",
        event_type="completed",
        progress=1.0,
        artifact_path=asset_dir,
    )
    return result
