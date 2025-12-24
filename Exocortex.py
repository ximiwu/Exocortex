from __future__ import annotations

import importlib.util
import os
import re
import sys
from pathlib import Path


def _is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False) or "__compiled__" in globals())


def _set_env_path_if_missing_or_invalid(key: str, value: str) -> None:
    current = os.environ.get(key)
    if not current:
        os.environ[key] = value
        return

    current_first = current.split(os.pathsep, 1)[0]
    if current_first and os.path.isdir(current_first):
        return

    os.environ[key] = value


def _configure_qt_runtime_for_frozen_app() -> None:
    if not _is_frozen_app():
        return

    base_dir = os.path.dirname(os.path.abspath(sys.executable))
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(base_dir)
        except OSError:
            pass

    os.environ["PATH"] = base_dir + os.pathsep + os.environ.get("PATH", "")

    candidates = [
        os.path.join(base_dir, "PySide6", "qt-plugins"),
        os.path.join(base_dir, "PySide6", "plugins"),
    ]
    plugin_path = next((p for p in candidates if os.path.isdir(p)), "")
    if not plugin_path:
        return

    _set_env_path_if_missing_or_invalid("QT_PLUGIN_PATH", plugin_path)
    _set_env_path_if_missing_or_invalid(
        "QT_QPA_PLATFORM_PLUGIN_PATH", os.path.join(plugin_path, "platforms")
    )


def _configure_qt_runtime_for_dev_python() -> None:
    if _is_frozen_app():
        return

    spec = importlib.util.find_spec("PySide6")
    if not spec or not spec.submodule_search_locations:
        return

    pyside6_dir = Path(next(iter(spec.submodule_search_locations))).resolve()

    dll_dirs: list[Path] = [pyside6_dir, pyside6_dir / "Qt" / "bin"]
    if hasattr(os, "add_dll_directory"):
        for dll_dir in dll_dirs:
            if not dll_dir.is_dir():
                continue
            try:
                os.add_dll_directory(str(dll_dir))
            except OSError:
                pass

    os.environ["PATH"] = str(pyside6_dir) + os.pathsep + os.environ.get("PATH", "")

    plugin_candidates = [
        pyside6_dir / "qt-plugins",
        pyside6_dir / "plugins",
        pyside6_dir / "Qt" / "plugins",
    ]
    plugin_path = next((p for p in plugin_candidates if p.is_dir()), None)
    if plugin_path is None:
        return

    _set_env_path_if_missing_or_invalid("QT_PLUGIN_PATH", str(plugin_path))
    _set_env_path_if_missing_or_invalid(
        "QT_QPA_PLATFORM_PLUGIN_PATH", str(plugin_path / "platforms")
    )


def _parse_path_list(value: str) -> list[Path]:
    parts = [p.strip().strip('"') for p in re.split(r"[;\n,]+", value) if p.strip()]
    return [Path(p) for p in parts]


def _venv_python_exe(venv_dir: Path) -> Path | None:
    if sys.platform.startswith("win"):
        scripts = venv_dir / "Scripts"
        if not scripts.is_dir():
            return None

        prefer_gui = Path(sys.executable).name.lower().endswith("pythonw.exe")
        preferred = scripts / ("pythonw.exe" if prefer_gui else "python.exe")
        fallback = scripts / ("python.exe" if prefer_gui else "pythonw.exe")
        if preferred.is_file():
            return preferred
        if fallback.is_file():
            return fallback
        return None

    candidate = venv_dir / "bin" / "python"
    return candidate if candidate.is_file() else None


def _venv_has_required_qt(venv_dir: Path) -> bool:
    if sys.platform.startswith("win"):
        site = venv_dir / "Lib" / "site-packages" / "PySide6"
        if not (site / "__init__.py").is_file():
            return False
        return any(site.glob("QtWidgets.*")) and any(site.glob("QtWebEngineWidgets.*"))

    lib_dir = venv_dir / "lib"
    if not lib_dir.is_dir():
        return False

    for init_file in lib_dir.glob("python*/site-packages/PySide6/__init__.py"):
        if not init_file.is_file():
            continue
        site = init_file.parent
        if any(site.glob("QtWidgets.*")) and any(site.glob("QtWebEngineWidgets.*")):
            return True

    return False


def _maybe_reexec_into_qt_venv() -> None:
    if _is_frozen_app():
        return

    if os.environ.get("EXOCORTEX_BOOTSTRAPPED") == "1":
        return

    force = os.environ.get("EXOCORTEX_FORCE_QT_PYTHON") == "1"
    required_modules = [
        "PySide6",
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtWebEngineWidgets",
    ]
    if not force and all(importlib.util.find_spec(m) is not None for m in required_modules):
        return

    explicit_python = os.environ.get("EXOCORTEX_QT_PYTHON")
    if explicit_python:
        python_exe = Path(explicit_python).expanduser()
        if python_exe.is_file() and python_exe.resolve() != Path(sys.executable).resolve():
            os.environ["EXOCORTEX_BOOTSTRAPPED"] = "1"
            os.execv(str(python_exe), [str(python_exe), __file__, *sys.argv[1:]])

    venv_dirs: list[Path] = []
    explicit_venvs = os.environ.get("EXOCORTEX_QT_VENVS")
    if explicit_venvs:
        venv_dirs.extend(_parse_path_list(explicit_venvs))

    repo_root = Path(__file__).resolve().parent
    venv_dirs.extend(
        [
            repo_root / ".venv",
            repo_root / "venv",
            repo_root / ".venv-qt",
            repo_root / "venv-qt",
            repo_root / "qt-venv",
            repo_root / "pyside6-venv",
        ]
    )

    for venv_dir in venv_dirs:
        venv_dir = venv_dir.expanduser()
        python_exe = _venv_python_exe(venv_dir)
        if python_exe is None:
            continue
        if python_exe.resolve() == Path(sys.executable).resolve():
            continue
        if not _venv_has_required_qt(venv_dir):
            continue

        os.environ["EXOCORTEX_BOOTSTRAPPED"] = "1"
        os.execv(str(python_exe), [str(python_exe), __file__, *sys.argv[1:]])


_maybe_reexec_into_qt_venv()
_configure_qt_runtime_for_frozen_app()
_configure_qt_runtime_for_dev_python()

from pdf_block_gui_lib import Block, MainWindow, PdfPageView, PdfRenderer, main

__all__ = [
    "Block",
    "MainWindow",
    "PdfPageView",
    "PdfRenderer",
    "main",
]


if __name__ == "__main__":
    main()
