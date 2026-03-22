from __future__ import annotations

import os

from exocortex_core.paths import repo_root


APP_TITLE = "Exocortex Web API"
APP_VERSION = "0.1.0"
HOST = "127.0.0.1"
API_PREFIX = "/api"
WS_TASKS_PATH = f"{API_PREFIX}/ws/tasks"

DEFAULT_RENDER_DPI = 130
MIN_RENDER_DPI = 72
MAX_RENDER_DPI = 1200

TASK_EVENT_BUFFER_SIZE = 512
TASK_SUBSCRIBER_QUEUE_SIZE = 256
TASK_MAX_WORKERS = max(4, min(16, (os.cpu_count() or 4)))

WEB_DIST_DIR = repo_root() / "web" / "dist"
WEB_INDEX_PATH = WEB_DIST_DIR / "index.html"


def browser_root_url(port: int) -> str:
    return f"http://{HOST}:{port}/"


def health_url(port: int) -> str:
    return f"http://{HOST}:{port}{API_PREFIX}/health"


__all__ = [
    "API_PREFIX",
    "APP_TITLE",
    "APP_VERSION",
    "DEFAULT_RENDER_DPI",
    "HOST",
    "MAX_RENDER_DPI",
    "MIN_RENDER_DPI",
    "TASK_EVENT_BUFFER_SIZE",
    "TASK_MAX_WORKERS",
    "TASK_SUBSCRIBER_QUEUE_SIZE",
    "WEB_DIST_DIR",
    "WEB_INDEX_PATH",
    "WS_TASKS_PATH",
    "browser_root_url",
    "health_url",
]
