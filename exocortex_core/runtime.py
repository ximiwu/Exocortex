from __future__ import annotations

import os


EXOCORTEX_RUNTIME_MODE_ENV = "EXOCORTEX_RUNTIME_MODE"
RUNTIME_MODE_DEV = "dev"
RUNTIME_MODE_PRODUCTION = "production"


def get_runtime_mode() -> str:
    raw = os.environ.get(EXOCORTEX_RUNTIME_MODE_ENV, "").strip().lower()
    if raw == RUNTIME_MODE_DEV:
        return RUNTIME_MODE_DEV
    return RUNTIME_MODE_PRODUCTION


def set_runtime_mode(mode: str) -> None:
    normalized = mode.strip().lower()
    os.environ[EXOCORTEX_RUNTIME_MODE_ENV] = (
        RUNTIME_MODE_DEV if normalized == RUNTIME_MODE_DEV else RUNTIME_MODE_PRODUCTION
    )


def is_dev_runtime() -> bool:
    return get_runtime_mode() == RUNTIME_MODE_DEV


__all__ = [
    "EXOCORTEX_RUNTIME_MODE_ENV",
    "RUNTIME_MODE_DEV",
    "RUNTIME_MODE_PRODUCTION",
    "get_runtime_mode",
    "is_dev_runtime",
    "set_runtime_mode",
]
