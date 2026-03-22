from __future__ import annotations

import io
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

from .contracts import BlockRecord

if TYPE_CHECKING:
    from PIL import Image


def _import_pymupdf():
    try:
        import pymupdf as fitz  # type: ignore[import-not-found]

        return fitz
    except Exception:
        try:
            import fitz  # type: ignore[import-not-found]

            if not hasattr(fitz, "open") or not hasattr(fitz, "Document"):
                raise ImportError("fitz is not PyMuPDF")
            return fitz
        except Exception as exc:  # pragma: no cover - import guard
            raise RuntimeError(
                "PyMuPDF is not available. Run: pip uninstall fitz; pip install PyMuPDF"
            ) from exc


def _require_pillow():
    try:
        from PIL import Image
    except Exception as exc:  # pragma: no cover - import guard
        raise RuntimeError("Pillow is required for image composition features.") from exc
    return Image


def _page_scale(dpi: int) -> float:
    if dpi <= 0:
        raise ValueError("dpi must be positive.")
    return dpi / 72.0


def _open_document(pdf_path: str | Path):
    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")
    fitz = _import_pymupdf()
    return fitz.open(str(path))


def _page_pixmap(page, *, dpi: int, clip=None):
    fitz = _import_pymupdf()
    scale = _page_scale(dpi)
    return page.get_pixmap(
        matrix=fitz.Matrix(scale, scale),
        colorspace=fitz.csRGB,
        alpha=False,
        clip=clip,
    )


def _pixmap_to_png_bytes(pixmap) -> bytes:
    return pixmap.tobytes("png")


def _pixmap_to_pillow_image(pixmap) -> "Image.Image":
    Image = _require_pillow()
    with Image.open(io.BytesIO(_pixmap_to_png_bytes(pixmap))) as image:
        return image.copy()


def render_page_to_png_bytes(pdf_path: str | Path, page_index: int, *, dpi: int = 150) -> bytes:
    document = _open_document(pdf_path)
    try:
        page = document.load_page(page_index)
        pixmap = _page_pixmap(page, dpi=dpi)
        return _pixmap_to_png_bytes(pixmap)
    finally:
        document.close()


def render_page_to_image(pdf_path: str | Path, page_index: int, *, dpi: int = 150) -> "Image.Image":
    document = _open_document(pdf_path)
    try:
        page = document.load_page(page_index)
        pixmap = _page_pixmap(page, dpi=dpi)
        return _pixmap_to_pillow_image(pixmap)
    finally:
        document.close()


def page_pixel_size(pdf_path: str | Path, page_index: int, *, dpi: int = 150) -> tuple[int, int]:
    document = _open_document(pdf_path)
    try:
        page = document.load_page(page_index)
        rect = page.rect
        scale = _page_scale(dpi)
        return int(rect.width * scale), int(rect.height * scale)
    finally:
        document.close()


def get_page_pixel_sizes(pdf_path: str | Path, *, dpi: int = 150) -> list[tuple[int, int]]:
    document = _open_document(pdf_path)
    try:
        scale = _page_scale(dpi)
        return [
            (int(page.rect.width * scale), int(page.rect.height * scale))
            for page in document
        ]
    finally:
        document.close()


def render_pdf_to_png_files(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    dpi: int = 300,
    prefix: str | None = None,
) -> list[Path]:
    document = _open_document(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    resolved_prefix = prefix or Path(pdf_path).stem

    image_paths: list[Path] = []
    try:
        for page_index in range(document.page_count):
            page = document.load_page(page_index)
            pixmap = _page_pixmap(page, dpi=dpi)
            image_path = output_dir / f"{resolved_prefix}_page_{page_index + 1:03d}.png"
            image_path.write_bytes(_pixmap_to_png_bytes(pixmap))
            image_paths.append(image_path)
    finally:
        document.close()
    return image_paths


def crop_blocks_to_images(
    pdf_path: str | Path,
    blocks: Iterable[BlockRecord],
    *,
    dpi: int = 300,
    reference_dpi: int = 130,
) -> list["Image.Image"]:
    fitz = _import_pymupdf()
    if reference_dpi <= 0:
        raise ValueError("reference_dpi must be positive.")

    document = _open_document(pdf_path)
    try:
        page_count = document.page_count
        points_per_ref_unit = 72.0 / reference_dpi
        page_widths_ref: list[float] = []
        page_heights_ref: list[float] = []
        page_offsets_ref: list[float] = [0.0]

        for page_index in range(page_count):
            page = document.load_page(page_index)
            width_ref = float(page.rect.width) * reference_dpi / 72.0
            height_ref = float(page.rect.height) * reference_dpi / 72.0
            page_widths_ref.append(width_ref)
            page_heights_ref.append(height_ref)
            page_offsets_ref.append(page_offsets_ref[-1] + height_ref)

        images: list["Image.Image"] = []
        for block in blocks:
            if block.page_index < 0 or block.page_index >= page_count:
                raise ValueError(f"Invalid page index for block {block.block_id}: {block.page_index}")

            block_width_ref = float(block.rect.width)
            block_height_ref = float(block.rect.height)
            if block_width_ref <= 0 or block_height_ref <= 0:
                raise ValueError(
                    f"Invalid block dimensions for block {block.block_id} on page {block.page_index}"
                )

            block_x_ref = float(block.rect.x)
            block_y_ref = float(block.rect.y)
            base_page_width_ref = page_widths_ref[block.page_index]
            base_page_offset_ref = page_offsets_ref[block.page_index]
            block_center_offset = (block_x_ref + block_width_ref / 2.0) - base_page_width_ref / 2.0
            block_global_y0 = base_page_offset_ref + block_y_ref
            block_global_y1 = block_global_y0 + block_height_ref

            slices: list["Image.Image"] = []
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
                center_x_ref = page_width_ref / 2.0 + block_center_offset
                x0_ref = center_x_ref - block_width_ref / 2.0

                clip = fitz.Rect(
                    x0_ref * points_per_ref_unit,
                    local_y0_ref * points_per_ref_unit,
                    (x0_ref + block_width_ref) * points_per_ref_unit,
                    (local_y0_ref + local_height_ref) * points_per_ref_unit,
                )
                page = document.load_page(page_index)
                clip = clip & page.rect
                if clip.width <= 0 or clip.height <= 0:
                    continue

                pixmap = _page_pixmap(page, dpi=dpi, clip=clip)
                slices.append(_pixmap_to_pillow_image(pixmap))

            if not slices:
                raise ValueError(f"Block {block.block_id} does not intersect any page.")
            if len(slices) == 1:
                images.append(slices[0])
            else:
                images.append(stack_images_vertically(slices))

        return images
    finally:
        document.close()


def stack_images_vertically(
    images: Iterable["Image.Image"],
    *,
    background: str = "white",
) -> "Image.Image":
    Image = _require_pillow()
    image_list = list(images)
    if not image_list:
        raise ValueError("No images provided to stack.")

    normalized = [image.convert("RGB") for image in image_list]
    max_width = max(image.width for image in normalized)
    total_height = sum(image.height for image in normalized)
    canvas = Image.new("RGB", (max_width, total_height), color=background)

    y_offset = 0
    for image in normalized:
        canvas.paste(image, (0, y_offset))
        y_offset += image.height
    return canvas


__all__ = [
    "crop_blocks_to_images",
    "get_page_pixel_sizes",
    "page_pixel_size",
    "render_page_to_image",
    "render_page_to_png_bytes",
    "render_pdf_to_png_files",
    "stack_images_vertically",
]
