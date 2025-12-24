from __future__ import annotations

from pathlib import Path

import pypdfium2 as pdfium


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
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    base_name = prefix or pdf_path.stem
    scale = dpi / 72  # PDF points are 1/72 in; scale maps to target DPI.
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
