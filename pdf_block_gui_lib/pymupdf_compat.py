from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import fitz  # type: ignore[import-not-found]


def import_pymupdf():
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


fitz = import_pymupdf()

