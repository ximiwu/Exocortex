from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable

from exocortex_core.fs import move_all_files as _fs_move_all_files
from exocortex_core.fs import safe_rmtree as _fs_safe_rmtree


def dir_has_content(path: Path) -> bool:
    """Return True if the directory exists and contains any entries."""
    return path.is_dir() and any(path.iterdir())


def clean_directory(directory: Path) -> None:
    """Remove all files/subdirectories under the given directory."""
    directory.mkdir(parents=True, exist_ok=True)
    for path in directory.iterdir():
        if path.is_file() or path.is_symlink():
            path.unlink()
        else:
            safe_rmtree(path)


def next_markdown_index(directory: Path) -> int:
    """Return the next numeric filename (1-based) under directory for *.md files."""
    if not directory.is_dir():
        return 1
    max_index = 0
    for path in directory.iterdir():
        if not path.is_file() or path.suffix.lower() != ".md":
            continue
        stem = path.stem
        if stem.isdigit():
            try:
                max_index = max(max_index, int(stem))
            except ValueError:  # pragma: no cover - defensive
                continue
    return max_index + 1


def next_directory_index(directory: Path) -> int:
    """Return the next numeric directory name (1-based) under directory."""
    if not directory.is_dir():
        return 1
    max_index = 0
    for path in directory.iterdir():
        if not path.is_dir():
            continue
        name = path.name
        if not name.isdigit():
            continue
        try:
            max_index = max(max_index, int(name))
        except ValueError:  # pragma: no cover - defensive
            continue
    return max_index + 1


def safe_rmtree(path: Path) -> None:
    _fs_safe_rmtree(path)


def copy_raw_pdf(pdf_path: Path, asset_dir: Path) -> Path:
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / "raw.pdf"
    try:
        if pdf_path.resolve() == target.resolve():
            return target
    except Exception:
        pass
    shutil.copy2(pdf_path, target)
    return target


def move_all_files(src_dir: Path, dst_dir: Path, rename: dict[str, str] | None = None) -> list[Path]:
    """Move all files from src_dir into dst_dir, optionally renaming selected files."""
    moved_files = _fs_move_all_files(src_dir, dst_dir, rename=rename)
    if not moved_files:
        raise FileNotFoundError(f"No files found to move in {src_dir}")
    return moved_files


def copy_all_files(
    src_dir: Path, dst_dirs: Iterable[Path], rename: dict[str, str] | None = None
) -> list[Path]:
    """Copy all files from src_dir into each dst_dir, optionally renaming selected files."""
    if not src_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {src_dir}")

    destinations = list(dst_dirs)
    if not destinations:
        raise ValueError("No destination directories provided.")

    for dst_dir in destinations:
        dst_dir.mkdir(parents=True, exist_ok=True)

    copied_files: list[Path] = []
    source_files = [path for path in src_dir.iterdir() if path.is_file()]
    if not source_files:
        raise FileNotFoundError(f"No files found to copy in {src_dir}")

    rename = rename or {}
    for path in source_files:
        target_name = rename.get(path.name, path.name)
        data = path.read_bytes()
        for dst_dir in destinations:
            destination = dst_dir / target_name
            destination.unlink(missing_ok=True)
            destination.write_bytes(data)
            copied_files.append(destination)

    return copied_files

