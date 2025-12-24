from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List

from PySide6 import QtGui, QtPrintSupport

from codex.extractor import main as extractor_main
from codex.img2md import main as img2md_main
from codex.img_explainer import main as img_explainer_main
from codex.pdf2img import convert_pdf_to_images
from codex.integrator import main as integrator_main
from codex.enhancer import main as enhancer_main
from codex.tutor import main as tutor_main


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
    for candidate in (module_dir, *module_dir.parents):
        if (candidate / "codex").is_dir():
            return candidate
    return module_dir


REPO_ROOT = _detect_repo_root(Path(__file__).resolve().parent)
CODEX_DIR = REPO_ROOT / "codex"
PDF2IMG_OUTPUT_DIR = CODEX_DIR / "img2md" / "input"
IMG2MD_OUTPUT_DIR = CODEX_DIR / "img2md" / "output"
IMG_EXPLAINER_DIR = CODEX_DIR / "img_explainer"
IMG_EXPLAINER_INPUT_DIR = IMG_EXPLAINER_DIR / "input"
IMG_EXPLAINER_OUTPUT_DIR = IMG_EXPLAINER_DIR / "output"
IMG_EXPLAINER_REFERENCES_DIR = IMG_EXPLAINER_DIR / "references"
EXTRACTOR_BASE_DIR = CODEX_DIR / "extractor"
EXTRACTOR_AGENTS: tuple[str, ...] = ("background", "concept", "formula")
EXTRACTOR_INPUT_DIRS = {
    name: EXTRACTOR_BASE_DIR / name / "input" for name in EXTRACTOR_AGENTS
}
EXTRACTOR_OUTPUT_DIRS = {
    name: EXTRACTOR_BASE_DIR / name / "output" for name in EXTRACTOR_AGENTS
}
TUTOR_DIR = CODEX_DIR / "tutor"
TUTOR_INPUT_DIR = TUTOR_DIR / "input"
TUTOR_OUTPUT_DIR = TUTOR_DIR / "output"
TUTOR_REFERENCES_DIR = TUTOR_DIR / "references"
INTEGRATOR_DIR = CODEX_DIR / "integrator"
INTEGRATOR_INPUT_DIR = INTEGRATOR_DIR / "input"
INTEGRATOR_OUTPUT_DIR = INTEGRATOR_DIR / "output"
INTEGRATOR_REFERENCES_DIR = INTEGRATOR_DIR / "references"
ENHANCER_DIR = CODEX_DIR / "enhancer"
ENHANCER_INPUT_DIR = ENHANCER_DIR / "input"
ENHANCER_OUTPUT_DIR = ENHANCER_DIR / "output"
ASSETS_ROOT = REPO_ROOT / "assets"
REFERENCE_RENDER_DPI = 130  # Keep in sync with pdf_block_gui_lib.main_window.DEFAULT_RENDER_DPI


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
        
def _clean_markdown_file(file_path: Path):
    content = file_path.read_text(encoding="utf-8-sig")

    # === 辅助函数：修复 LaTeX 语法 (去转义) ===
    def _fix_latex_syntax(text):
        # 将双反斜杠 \\ 替换为单反斜杠 \
        # 注意：在 Python 字符串中，\\\\ 代表字面量的两个反斜杠
        return text.replace('\\\\', '\\')

    # 1. 统一转换 \[ \] 为 $$ $$
    content = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', content, flags=re.DOTALL)

    # 2. 统一转换 \( \) 为 $ $
    # 先把 \( ... \) 这种格式转成 $ ... $，后续统一在步骤3处理内容
    content = re.sub(r'\\\((.*?)\\\)', r'$\1$', content, flags=re.DOTALL)

    # 3. 处理行内公式 $...$ (修复 \\epsilon 为 \epsilon，并去除多余空格)
    # 正则解释：(?<!\$) 表示前面不能是 $，(?!\$) 表示后面不能是 $，确保只匹配单个 $ 包裹的内容
    def clean_inline(match):
        inner = match.group(1)
        # 修复转义字符
        inner = _fix_latex_syntax(inner)
        # 清洗特殊空格
        inner = inner.replace('\u00A0', ' ').replace('\u3000', ' ').strip()
        return f"${inner}$"
    
    content = re.sub(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', clean_inline, content, flags=re.DOTALL)

    # 4. 处理块级公式 $$...$$ (修复语法 + 重新排版)
    pattern = re.compile(r'\$\$(.*?)\$\$', re.DOTALL)
    def reform_block(match):
        math_content = match.group(1)
        
        # 修复转义字符 (例如 \\epsilon -> \epsilon)
        math_content = _fix_latex_syntax(math_content)
        
        lines = math_content.splitlines()
        clean_lines = []
        for line in lines:
            stripped = line.strip().replace("\u00A0", " ").replace("\u3000", " ").replace("\u200b", " ").replace("\ufeff", " ")
            if stripped:
                clean_lines.append(stripped)
        
        cleaned_math_body = "\n".join(clean_lines)
        return f"\n\n$$\n{cleaned_math_body}\n$$\n\n"
    
    new_content = pattern.sub(reform_block, content)

    # ================= [缩进清洗功能] =================
    lines = new_content.splitlines()
    processed_lines = []
    in_code_block = False
    strip_chars = ' \t\u00A0\u3000'

    for line in lines:
        # 检测代码块标记
        if re.match(r'^\s*```', line):
            in_code_block = not in_code_block
            processed_lines.append(line.lstrip(strip_chars))
            continue
        
        if in_code_block:
            processed_lines.append(line)
        else:
            # 非代码块，强制去除左侧缩进，解决公式不渲染问题
            processed_lines.append(line.lstrip(strip_chars))
            
    new_content = "\n".join(processed_lines)
    # =================================================

    # 5. 规范化换行符
    new_content = re.sub(r'\n{3,}', '\n\n', new_content)

    with open(file_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(new_content)


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
    """Ensure intermediate working directories start empty."""
    _clean_directory(PDF2IMG_OUTPUT_DIR)
    _clean_directory(IMG2MD_OUTPUT_DIR)
    for directory in EXTRACTOR_INPUT_DIRS.values():
        _clean_directory(directory)
    for directory in EXTRACTOR_OUTPUT_DIRS.values():
        _clean_directory(directory)


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


def _populate_agent_references(
    asset_name: str,
    destination_dir: Path,
    *,
    reference_filenames: Iterable[str] | None = None,
    include_entire_content: bool = False,
    entire_content_filename: str = "entire_content.md",
) -> list[Path]:
    """
    Populate an agent's /references directory from an asset.

    By default this copies all files from `assets/<asset_name>/references`.
    When `include_entire_content` is True, also copy the asset's
    `img2md_output/output.md` as `entire_content.md`.
    """
    _clean_directory(destination_dir)

    asset_reference_dir = ASSETS_ROOT / asset_name / "references"
    if not asset_reference_dir.is_dir():
        raise FileNotFoundError(
            f"References directory not found for asset '{asset_name}': {asset_reference_dir}"
        )

    copied: list[Path] = []
    if reference_filenames is None:
        for path in asset_reference_dir.iterdir():
            if not path.is_file():
                continue
            destination = destination_dir / path.name
            shutil.copy2(path, destination)
            copied.append(destination)
    else:
        for filename in reference_filenames:
            source = asset_reference_dir / filename
            if not source.is_file():
                raise FileNotFoundError(
                    f"Missing reference file for asset '{asset_name}': {source}"
                )
            destination = destination_dir / source.name
            shutil.copy2(source, destination)
            copied.append(destination)

    if not copied:
        raise FileNotFoundError(f"No reference files found in {asset_reference_dir}")

    if include_entire_content:
        entire_content_source = _resolve_asset_img2md_output_markdown(asset_name)
        entire_content_destination = destination_dir / entire_content_filename
        shutil.copy2(entire_content_source, entire_content_destination)
        _clean_markdown_file(entire_content_destination)
        copied.append(entire_content_destination)

    return copied


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
        _clean_directory(ENHANCER_INPUT_DIR)
        _clean_directory(ENHANCER_OUTPUT_DIR)
        enhancer_base = ENHANCER_OUTPUT_DIR / "main.md"
        enhancer_supplement = ENHANCER_INPUT_DIR / "supplement.md"
        shutil.copy2(initial_output, enhancer_base)
        shutil.copy2(initial_gemini_output, enhancer_supplement)

        exit_code = enhancer_main()
        if exit_code != 0:
            raise RuntimeError(f"enhancer failed with exit code {exit_code}")

        enhancer_output = ENHANCER_OUTPUT_DIR / "main.md"
        if not enhancer_output.is_file():
            raise FileNotFoundError(f"enhancer output not found: {enhancer_output}")

        target_dir.mkdir(parents=True, exist_ok=True)
        if enhanced_md.exists():
            enhanced_md.unlink()
        shutil.move(str(enhancer_output), str(enhanced_md))
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
    _clean_directory(IMG_EXPLAINER_OUTPUT_DIR)
    _clean_directory(IMG_EXPLAINER_INPUT_DIR)
    initial_dir.mkdir(parents=True, exist_ok=True)
    _populate_agent_references(
        asset_name,
        IMG_EXPLAINER_REFERENCES_DIR,
        include_entire_content=True,
    )

    pdf_path = get_asset_pdf_path(asset_name)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found for asset '{asset_name}': {pdf_path}")

    blocks = _select_blocks_for_group(asset_name, group_idx)
    images = _render_blocks_to_images(pdf_path, blocks, dpi=300)
    merged_image = _stack_images_vertically(images)

    thesis_image_path = IMG_EXPLAINER_INPUT_DIR / "thesis.png"
    thesis_image_path.parent.mkdir(parents=True, exist_ok=True)
    if not merged_image.save(str(thesis_image_path)):
        raise RuntimeError(f"Failed to save rendered image to {thesis_image_path}")

    def _copy_gemini_output(path: Path) -> None:
        try:
            shutil.copy2(path, initial_gemini_output)
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

    exit_code = img_explainer_main(on_gemini_ready=_copy_gemini_output)
    if exit_code != 0:
        raise RuntimeError(f"img_explainer failed with exit code {exit_code}")

    output_md = IMG_EXPLAINER_OUTPUT_DIR / "output.md"
    if not output_md.is_file():
        raise FileNotFoundError(f"img_explainer output not found: {output_md}")

    shutil.copy2(output_md, initial_output)
    _clean_markdown_file(initial_output)
    gemini_output = IMG_EXPLAINER_OUTPUT_DIR / "output_gemini.md"
    if not gemini_output.is_file():
        raise FileNotFoundError(f"img_explainer Gemini output not found: {gemini_output}")

    shutil.copy2(gemini_output, initial_gemini_output)
    _clean_markdown_file(initial_gemini_output)
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
    1) Clear codex/tutor input & output.
    2) Copy focus.md to codex/tutor/input/input.md.
    3) If ask_history exists, append it to codex/tutor/input/input.md (after a "# 历史对话：" line).
    4) Invoke tutor main(question).
    5) Move output.md into ask_history as the next sequential markdown (1, 2, ...), clean it, and prefix with Q/A headings.
    """
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("Question is required.")

    if not TUTOR_DIR.is_dir():
        raise FileNotFoundError(f"tutor directory not found: {TUTOR_DIR}")

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

    _clean_directory(TUTOR_INPUT_DIR)
    _clean_directory(TUTOR_OUTPUT_DIR)
    _populate_agent_references(
        asset_name,
        TUTOR_REFERENCES_DIR,
        include_entire_content=True,
    )
    tutor_input_path = TUTOR_INPUT_DIR / "input.md"
    shutil.copy2(focus_md, tutor_input_path)

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

    exit_code = tutor_main(normalized_question)
    if exit_code != 0:
        raise RuntimeError(f"tutor failed with exit code {exit_code}")

    tutor_output_path = TUTOR_OUTPUT_DIR / "output.md"
    if not tutor_output_path.is_file():
        raise FileNotFoundError(f"tutor output not found at {tutor_output_path}")

    ask_history_dir.mkdir(parents=True, exist_ok=True)
    next_idx = _next_markdown_index(ask_history_dir)
    history_output = ask_history_dir / f"{next_idx}.md"
    moved_output = Path(shutil.move(str(tutor_output_path), history_output))
    _clean_markdown_file(moved_output)

    answer = moved_output.read_text(encoding="utf-8")
    header = f"## 提问：\n\n{normalized_question}\n\n## 回答：\n\n"
    moved_output.write_text(header + answer.lstrip(), encoding="utf-8", newline="\n")
    return moved_output


def integrate(asset_name: str, group_idx: int, tutor_idx: int) -> Path:
    """
    Run the integrator agent for a tutor session, save a note, and insert it back into enhanced.md.

    Steps:
    1) Clear codex/integrator input & output.
    2) Concatenate focus.md + ask_history into codex/integrator/input/input.md.
    3) Invoke integrator main.
    4) Clean markdown output and move it to tutor_data/<tutor_idx>/note.md.
    5) Wrap note.md in a <details class="note"> block.
    6) Insert the wrapped note block into img_explainer_data/enhanced.md at the end of the focus region.
    """
    if not INTEGRATOR_DIR.is_dir():
        raise FileNotFoundError(f"integrator directory not found: {INTEGRATOR_DIR}")

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

    _clean_directory(INTEGRATOR_INPUT_DIR)
    _clean_directory(INTEGRATOR_OUTPUT_DIR)
    _populate_agent_references(
        asset_name,
        INTEGRATOR_REFERENCES_DIR,
        reference_filenames=("formula.md", "concept.md"),
    )
    integrator_input_path = INTEGRATOR_INPUT_DIR / "input.md"
    shutil.copy2(focus_md, integrator_input_path)

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

    exit_code = integrator_main("finish_ask")
    if exit_code != 0:
        raise RuntimeError(f"integrator failed with exit code {exit_code}")

    integrator_output_path = INTEGRATOR_OUTPUT_DIR / "output.md"
    if not integrator_output_path.is_file():
        raise FileNotFoundError(f"integrator output not found at {integrator_output_path}")

    _clean_markdown_file(integrator_output_path)

    note_path = tutor_session_dir / "note.md"
    existing_note_wrapped = ""
    if note_path.is_file():
        try:
            existing_note_wrapped = note_path.read_text(encoding="utf-8").lstrip("\ufeff")
        except Exception:  # pragma: no cover - defensive
            existing_note_wrapped = ""
    note_path.unlink(missing_ok=True)
    moved_output = Path(shutil.move(str(integrator_output_path), note_path))

    note_content = moved_output.read_text(encoding="utf-8").lstrip("\ufeff")
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
    moved_output.write_text(note_wrapped, encoding="utf-8", newline="\n")

    img_explainer_dir = group_dir / "img_explainer_data"
    enhanced_md = img_explainer_dir / "enhanced.md"
    if not enhanced_md.is_file():
        raise FileNotFoundError(f"enhanced.md not found at {enhanced_md}")

    enhanced_content = enhanced_md.read_text(encoding="utf-8")
    if existing_note_wrapped:
        if existing_note_wrapped in enhanced_content:
            enhanced_content = enhanced_content.replace(existing_note_wrapped, "", 1)
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


def asset_init(
    pdf_path: str | Path,
    asset_name: str | None = None,
    progress_callback: Callable[[str], None] | None = None,
    *,
    rendered_pdf_path: str | Path | None = None,
) -> AssetInitResult:
    # return
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
        _prepare_working_directories()

        output_md = IMG2MD_OUTPUT_DIR / "output.md"
        output_md.write_text(source_path.read_text(encoding="utf-8-sig"), encoding="utf-8", newline="\n")
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
        _prepare_working_directories()

        _notify("Converting PDF pages to images...")
        image_paths = convert_pdf_to_images(source_path, PDF2IMG_OUTPUT_DIR, dpi=300)
        logger.info("Converted %d page(s) to %s", len(image_paths), PDF2IMG_OUTPUT_DIR)

        _notify("Running img2md...")
        img2md_exit_code = img2md_main()
        if img2md_exit_code != 0:
            raise RuntimeError(f"img2md failed with exit code {img2md_exit_code}")

        # Normalize markdown produced by img2md before it feeds other steps.
        for path in IMG2MD_OUTPUT_DIR.iterdir():
            if path.is_file():
                _clean_markdown_file(path)

    _notify("Copying img2md output to asset directory...")
    asset_img2md_dir = asset_dir / "img2md_output"
    _clean_directory(asset_img2md_dir)
    copied_img2md_files: list[Path] = []
    for path in IMG2MD_OUTPUT_DIR.iterdir():
        if not path.is_file():
            continue
        destination = asset_img2md_dir / path.name
        shutil.copy2(path, destination)
        copied_img2md_files.append(destination)
        _clean_markdown_file(destination)
    if not copied_img2md_files:
        raise FileNotFoundError(f"No img2md outputs found in {IMG2MD_OUTPUT_DIR}")

    _notify("Copying markdown to extractor inputs...")
    copy_all_files(
        IMG2MD_OUTPUT_DIR,
        EXTRACTOR_INPUT_DIRS.values(),
        rename={"output.md": "input.md"},
    )

    _notify("Running extractors...")
    extractor_exit_code = extractor_main()
    if extractor_exit_code != 0:
        raise RuntimeError(f"extractor failed with exit code {extractor_exit_code}")

    _notify("Collecting extractor outputs...")
    reference_files: list[Path] = []
    for agent in EXTRACTOR_AGENTS:
        reference_files.extend(
            move_all_files(EXTRACTOR_OUTPUT_DIRS[agent], references_dir)
        )
    for ref in reference_files:
        _clean_markdown_file(ref)

    _notify("Cleaning working directories...")
    _clean_directory(PDF2IMG_OUTPUT_DIR)
    _clean_directory(IMG2MD_OUTPUT_DIR)
    for directory in EXTRACTOR_INPUT_DIRS.values():
        _clean_directory(directory)
    for directory in EXTRACTOR_OUTPUT_DIRS.values():
        _clean_directory(directory)

    logger.info(
        "Moved %d file(s) to %s", len(reference_files), references_dir
    )
    return AssetInitResult(
        asset_dir=asset_dir,
        references_dir=references_dir,
        raw_pdf_path=raw_pdf_path,
        reference_files=reference_files,
    )
