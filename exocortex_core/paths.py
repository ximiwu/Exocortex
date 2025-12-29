from __future__ import annotations

import builtins
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


__all__ = [
    "DEFAULT_REPO_MARKERS",
    "detect_repo_root",
    "is_compiled_runtime",
    "relative_to_repo",
    "repo_root",
    "runtime_base_dir",
]

