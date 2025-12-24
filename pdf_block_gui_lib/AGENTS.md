# Agent instructions (scope: this directory and subdirectories)

## Scope and layout
- **This AGENTS.md applies to:** `pdf_block_gui_lib/` and below.
- **Key files:**
  - `pdf_block_gui_lib/app.py`: Qt application bootstrap + `main()`.
  - `pdf_block_gui_lib/main_window.py`: main UI/state machine (open PDF, select blocks, export).
  - `pdf_block_gui_lib/renderer.py`: PDF -> `QImage` renderer (PyMuPDF/fitz).
  - `pdf_block_gui_lib/widgets.py`: `PdfPageView` interaction (rubber-band selection, clicks).
  - `pdf_block_gui_lib/models.py`: small data models (`Block`, etc.).

## Commands (how to run)
- **Install deps:** `pip install PySide6 PyMuPDF`
- **Run GUI (from repo root):** `python pdf_block_gui.py`

## Feature map
| Feature | Owner | Key paths | Entrypoints | Tests | Docs |
|--------|-------|-----------|-------------|-------|------|
| Open PDF and render pages | gui | `renderer.py`, `main_window.py` | `MainWindow._open_pdf()` | (none) | (none) |
| Rubber-band selection | gui | `widgets.py` | `PdfPageView.selection_finished` | (none) | (none) |
| Block toggle/delete | gui | `widgets.py`, `main_window.py` | `block_clicked`, `block_right_clicked` | (none) | (none) |
| Export selected/merged blocks | gui | `main_window.py` | `_export_selected_block()`, `_export_merged_blocks()` | (none) | (none) |

## Conventions
- **Qt threading rule:** only touch widgets/scene in the main thread. For PDF processing/LLM calls, use a worker and emit signals back.
- **Coordinate systems:** be explicit about scene vs viewport coordinates when adding new interactions.
- **Images:** when creating `QImage` from external buffers (PyMuPDF pixmaps), copy if lifetime is uncertain (as done in `renderer.py`).
- **Performance:** avoid re-rendering pages unnecessarily; prefer caching and incremental scene updates.

## Common pitfalls
- High DPI rendering can be memory-heavy; keep `PdfRenderer(dpi=...)` changes intentional and consider cache invalidation.
