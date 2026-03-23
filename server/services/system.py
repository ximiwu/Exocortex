from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

from exocortex_core.fs import atomic_write_text
from exocortex_core.paths import user_documents_dir
from server.errors import ApiError
from server.schemas import AppConfigModel
from server.schemas.system import TutorReasoningEffort

from .assets import resolve_asset_dir, resolve_relative_file

APP_CONFIG_DIR_RELATIVE = Path("ximiwu_app") / "Exocortex"
APP_CONFIG_FILENAME = "config.json"
ThemeMode = Literal["light", "dark"]


def _app_config_path() -> Path:
    return user_documents_dir() / APP_CONFIG_DIR_RELATIVE / APP_CONFIG_FILENAME


def _normalize_int_in_range(raw: object, *, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(raw)
    except Exception:
        return default
    if value < minimum or value > maximum:
        return default
    return value


def _load_app_config_data() -> dict[str, object]:
    path = _app_config_path()
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}


def _normalize_theme_mode(raw: object, *, default: ThemeMode) -> ThemeMode:
    return raw if raw in {"light", "dark"} else default


def _normalize_reasoning_effort(raw: object, *, default: TutorReasoningEffort) -> TutorReasoningEffort:
    return raw if raw in {"low", "medium", "high", "xhigh"} else default


def _normalize_bool(raw: object, *, default: bool) -> bool:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        normalized = raw.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


def _write_app_config_data(data: dict[str, object]) -> None:
    path = _app_config_path()
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def get_app_config() -> AppConfigModel:
    data = _load_app_config_data()
    return AppConfigModel(
        themeMode=_normalize_theme_mode(
            data.get("theme_mode"),
            default="light",
        ),
        sidebarTextLineClamp=_normalize_int_in_range(
            data.get("sidebar_text_line_clamp"),
            default=1,
            minimum=1,
            maximum=6,
        ),
        sidebarFontSizePx=_normalize_int_in_range(
            data.get("sidebar_font_size_px"),
            default=14,
            minimum=10,
            maximum=24,
        ),
        tutorReasoningEffort=_normalize_reasoning_effort(
            data.get("tutor_reasoning_effort"),
            default="medium",
        ),
        tutorWithGlobalContext=_normalize_bool(
            data.get("tutor_with_global_context"),
            default=True,
        ),
    )


def update_app_config(
    *,
    theme_mode: ThemeMode | None = None,
    sidebar_text_line_clamp: int | None = None,
    sidebar_font_size_px: int | None = None,
    tutor_reasoning_effort: TutorReasoningEffort | None = None,
    tutor_with_global_context: bool | None = None,
) -> AppConfigModel:
    current = get_app_config()
    next_theme_mode = current.themeMode if theme_mode is None else theme_mode
    next_sidebar_text_line_clamp = (
        current.sidebarTextLineClamp if sidebar_text_line_clamp is None else int(sidebar_text_line_clamp)
    )
    next_sidebar_font_size_px = (
        current.sidebarFontSizePx if sidebar_font_size_px is None else int(sidebar_font_size_px)
    )
    next_tutor_reasoning_effort = (
        current.tutorReasoningEffort if tutor_reasoning_effort is None else tutor_reasoning_effort
    )
    next_tutor_with_global_context = (
        current.tutorWithGlobalContext if tutor_with_global_context is None else bool(tutor_with_global_context)
    )
    normalized = AppConfigModel(
        themeMode=next_theme_mode,
        sidebarTextLineClamp=next_sidebar_text_line_clamp,
        sidebarFontSizePx=next_sidebar_font_size_px,
        tutorReasoningEffort=next_tutor_reasoning_effort,
        tutorWithGlobalContext=next_tutor_with_global_context,
    )
    _write_app_config_data(
        {
            "theme_mode": normalized.themeMode,
            "sidebar_text_line_clamp": normalized.sidebarTextLineClamp,
            "sidebar_font_size_px": normalized.sidebarFontSizePx,
            "tutor_reasoning_effort": normalized.tutorReasoningEffort,
            "tutor_with_global_context": normalized.tutorWithGlobalContext,
        }
    )
    return normalized


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


__all__ = ["get_app_config", "reveal_asset", "reveal_asset_file", "update_app_config"]
