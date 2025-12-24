from __future__ import annotations

import sys
from pathlib import Path


def is_compiled_runtime() -> bool:
    """
    Best-effort detection for packaged/compiled runtimes (Nuitka/PyInstaller).
    """
    if "__compiled__" in globals():
        return True
    try:
        import builtins  # noqa: PLC0415

        if hasattr(builtins, "__compiled__"):
            return True
    except Exception:  # pragma: no cover - defensive
        pass
    if getattr(sys, "frozen", False):
        return True
    if hasattr(sys, "_MEIPASS"):
        return True
    return False


def _packaged_base_dir() -> Path:
    """
    Return the unpacked base directory for packaged builds.

    - PyInstaller: sys._MEIPASS points to the extraction dir.
    - Nuitka standalone: sys.argv[0] is the executable path.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()
    argv0 = sys.argv[0] if sys.argv else sys.executable
    return Path(argv0).resolve().parent


def lib_dir() -> Path:
    """
    Return the on-disk directory that contains the pdf_block_gui_lib package data.

    In source checkouts this is the package folder; in packaged builds this is
    typically either `<exe_dir>/pdf_block_gui_lib` or `<exe_dir>`.
    """
    if is_compiled_runtime():
        base_dir = _packaged_base_dir()
        candidate = base_dir / "pdf_block_gui_lib"
        return candidate if candidate.is_dir() else base_dir
    return Path(__file__).resolve().parent


def static_dir() -> Path:
    return lib_dir() / "static"


def static_path(*parts: str) -> Path:
    return static_dir().joinpath(*parts)


__all__ = [
    "is_compiled_runtime",
    "lib_dir",
    "static_dir",
    "static_path",
]

