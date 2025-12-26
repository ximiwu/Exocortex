from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List

from PySide6 import QtGui, QtPrintSupport

from agent_manager import (
    AgentCallbacks,
    AgentJob,
    RunnerConfig,
    clean_markdown_file as _agent_clean_markdown_file,
    merge_outputs,
    run_agent_job,
    run_agent_jobs,
)


logger = logging.getLogger(__name__)

try:
    import markdown
except ImportError:  # pragma: no cover - optional dependency guard
    markdown = None

try:
    import pymdownx.arithmatex  # type: ignore  # noqa: F401

    _ARITHMETEX_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    _ARITHMETEX_AVAILABLE = False

def _detect_repo_root(module_dir: Path) -> Path:
    markers = ("prompts", "assets", "agent_workspace", "README.md")
    for candidate in (module_dir, *module_dir.parents):
        if any((candidate / marker).exists() for marker in markers):
            return candidate
    return module_dir


def _runtime_start_dir() -> Path:
    if "__compiled__" in globals():
        return Path(sys.argv[0]).resolve().parent
    return Path(__file__).resolve().parent


def _relative_to_repo(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


REPO_ROOT = _detect_repo_root(_runtime_start_dir())
PROMPTS_DIR = REPO_ROOT / "prompts"
ASSETS_ROOT = REPO_ROOT / "assets"
REFERENCE_RENDER_DPI = 130  # Keep in sync with pdf_block_gui_lib.main_window.DEFAULT_RENDER_DPI

EXTRACTOR_AGENTS: tuple[str, ...] = ("background", "concept", "formula")

CODEX_MODEL = "gpt-5.2"
CODEX_REASONING_HIGH = "high"
CODEX_REASONING_MEDIUM = "medium"
GEMINI_MODEL = "gemini-3-pro-preview"


def _prompt_path(*parts: str) -> Path:
    return PROMPTS_DIR.joinpath(*parts)


IMG2MD_CODEX_PROMPT = _prompt_path("img2md", "codex", "AGENTS.md")
IMG_EXPLAINER_CODEX_PROMPT = _prompt_path("img_explainer", "codex", "AGENTS.md")
IMG_EXPLAINER_GEMINI_PROMPT = _prompt_path("img_explainer", "gemini", "GEMINI.md")
ENHANCER_GEMINI_PROMPT = _prompt_path("enhancer", "gemini", "GEMINI.md")
INTEGRATOR_CODEX_PROMPT = _prompt_path("integrator", "codex", "AGENTS.md")
TUTOR_GEMINI_PROMPT = _prompt_path("tutor", "gemini", "GEMINI.md")
BUG_FINDER_GEMINI_PROMPT = _prompt_path("bug_finder", "gemini", "GEMINI.md")
MANUSCRIPT_GEMINI_PROMPT = _prompt_path("manuscript2md", "gemini", "GEMINI.md")
LATEX_FIXER_GEMINI_PROMPT = _prompt_path("latex_fixer", "GEMINI.md")

EXTRACTOR_PROMPTS = {
    "background": _prompt_path("extractor", "background", "codex", "AGENTS.md"),
    "concept": _prompt_path("extractor", "concept", "codex", "AGENTS.md"),
    "formula": _prompt_path("extractor", "formula", "codex", "AGENTS.md"),
}

EXTRACTOR_OUTPUT_NAMES = {
    "background": "background.md",
    "concept": "concept.md",
    "formula": "formula.md",
}


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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    serialized = json.dumps(data, ensure_ascii=False, indent=2)
    tmp_path.write_text(serialized, encoding="utf-8")
    tmp_path.replace(path)
    return path


@dataclass(frozen=True)
class AssetInitResult:
    asset_dir: Path
    references_dir: Path
    raw_pdf_path: Path
    reference_files: list[Path]


@dataclass(frozen=True)
class BlockRect:
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_dict(cls, data: dict) -> BlockRect:
        try:
            return cls(
                x=float(data["x"]),
                y=float(data["y"]),
                width=float(data["width"]),
                height=float(data["height"]),
            )
        except Exception as exc:  # pragma: no cover - defensive parsing
            raise ValueError(f"Invalid rect: {data}") from exc

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class BlockRecord:
    block_id: int
    page_index: int
    rect: BlockRect
    group_idx: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> BlockRecord:
        try:
            block_id = int(data.get("block_id", data.get("id")))
            page_index = int(data["page_index"])
            rect = BlockRect.from_dict(data["rect"])
            group_idx_raw = data.get("group_idx")
            group_idx = int(group_idx_raw) if group_idx_raw is not None else None
        except Exception as exc:  # pragma: no cover - defensive parsing
            raise ValueError(f"Invalid block record: {data}") from exc
        return cls(block_id=block_id, page_index=page_index, rect=rect, group_idx=group_idx)

    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "page_index": self.page_index,
            "rect": self.rect.to_dict(),
            "group_idx": self.group_idx,
        }


@dataclass(frozen=True)
class BlockData:
    blocks: List[BlockRecord]
    merge_order: List[int]
    next_block_id: int

    @classmethod
    def empty(cls) -> BlockData:
        return cls(blocks=[], merge_order=[], next_block_id=1)

    @classmethod
    def from_dict(cls, data: dict) -> BlockData:
        blocks_raw = data.get("blocks", [])
        merge_order_raw = data.get("merge_order", [])
        next_block_id = int(data.get("next_block_id", 1))

        blocks: list[BlockRecord] = []
        for entry in blocks_raw:
            try:
                blocks.append(BlockRecord.from_dict(entry))
            except ValueError as exc:  # pragma: no cover - defensive parsing
                logging.warning("Skipping invalid block entry: %s", exc)

        merge_order: list[int] = []
        for bid in merge_order_raw:
            try:
                merge_order.append(int(bid))
            except Exception:  # pragma: no cover - defensive parsing
                logging.warning("Invalid merge_order entry: %s", bid)

        if next_block_id <= 0:
            next_block_id = 1
        return cls(blocks=blocks, merge_order=merge_order, next_block_id=next_block_id)

    def to_dict(self) -> dict:
        return {
            "blocks": [block.to_dict() for block in self.blocks],
            "merge_order": self.merge_order,
            "next_block_id": self.next_block_id,
        }


@dataclass(frozen=True)
class GroupRecord:
    group_idx: int
    block_ids: list[int]

    @classmethod
    def from_dict(cls, data: dict, *, default_idx: int | None = None) -> GroupRecord:
        try:
            idx_value = data.get("group_idx", default_idx)
            if idx_value is None:
                raise ValueError("Missing group_idx")
            group_idx = int(idx_value)
            raw_block_ids = data.get("block_ids", data.get("blocks", []))
            block_ids = list(dict.fromkeys(int(bid) for bid in raw_block_ids))
        except Exception as exc:  # pragma: no cover - defensive parsing
            raise ValueError(f"Invalid group record: {data}") from exc
        if not block_ids:
            raise ValueError("Group record must contain block_ids.")
        return cls(group_idx=group_idx, block_ids=block_ids)

    def to_dict(self) -> dict:
        return {
            "group_idx": self.group_idx,
            "block_ids": self.block_ids,
        }


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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    serialized = json.dumps(record.to_dict(), ensure_ascii=False, indent=2)
    tmp_path.write_text(serialized, encoding="utf-8")
    tmp_path.replace(path)
    return path


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


def _clean_directory(directory: Path) -> None:
    """Remove all files/subdirectories under the given directory."""
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.iterdir():
        if path.is_file() or path.is_symlink():
            path.unlink()
        else:
            _safe_rmtree(path)


def _render_markdown_to_pdf(markdown_path: Path, output_pdf: Path) -> Path:
    if markdown is None:
        raise RuntimeError("Missing 'markdown' package for rendering markdown.")

    text = markdown_path.read_text(encoding="utf-8-sig").lstrip("\ufeff")
    extensions = ["extra", "sane_lists", "fenced_code", "tables"]
    extension_configs: dict[str, dict[str, object]] = {}
    if _ARITHMETEX_AVAILABLE:
        extensions.append("pymdownx.arithmatex")
        extension_configs["pymdownx.arithmatex"] = {"generic": True}

    md = markdown.Markdown(
        extensions=extensions,
        extension_configs=extension_configs,
    )
    body = md.convert(text)

    styles = """
body { font-family: 'Times New Roman','Segoe UI','Helvetica Neue',Arial,sans-serif; font-size: 14px; line-height: 1.6; color: #222; padding: 18px; }
p { margin: 0.6em 0; }
pre { background: #f7f7f7; padding: 10px; border: 1px solid #e0e0e0; white-space: pre-wrap; }
code { font-family: 'Consolas','JetBrains Mono',monospace; font-size: 0.95em; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #dcdcdc; padding: 8px 10px; vertical-align: top; }
thead th { background: #f5f5f5; font-weight: 600; }
"""
    html_text = (
        "<!DOCTYPE html>"
        "<html><head><meta charset='UTF-8'>"
        f"<style>{styles}</style>"
        "</head><body>"
        f"{body}"
        "</body></html>"
    )

    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    printer = QtPrintSupport.QPrinter()
    printer.setOutputFormat(QtPrintSupport.QPrinter.PdfFormat)
    printer.setOutputFileName(str(output_pdf))
    printer.setPageSize(QtGui.QPageSize(QtGui.QPageSize.A4))
    printer.setResolution(150)

    document = QtGui.QTextDocument()
    document.setHtml(html_text)
    document.print_(printer)

    if not output_pdf.is_file():
        raise FileNotFoundError(f"Markdown PDF output not found: {output_pdf}")
    return output_pdf


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
    import pypdfium2 as pdfium

    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = prefix or pdf_path.stem
    scale = dpi / 72
    image_paths: list[Path] = []

    with pdfium.PdfDocument(pdf_path) as pdf:
        for page_index in range(len(pdf)):
            page = pdf.get_page(page_index)
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            image_path = output_dir / f"{base_name}_page_{page_index + 1:03d}.png"
            image.save(image_path)

            image_paths.append(image_path)

            image.close()
            bitmap.close()
            page.close()

    return image_paths


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
) -> list[QtGui.QImage]:
    """
    Render each block rect to a QImage cropped from its page(s).

    Block coordinates are stored in reference_dpi space (GUI reference render DPI) and must
    be scaled to the target renderer DPI before cropping.
    """
    from pdf_block_gui_lib.renderer import PdfRenderer

    renderer = PdfRenderer(dpi=dpi)
    renderer.open(str(pdf_path))
    images: list[QtGui.QImage] = []
    try:
        if reference_dpi <= 0:
            raise ValueError("reference_dpi must be positive.")
        scale = renderer.dpi / reference_dpi
        if scale <= 0:
            raise ValueError("Invalid render scale.")
        page_count = renderer.page_count
        page_widths_ref: list[float] = []
        page_heights_ref: list[float] = []
        page_offsets_ref: list[float] = [0.0]
        for page_index in range(page_count):
            width_px, height_px = renderer.page_pixel_size(page_index)
            width_ref = width_px / scale
            height_ref = height_px / scale
            page_widths_ref.append(width_ref)
            page_heights_ref.append(height_ref)
            page_offsets_ref.append(page_offsets_ref[-1] + height_ref)

        for block in blocks:
            if block.page_index < 0 or block.page_index >= page_count:
                raise ValueError(f"Invalid page index for block {block.block_id}: {block.page_index}")
            block_width_ref = float(block.rect.width)
            block_height_ref = float(block.rect.height)
            if block_width_ref <= 0 or block_height_ref <= 0:
                raise ValueError(f"Invalid block dimensions for block {block.block_id} on page {block.page_index}")
            block_x_ref = float(block.rect.x)
            block_y_ref = float(block.rect.y)

            base_page_width_ref = page_widths_ref[block.page_index]
            base_page_offset_ref = page_offsets_ref[block.page_index]
            block_center_offset = (block_x_ref + block_width_ref / 2) - base_page_width_ref / 2
            block_global_y0 = base_page_offset_ref + block_y_ref
            block_global_y1 = block_global_y0 + block_height_ref

            slices: list[QtGui.QImage] = []
            for page_index in range(page_count):
                page_top = page_offsets_ref[page_index]
                page_bottom = page_offsets_ref[page_index + 1]
                inter_top = max(block_global_y0, page_top)
                inter_bottom = min(block_global_y1, page_bottom)
                if inter_bottom <= inter_top:
                    continue

                local_y0_ref = inter_top - page_top
                local_height_ref = inter_bottom - inter_top

                page_width_ref = page_widths_ref[page_index]
                center_x_ref = page_width_ref / 2 + block_center_offset
                x0_ref = center_x_ref - block_width_ref / 2

                page_image = renderer.render_page(page_index)
                x = int(round(x0_ref * scale))
                y = int(round(local_y0_ref * scale))
                width = int(round(block_width_ref * scale))
                height = int(round(local_height_ref * scale))

                if x < 0:
                    width += x
                    x = 0
                if y < 0:
                    height += y
                    y = 0
                width = min(width, page_image.width() - x)
                height = min(height, page_image.height() - y)
                if width <= 0 or height <= 0:
                    continue
                slices.append(page_image.copy(x, y, width, height))

            if not slices:
                raise ValueError(f"Block {block.block_id} does not intersect any page.")
            if len(slices) == 1:
                images.append(slices[0])
            else:
                images.append(_stack_images_vertically(slices))
    finally:
        renderer.close()
    return images


def _stack_images_vertically(images: list[QtGui.QImage]) -> QtGui.QImage:
    """Stack images vertically into one combined QImage."""
    if not images:
        raise ValueError("No images provided to stack.")
    max_width = max(image.width() for image in images)
    total_height = sum(image.height() for image in images)
    canvas = QtGui.QImage(max_width, total_height, QtGui.QImage.Format_RGB888)
    canvas.fill(QtGui.QColor("white"))
    painter = QtGui.QPainter(canvas)
    try:
        y_offset = 0
        for image in images:
            painter.drawImage(0, y_offset, image)
            y_offset += image.height()
    finally:
        painter.end()
    return canvas


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


def load_block_data(asset_name: str) -> BlockData:
    """
    Load block data for an asset. Returns empty data if file is missing or invalid.
    """
    path = get_block_data_path(asset_name)
    if not path.is_file():
        return BlockData.empty()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return BlockData.from_dict(raw)
    except Exception as exc:  # pragma: no cover - defensive path
        logging.warning("Failed to load block data for '%s': %s", asset_name, exc)
        return BlockData.empty()


def save_block_data(asset_name: str, data: BlockData) -> Path:
    """
    Persist block data for an asset using an atomic replace.
    """
    path = get_block_data_path(asset_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    serialized = json.dumps(data.to_dict(), ensure_ascii=False, indent=2)
    tmp_path.write_text(serialized, encoding="utf-8")
    tmp_path.replace(path)
    return path


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
    asset_name: str, group_idx: int, *, on_gemini_ready: Callable[[Path], None] | None = None
) -> Path:
    """
    Generate img_explainer output for a group, archive initial outputs, and run enhancer.
    """
    target_dir = get_group_data_dir(asset_name) / str(group_idx) / "img_explainer_data"
    initial_dir = target_dir / "initial"
    enhanced_md = target_dir / "enhanced.md"

    legacy_output = target_dir / "output.md"
    legacy_gemini = target_dir / "output_gemini.md"
    initial_output = initial_dir / "output.md"
    initial_gemini_output = initial_dir / "output_gemini.md"

    def _run_enhancer() -> Path:
        job = AgentJob(
            name="enhancer",
            runners=[
                RunnerConfig(
                    runner="gemini",
                    prompt_path=ENHANCER_GEMINI_PROMPT,
                    model=GEMINI_MODEL,
                    new_console=True,
                    extra_message="以材料 @/output/main.md 的逻辑结构和数学深度 为主轴，将 @/input/supplement.md 中适合插入的片段增量式插入 @/output/main.md ，禁止删减 @/output/main.md的原有内容"
                )
            ],
            input_files=[initial_gemini_output],
            input_rename={initial_gemini_output.name: "supplement.md"},
            output_seed_files=[initial_output],
            output_rename={initial_output.name: "main.md"},
            deliver_dir=_relative_to_repo(target_dir),
            deliver_rename={"main.md": "enhanced.md"},
            clean_markdown=True,
        )
        run_agent_job(job)
        if not enhanced_md.is_file():
            raise FileNotFoundError(f"enhancer output not found: {enhanced_md}")
        _clean_markdown_file(enhanced_md)
        return enhanced_md

    if enhanced_md.is_file():
        _clean_markdown_file(enhanced_md)
        logger.info(
            "enhanced.md already exists for asset '%s', group %s; skipping regeneration.",
            asset_name,
            group_idx,
        )
        return enhanced_md

    if legacy_output.is_file() or legacy_gemini.is_file():
        initial_dir.mkdir(parents=True, exist_ok=True)
        if legacy_output.is_file() and not initial_output.is_file():
            shutil.move(str(legacy_output), str(initial_output))
        if legacy_gemini.is_file() and not initial_gemini_output.is_file():
            shutil.move(str(legacy_gemini), str(initial_gemini_output))

    if initial_output.is_file():
        _clean_markdown_file(initial_output)
    if initial_gemini_output.is_file():
        try:
            _clean_markdown_file(initial_gemini_output)
        except Exception as exc:  # pragma: no cover - defensive cleanup
            logger.warning(
                "Failed to clean existing Gemini output for '%s' (group %s): %s",
                asset_name,
                group_idx,
                exc,
            )
    if initial_output.is_file() and initial_gemini_output.is_file():
        logger.info(
            "Found initial img_explainer outputs for asset '%s', group %s; running enhancer only.",
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

    pdf_path = get_asset_pdf_path(asset_name)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found for asset '{asset_name}': {pdf_path}")

    blocks = _select_blocks_for_group(asset_name, group_idx)
    images = _render_blocks_to_images(pdf_path, blocks, dpi=300)
    merged_image = _stack_images_vertically(images)

    thesis_image_path = target_dir / "thesis.png"
    thesis_image_path.parent.mkdir(parents=True, exist_ok=True)
    if not merged_image.save(str(thesis_image_path)):
        raise RuntimeError(f"Failed to save rendered image to {thesis_image_path}")

    def _on_runner_finish(job_name: str, runner: RunnerConfig, workspace: Path, error: Exception | None) -> None:
        if runner.runner != "gemini":
            return
        gemini_output_path = workspace / "output" / "output_gemini.md"
        if not gemini_output_path.is_file():
            logger.warning(
                "Gemini finished but output_gemini.md not found at %s",
                gemini_output_path,
            )
            return
        try:
            initial_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(gemini_output_path, initial_gemini_output)
            _clean_markdown_file(initial_gemini_output)
            if on_gemini_ready is not None:
                on_gemini_ready(initial_gemini_output)
        except Exception as exc:  # pragma: no cover - defensive callback
            logger.warning(
                "Failed to archive Gemini output for '%s' (group %s): %s",
                asset_name,
                group_idx,
                exc,
            )

    callbacks = AgentCallbacks(on_finish=_on_runner_finish)

    job = AgentJob(
        name="img_explainer",
        runners=[
            RunnerConfig(
                runner="codex",
                prompt_path=IMG_EXPLAINER_CODEX_PROMPT,
                model=CODEX_MODEL,
                reasoning_effort=CODEX_REASONING_HIGH,
                new_console=True,
                extra_message="开始讲解 input/thesis.png，保存到 output.md中"
            ),
            RunnerConfig(
                runner="gemini",
                prompt_path=IMG_EXPLAINER_GEMINI_PROMPT,
                model=GEMINI_MODEL,
                new_console=True,
                extra_message="开始讲解 @input/thesis.png，保存到 output_gemini.md中"
            ),
        ],
        input_files=[thesis_image_path],
        input_rename={thesis_image_path.name: "thesis.png"},
        reference_files=reference_files,
        reference_rename=reference_rename,
        deliver_dir=_relative_to_repo(initial_dir),
        deliver_rename={
            "output.md": "output.md",
            "output_gemini.md": "output_gemini.md",
        },
        clean_markdown=True,
        callbacks=callbacks,
    )
    run_agent_job(job)

    if not initial_output.is_file():
        raise FileNotFoundError(f"img_explainer output not found: {initial_output}")
    if not initial_gemini_output.is_file():
        raise FileNotFoundError(
            f"img_explainer Gemini output not found: {initial_gemini_output}"
        )

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
    return focus_path


def ask_tutor(question: str, asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    """
    Run the tutor agent for a given question and tutor session, archive the response, and return it.

    Steps:
    1) Build input.md from focus.md + ask_history.
    2) Invoke tutor agent with the question.
    3) Move output.md into ask_history as the next sequential markdown (1, 2, ...), clean it, and prefix with Q/A headings.
    """
    normalized_question = (
        question.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "").strip()
    )
    if not normalized_question:
        raise ValueError("Question is required.")

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

    reference_files, reference_rename = _collect_reference_files(
        asset_name,
        include_entire_content=True,
    )

    job = AgentJob(
        name="tutor",
        runners=[
            RunnerConfig(
                runner="gemini",
                prompt_path=TUTOR_GEMINI_PROMPT,
                model=GEMINI_MODEL,
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
    run_agent_job(job)

    moved_output = ask_history_dir / output_name
    if not moved_output.is_file():
        raise FileNotFoundError(f"tutor output not found at {moved_output}")

    answer = moved_output.read_text(encoding="utf-8")
    header = f"## 提问：\n\n{normalized_question}\n\n## 回答：\n\n"
    moved_output.write_text(header + answer.lstrip(), encoding="utf-8", newline="\n")
    return moved_output



def integrate(asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    """
    Run the integrator agent for a tutor session, save a note, and insert it back into enhanced.md.

    Steps:
    1) Concatenate focus.md + ask_history into input.md.
    2) Invoke integrator agent.
    3) Clean markdown output and move it to tutor_data/<tutor_idx>/note.md.
    4) Wrap note.md in a <details class="note"> block.
    5) Insert the wrapped note block into img_explainer_data/enhanced.md at the end of the focus region.
    """
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
                reasoning_effort=CODEX_REASONING_HIGH,
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
    run_agent_job(job)

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


def bug_finder(asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    """
    Review manuscript images against note.md for a tutor session and write bugs.md.

    Uses prompts/bug_finder with:
    - input/manuscript_1.png (and manuscript_2.png, ...)
    - references/original.md (renamed from note.md)
    - output/bugs.md (delivered to tutor_data/<tutor_idx>/bugs.md)
    """
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
    run_agent_job(job)

    if not bugs_path.is_file():
        raise FileNotFoundError(f"bug_finder output not found at {bugs_path}")
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

    image_markdown = "\n\n".join(f"![你的推导]({name})" for name in target_names)
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


def create_student_note(asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    """
    Convert tutor_data/<tutor_idx>/manuscript_1.png (and manuscript_2.png, ...) into note_student.md via the
    manuscript prompt, then insert it into
    img_explainer_data/enhanced.md.
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
    run_agent_job(job)

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

    image_markdown = "\n\n".join(f"![你的推导]({name})" for name in target_names)
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
    return enhanced_md


def fix_latex(markdown_path: str | Path) -> Path:
    path = Path(markdown_path)
    if not path.is_file():
        raise FileNotFoundError(f"Markdown not found: {path}")
    if path.suffix.lower() != ".md":
        raise ValueError(f"fix_latex only supports markdown files: {path}")

    job = AgentJob(
        name="latex_fixer",
        runners=[
            RunnerConfig(
                runner="gemini",
                prompt_path=LATEX_FIXER_GEMINI_PROMPT,
                model=GEMINI_MODEL,
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
    run_agent_job(job)

    if not path.is_file():
        raise FileNotFoundError(f"Latex fixer output not found at {path}")
    return path


def asset_init(
    pdf_path: str | Path,
    asset_name: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
    *,
    rendered_pdf_path: str | Path | None = None,
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

    def _notify(message: str) -> None:
        if progress_callback:
            try:
                progress_callback(message)
            except Exception:  # pragma: no cover - defensive
                pass

    if is_markdown:
        _notify("Preparing markdown asset...")
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
            _notify("Copying rendered PDF...")
            raw_pdf_path = _copy_raw_pdf(rendered_pdf_path, asset_dir)
        else:
            _notify("Rendering markdown to PDF...")
            raw_pdf_path = _render_markdown_to_pdf(output_md, asset_dir / "raw.pdf")
    else:
        _notify("Copying PDF and preparing directories...")
        logger.info("Preparing asset '%s' from %s", resolved_asset_name, source_path)
        raw_pdf_path = _copy_raw_pdf(source_path, asset_dir)
        _clean_directory(references_dir)

        images_dir = asset_dir / "img2md_images"
        _clean_directory(images_dir)

        _notify("Converting PDF pages to images...")
        image_paths = convert_pdf_to_images(source_path, images_dir, dpi=300)
        if not image_paths:
            raise RuntimeError(f"No images rendered from {source_path}")
        logger.info("Converted %d page(s) to %s", len(image_paths), images_dir)

        _notify("Running img2md...")
        img2md_output_dir.mkdir(parents=True, exist_ok=True)
        stale_pattern = re.compile(r"output_(\d{3})\.md$", re.IGNORECASE)
        for path in img2md_output_dir.iterdir():
            if path.is_file() and stale_pattern.match(path.name):
                path.unlink(missing_ok=True)

        image_pattern = re.compile(r".*_(\d{3})\.png$", re.IGNORECASE)
        def _image_sort_key(path: Path) -> tuple[int, int | str]:
            match = image_pattern.match(path.name)
            if match:
                return 0, int(match.group(1))
            return 1, path.name.lower()

        sorted_images = sorted(image_paths, key=_image_sort_key)

        jobs: list[AgentJob] = []
        for idx, image_path in enumerate(sorted_images):
            match = image_pattern.match(image_path.name)
            suffix = match.group(1) if match else f"{idx + 1:03d}"
            output_name = f"output_{suffix}.md"
            jobs.append(
                AgentJob(
                    name=f"img2md_{suffix}",
                    runners=[
                        RunnerConfig(
                            runner="codex",
                            prompt_path=IMG2MD_CODEX_PROMPT,
                            model=CODEX_MODEL,
                            reasoning_effort=CODEX_REASONING_MEDIUM,
                            new_console=True,
                        )
                    ],
                    input_files=[image_path],
                    input_rename={image_path.name: "input.png"},
                    deliver_dir=_relative_to_repo(img2md_output_dir),
                    deliver_rename={"output.md": output_name},
                    clean_markdown=True,
                )
            )

        results = run_agent_jobs(jobs, max_workers=len(jobs))
        delivered = [path for result in results for path in result.delivered]
        if not delivered:
            raise FileNotFoundError("img2md produced no outputs")

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

    _notify("Running extractors...")
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
                        reasoning_effort=CODEX_REASONING_HIGH,
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

    extractor_results = run_agent_jobs(extractor_jobs, max_workers=len(extractor_jobs))
    reference_files: list[Path] = [
        path for result in extractor_results for path in result.delivered
    ]
    if not reference_files:
        raise FileNotFoundError("Extractor produced no reference files")

    logger.info("Moved %d file(s) to %s", len(reference_files), references_dir)
    return AssetInitResult(
        asset_dir=asset_dir,
        references_dir=references_dir,
        raw_pdf_path=raw_pdf_path,
        reference_files=reference_files,
    )
