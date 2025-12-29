from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from typing import Iterable


def safe_rmtree(path: Path) -> None:
    """Remove a directory tree, clearing read-only flags on Windows if needed."""

    def _handle_remove_readonly(func, target, exc_info):  # noqa: ARG001
        try:
            os.chmod(target, stat.S_IWRITE)
        except Exception:
            pass
        func(target)

    shutil.rmtree(path, onerror=_handle_remove_readonly)


def safe_unlink(path: Path) -> None:
    """Remove a file, clearing read-only flags on Windows if needed."""
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except PermissionError:
        try:
            os.chmod(path, stat.S_IWRITE)
        except Exception:
            pass
        path.unlink(missing_ok=True)


def copy_files(
    sources: Iterable[Path],
    destination_dir: Path,
    rename: dict[str, str] | None = None,
) -> list[Path]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    rename = rename or {}
    for source in sources:
        if not source.is_file():
            raise FileNotFoundError(f"Source file not found: {source}")
        target_name = rename.get(source.name, source.name)
        destination = destination_dir / target_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.unlink(missing_ok=True)
        shutil.copy2(source, destination)
        copied.append(destination)
    return copied


def move_all_files(
    src_dir: Path,
    dst_dir: Path,
    *,
    rename: dict[str, str] | None = None,
) -> list[Path]:
    """Move all files from src_dir into dst_dir, optionally renaming selected files."""
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)
    moved_files: list[Path] = []
    rename = rename or {}

    for path in src_dir.iterdir():
        if not path.is_file():
            continue
        target_name = rename.get(path.name, path.name)
        destination = dst_dir / target_name
        destination.unlink(missing_ok=True)
        moved_files.append(Path(shutil.move(str(path), destination)))
    return moved_files


def copy_all_files(
    src_dir: Path,
    dst_dir: Path,
    *,
    rename: dict[str, str] | None = None,
) -> list[Path]:
    """Copy all files from src_dir into dst_dir, optionally renaming selected files."""
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_dir}")

    dst_dir.mkdir(parents=True, exist_ok=True)
    copied_files: list[Path] = []
    rename = rename or {}

    for path in src_dir.iterdir():
        if not path.is_file():
            continue
        target_name = rename.get(path.name, path.name)
        destination = dst_dir / target_name
        destination.unlink(missing_ok=True)
        shutil.copy2(path, destination)
        copied_files.append(destination)
    return copied_files

