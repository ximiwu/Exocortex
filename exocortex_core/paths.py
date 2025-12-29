from __future__ import annotations

import builtins
import os
import sys
from functools import lru_cache
from pathlib import Path


DEFAULT_REPO_MARKERS: tuple[str, ...] = ("prompts", "assets", "agent_workspace", "README.md")


def is_compiled_runtime() -> bool:
    """
    Best-effort detection for packaged/compiled runtimes (Nuitka/PyInstaller).
    """
    if "__compiled__" in globals():
        return True
    try:
        if hasattr(builtins, "__compiled__"):
            return True
    except Exception:  # pragma: no cover - defensive
        pass
    if getattr(sys, "frozen", False):
        return True
    if hasattr(sys, "_MEIPASS"):
        return True
    return False


def runtime_base_dir() -> Path:
    """
    Return the best-guess base directory for locating bundled data files.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    argv0 = sys.argv[0] if sys.argv else sys.executable
    return Path(argv0).resolve().parent


def detect_repo_root(start: Path, markers: tuple[str, ...] = DEFAULT_REPO_MARKERS) -> Path:
    for candidate in (start, *start.parents):
        if any((candidate / marker).exists() for marker in markers):
            return candidate
    return start


@lru_cache(maxsize=1)
def repo_root() -> Path:
    """
    Locate the project root directory by walking upwards from common runtime anchors.
    """
    candidates: list[Path] = []
    try:
        candidates.append(Path(__file__).resolve().parent)
    except Exception:
        pass
    try:
        candidates.append(runtime_base_dir())
    except Exception:
        pass
    try:
        candidates.append(Path.cwd())
    except Exception:
        pass

    for start in candidates:
        root = detect_repo_root(start)
        if root != start or any((root / marker).exists() for marker in DEFAULT_REPO_MARKERS):
            return root
    return Path.cwd()


def relative_to_repo(path: Path) -> Path:
    try:
        return path.relative_to(repo_root())
    except ValueError:
        return path


def _windows_documents_dir() -> Path | None:
    try:
        import ctypes
        from ctypes import wintypes

        CSIDL_PERSONAL = 5
        SHGFP_TYPE_CURRENT = 0
        buf = ctypes.create_unicode_buffer(wintypes.MAX_PATH)
        result = ctypes.windll.shell32.SHGetFolderPathW(
            None, CSIDL_PERSONAL, None, SHGFP_TYPE_CURRENT, buf
        )
        if result != 0:
            return None
        path = buf.value.strip("\x00").strip()
        return Path(path) if path else None
    except Exception:
        return None


@lru_cache(maxsize=1)
def user_documents_dir() -> Path:
    """
    Best-effort resolution of the user's Documents directory.

    Windows: uses Shell32 SHGetFolderPathW(CSIDL_PERSONAL).
    Fallback: ~/Documents.
    """
    override = os.environ.get("EXOCORTEX_DOCUMENTS_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if os.name == "nt":
        resolved = _windows_documents_dir()
        if resolved is not None:
            return resolved.resolve()

    return (Path.home() / "Documents").resolve()


@lru_cache(maxsize=1)
def exocortex_assets_root() -> Path:
    """
    Default on-disk location for user assets.

    Uses `%USERPROFILE%\\Documents\\ximiwu_app\\Exocortex\\assets` on Windows.
    Can be overridden with EXOCORTEX_ASSETS_ROOT.
    """
    override = os.environ.get("EXOCORTEX_ASSETS_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    return user_documents_dir() / "ximiwu_app" / "Exocortex" / "assets"


__all__ = [
    "DEFAULT_REPO_MARKERS",
    "detect_repo_root",
    "exocortex_assets_root",
    "is_compiled_runtime",
    "relative_to_repo",
    "repo_root",
    "runtime_base_dir",
    "user_documents_dir",
]
