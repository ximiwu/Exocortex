from __future__ import annotations

import os
import shutil
import stat
import tempfile
import threading
import time
from pathlib import Path
from typing import Iterable

_ATOMIC_REPLACE_RETRY_DELAYS: tuple[float, ...] = (0.02, 0.05, 0.1, 0.2, 0.35)
_ATOMIC_WRITE_LOCKS: dict[str, threading.Lock] = {}
_ATOMIC_WRITE_LOCKS_GUARD = threading.Lock()


def _atomic_write_lock(path: Path) -> threading.Lock:
    key = os.path.normcase(os.path.abspath(path))
    with _ATOMIC_WRITE_LOCKS_GUARD:
        lock = _ATOMIC_WRITE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _ATOMIC_WRITE_LOCKS[key] = lock
    return lock


def _is_retryable_replace_error(exc: OSError) -> bool:
    return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {5, 32}


def atomic_write_text(
    path: Path,
    text: str,
    *,
    encoding: str = "utf-8",
    newline: str | None = None,
    retry_delays: tuple[float, ...] = _ATOMIC_REPLACE_RETRY_DELAYS,
) -> Path:
    """Write text via a same-directory temp file, retrying transient replace failures."""
    path.parent.mkdir(parents=True, exist_ok=True)

    with _atomic_write_lock(path):
        tmp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding=encoding,
                newline=newline,
                dir=path.parent,
                prefix=f".{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                handle.write(text)
                handle.flush()
                try:
                    os.fsync(handle.fileno())
                except OSError:
                    pass
                tmp_path = Path(handle.name)

            for attempt in range(len(retry_delays) + 1):
                try:
                    os.replace(tmp_path, path)
                    tmp_path = None
                    return path
                except OSError as exc:
                    if attempt >= len(retry_delays) or not _is_retryable_replace_error(exc):
                        raise
                    time.sleep(retry_delays[attempt])
        finally:
            if tmp_path is not None:
                safe_unlink(tmp_path)

    return path


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
