from __future__ import annotations

from pathlib import Path

from .constants import REFERENCE_RENDER_DPI
from .models import BlockRecord

try:
    from PySide6 import QtGui, QtPrintSupport
except ImportError:  # pragma: no cover - optional dependency guard
    QtGui = None  # type: ignore[assignment]
    QtPrintSupport = None  # type: ignore[assignment]

try:
    import markdown
except ImportError:  # pragma: no cover - optional dependency guard
    markdown = None

try:
    import pymdownx.arithmatex  # type: ignore  # noqa: F401

    _ARITHMETEX_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    _ARITHMETEX_AVAILABLE = False


def render_markdown_to_pdf(markdown_path: Path, output_pdf: Path) -> Path:
    if QtGui is None or QtPrintSupport is None:  # pragma: no cover - optional dependency guard
        raise RuntimeError("Missing PySide6 for rendering markdown to PDF.")
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


def render_blocks_to_images(
    pdf_path: Path,
    blocks: list[BlockRecord],
    dpi: int = 300,
    reference_dpi: int = REFERENCE_RENDER_DPI,
) -> list["QtGui.QImage"]:
    """
    Render each block rect to a QImage cropped from its page(s).

    Block coordinates are stored in reference_dpi space (GUI reference render DPI) and must
    be scaled to the target renderer DPI before cropping.
    """
    if QtGui is None:  # pragma: no cover - optional dependency guard
        raise RuntimeError("Missing PySide6 for rendering block images.")
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
                raise ValueError(
                    f"Invalid block dimensions for block {block.block_id} on page {block.page_index}"
                )
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
                images.append(stack_images_vertically(slices))
    finally:
        renderer.close()
    return images


def stack_images_vertically(images: list["QtGui.QImage"]) -> "QtGui.QImage":
    """Stack images vertically into one combined QImage."""
    if QtGui is None:  # pragma: no cover - optional dependency guard
        raise RuntimeError("Missing PySide6 for stacking images.")
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

