from __future__ import annotations

import threading
from typing import Dict, TYPE_CHECKING

from PySide6 import QtGui

from .pymupdf_compat import fitz

if TYPE_CHECKING:
    import fitz as fitz_typing  # type: ignore[import-not-found]


class PdfRenderer:
    def __init__(self, dpi: int = 150) -> None:
        self._dpi = dpi
        self._doc: fitz_typing.Document | None = None
        self._cache: Dict[int, QtGui.QImage] = {}
        self._lock = threading.Lock()

    def open(self, pdf_path: str) -> None:
        with self._lock:
            self._doc = fitz.open(pdf_path)
            self._cache.clear()

    @property
    def page_count(self) -> int:
        with self._lock:
            if not self._doc:
                return 0
            return self._doc.page_count

    @property
    def dpi(self) -> int:
        return self._dpi

    def set_dpi(self, dpi: int) -> None:
        if dpi <= 0:
            raise ValueError("dpi must be positive.")
        with self._lock:
            if dpi == self._dpi:
                return
            self._dpi = dpi
            self._cache.clear()

    def render_page(self, page_index: int) -> QtGui.QImage:
        with self._lock:
            if page_index in self._cache:
                return self._cache[page_index]
            if not self._doc:
                raise RuntimeError("PDF not loaded.")

            page = self._doc.load_page(page_index)
            scale = self._dpi / 72.0
            pix = page.get_pixmap(
                matrix=fitz.Matrix(scale, scale),
                colorspace=fitz.csRGB,
                alpha=False,
            )
            image = QtGui.QImage(
                pix.samples,
                pix.width,
                pix.height,
                pix.stride,
                QtGui.QImage.Format_RGB888,
            ).copy()
            self._cache[page_index] = image
            return image

    def page_pixel_size(self, page_index: int) -> tuple[int, int]:
        with self._lock:
            if not self._doc:
                raise RuntimeError("PDF not loaded.")
            page = self._doc.load_page(page_index)
            scale = self._dpi / 72.0
            rect = page.rect
            width = int(rect.width * scale)
            height = int(rect.height * scale)
            return width, height

    def close(self) -> None:
        with self._lock:
            if self._doc:
                try:
                    self._doc.close()
                finally:
                    self._doc = None
            self._cache.clear()
