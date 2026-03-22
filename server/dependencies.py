from __future__ import annotations

from starlette.requests import HTTPConnection

from .tasking.manager import TaskManager


def get_task_manager(connection: HTTPConnection) -> TaskManager:
    manager = getattr(connection.app.state, "task_manager", None)
    if manager is None:
        raise RuntimeError("Task manager not initialized.")
    return manager


__all__ = ["get_task_manager"]
