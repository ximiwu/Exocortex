from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from .pdf_images import _import_pymupdf, _require_pillow, render_pdf_to_png_files


_BADGE_POSITIONS = {"top_left", "top_right", "bottom_left", "bottom_right"}


@dataclass(frozen=True, slots=True)
class CompressPreviewResult:
    pdf_path: Path
    image_path: Path
    width: int
    height: int
    size_bytes: int


def _fraction_rect_to_fitz(fitz, fraction_rect: tuple[float, float, float, float]):
    if len(fraction_rect) != 4:
        raise ValueError("invalid clip rectangle")
    x, y, width, height = (float(value) for value in fraction_rect)
    rect = fitz.Rect(x, y, x + width, y + height)
    rect.normalize()
    return rect


def _visual_clip_rect(fitz, page, frac_rect):
    page_rect = page.rect
    clip_rect = fitz.Rect(
        page_rect.x0 + frac_rect.x0 * page_rect.width,
        page_rect.y0 + frac_rect.y0 * page_rect.height,
        page_rect.x0 + frac_rect.x1 * page_rect.width,
        page_rect.y0 + frac_rect.y1 * page_rect.height,
    )
    clip_rect.normalize()
    return clip_rect


def _clamp_rect(fitz, rect, bounds):
    clamped = fitz.Rect(
        max(bounds.x0, rect.x0),
        max(bounds.y0, rect.y0),
        min(bounds.x1, rect.x1),
        min(bounds.y1, rect.y1),
    )
    clamped.normalize()
    return clamped


def _badge_rect(
    fitz,
    left: float,
    top: float,
    cell_width: float,
    cell_height: float,
    *,
    compress_scale: float,
    badge_position: str,
):
    scale = max(0.1, compress_scale)
    margin = max(4.0, 6.0 * scale)
    size = max(24.0, 32.0 * scale)
    if cell_width < size + 2 * margin:
        margin = max(2.0, (cell_width - size) / 2)
    if cell_height < size + 2 * margin:
        margin = max(2.0, (cell_height - size) / 2)

    if badge_position in {"top_right", "bottom_right"}:
        x0 = left + cell_width - size - margin
    else:
        x0 = left + margin

    if badge_position in {"bottom_left", "bottom_right"}:
        y0 = top + cell_height - size - margin
    else:
        y0 = top + margin

    return fitz.Rect(x0, y0, x0 + size, y0 + size)


def compress_pdf_selection(
    source_pdf: str | Path,
    fraction_rect: tuple[float, float, float, float],
    ratio: int,
    output_path: str | Path,
    *,
    compress_scale: float = 1.0,
    draw_badge: bool = True,
    badge_position: str = "top_left",
) -> Path:
    if ratio <= 0:
        raise ValueError("compress ratio must be positive")
    if compress_scale <= 0:
        raise ValueError("compress scale must be positive")

    resolved_badge_position = badge_position if badge_position in _BADGE_POSITIONS else "top_left"
    output = Path(output_path)
    source = Path(source_pdf)
    if not source.is_file():
        raise FileNotFoundError(f"PDF not found: {source}")

    fitz_module = _import_pymupdf()

    base_frac = _fraction_rect_to_fitz(fitz_module, fraction_rect)
    if base_frac.width <= 0 or base_frac.height <= 0:
        raise ValueError("compress block is empty")

    side = int(math.isqrt(ratio))
    if side * side != ratio:
        raise ValueError("compress ratio must be a perfect square")

    source_doc = fitz_module.open(str(source))
    try:
        if source_doc.page_count == 0:
            raise ValueError("PDF has no pages")

        out_doc = fitz_module.open()
        try:
            pages = list(range(source_doc.page_count))
            for start in range(0, len(pages), ratio):
                chunk = pages[start : start + ratio]
                if not chunk:
                    continue

                first_page = source_doc.load_page(chunk[0])
                clip_template = _visual_clip_rect(fitz_module, first_page, base_frac)
                if clip_template.width <= 0 or clip_template.height <= 0:
                    raise ValueError("Computed clip is empty")

                cell_width = clip_template.width
                cell_height = clip_template.height
                cols = side
                rows = max(1, math.ceil(len(chunk) / cols))
                page_width = cell_width * cols * compress_scale
                page_height = cell_height * rows * compress_scale
                dest_page = out_doc.new_page(width=page_width, height=page_height)

                for idx, src_index in enumerate(chunk):
                    src_page = source_doc.load_page(src_index)
                    orig_rotation = int(src_page.rotation or 0) % 360
                    if orig_rotation not in (0, 90, 180, 270):
                        orig_rotation = 0

                    clip_visual = _visual_clip_rect(fitz_module, src_page, base_frac)
                    clip_unrot = clip_visual * src_page.derotation_matrix
                    clip_unrot.normalize()

                    src_page.set_rotation(0)
                    clip_unrot = _clamp_rect(fitz_module, clip_unrot, src_page.rect)
                    if clip_unrot.width <= 0 or clip_unrot.height <= 0:
                        raise ValueError("Computed clip is empty after derotation")

                    rotate_apply = (-orig_rotation) % 360
                    col = idx % cols
                    row = idx // cols
                    left_scaled = cell_width * col * compress_scale
                    top_scaled = cell_height * row * compress_scale
                    cell_width_scaled = cell_width * compress_scale
                    cell_height_scaled = cell_height * compress_scale

                    target_rect = fitz_module.Rect(
                        left_scaled,
                        top_scaled,
                        left_scaled + cell_width_scaled,
                        top_scaled + cell_height_scaled,
                    )
                    dest_page.show_pdf_page(
                        target_rect,
                        source_doc,
                        src_index,
                        clip=clip_unrot,
                        rotate=rotate_apply,
                    )

                    if draw_badge:
                        badge_rect = _badge_rect(
                            fitz_module,
                            left_scaled,
                            top_scaled,
                            cell_width_scaled,
                            cell_height_scaled,
                            compress_scale=compress_scale,
                            badge_position=resolved_badge_position,
                        )
                        center = fitz_module.Point(
                            (badge_rect.x0 + badge_rect.x1) / 2,
                            (badge_rect.y0 + badge_rect.y1) / 2,
                        )
                        radius = badge_rect.width / 2
                        line_width = max(2.0, 3.0 * compress_scale)
                        dest_page.draw_circle(
                            center,
                            radius,
                            color=(1, 0, 0),
                            fill=None,
                            width=line_width,
                        )
                        size_hint = min(badge_rect.width, badge_rect.height)
                        fontsize = max(12.0, min(size_hint * 0.7, 32.0 * compress_scale))
                        dest_page.insert_textbox(
                            badge_rect,
                            str(idx + 1),
                            fontsize=fontsize,
                            color=(1, 0, 0),
                            align=1,
                        )

            output.parent.mkdir(parents=True, exist_ok=True)
            output.unlink(missing_ok=True)
            out_doc.save(output)
        finally:
            out_doc.close()
    finally:
        source_doc.close()

    return output


def render_compress_preview(
    source_pdf: str | Path,
    fraction_rect: tuple[float, float, float, float],
    ratio: int,
    output_dir: str | Path,
    *,
    compress_scale: float = 1.0,
    draw_badge: bool = True,
    badge_position: str = "top_left",
    dpi: int = 300,
) -> CompressPreviewResult:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    preview_pdf = output_root / "compressed_preview.pdf"
    pdf_path = compress_pdf_selection(
        source_pdf,
        fraction_rect,
        ratio,
        preview_pdf,
        compress_scale=compress_scale,
        draw_badge=draw_badge,
        badge_position=badge_position,
    )

    images_dir = output_root / "images"
    image_paths = render_pdf_to_png_files(pdf_path, images_dir, dpi=dpi, prefix="preview")
    if not image_paths:
        raise RuntimeError("Preview conversion produced no images.")

    image_path = image_paths[0]
    Image = _require_pillow()
    with Image.open(image_path) as image:
        width, height = image.size

    return CompressPreviewResult(
        pdf_path=pdf_path,
        image_path=image_path,
        width=width,
        height=height,
        size_bytes=image_path.stat().st_size,
    )


__all__ = [
    "CompressPreviewResult",
    "compress_pdf_selection",
    "render_compress_preview",
]
