from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from server.errors import ApiError

from .assets import resolve_asset_dir, resolve_relative_file


def _reveal_path(path: Path, *, select_file: bool) -> Path:
    if sys.platform.startswith("win"):
        try:
            if select_file and path.is_file():
                subprocess.Popen(["explorer.exe", "/select,", str(path.resolve())])
            else:
                os.startfile(path)  # type: ignore[attr-defined]
        except Exception as exc:
            raise ApiError(500, "reveal_failed", f"Failed to reveal path '{path}'.") from exc
        return path
    if sys.platform == "darwin":
        subprocess.Popen(["open", "-R", str(path)] if select_file else ["open", str(path)])
        return path
    subprocess.Popen(["xdg-open", str(path.parent if select_file else path)])
    return path


def reveal_asset(asset_name: str) -> Path:
    asset_dir = resolve_asset_dir(asset_name)
    return _reveal_path(asset_dir, select_file=False)


def reveal_asset_file(asset_name: str, raw_path: str) -> Path:
    file_path = resolve_relative_file(asset_name, raw_path)
    return _reveal_path(file_path, select_file=True)


__all__ = ["reveal_asset", "reveal_asset_file"]
