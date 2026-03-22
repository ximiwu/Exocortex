from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Literal


logger = logging.getLogger(__name__)

WorkflowEventType = Literal[
    "queued",
    "started",
    "progress",
    "log",
    "artifact",
    "completed",
    "failed",
]


@dataclass(frozen=True)
class WorkflowEvent:
    type: WorkflowEventType
    message: str
    progress: float | None = None
    artifact_path: str | None = None
    payload: dict[str, Any] | None = None


WorkflowEventCallback = Callable[[WorkflowEvent], None]


def make_workflow_event(
    event_type: WorkflowEventType,
    message: str,
    *,
    progress: float | None = None,
    artifact_path: str | Path | None = None,
    payload: dict[str, Any] | None = None,
) -> WorkflowEvent:
    if progress is not None:
        progress = max(0.0, min(1.0, float(progress)))
    artifact_value: str | None = None
    if artifact_path is not None:
        artifact_value = str(Path(artifact_path))
    return WorkflowEvent(
        type=event_type,
        message=message,
        progress=progress,
        artifact_path=artifact_value,
        payload=payload,
    )


def emit_workflow_event(
    callback: WorkflowEventCallback | None,
    event_type: WorkflowEventType,
    message: str,
    *,
    progress: float | None = None,
    artifact_path: str | Path | None = None,
    payload: dict[str, Any] | None = None,
) -> WorkflowEvent:
    event = make_workflow_event(
        event_type,
        message,
        progress=progress,
        artifact_path=artifact_path,
        payload=payload,
    )
    if callback is not None:
        try:
            callback(event)
        except Exception as exc:  # pragma: no cover - defensive callback guard
            logger.warning("Workflow event callback failed for %s: %s", event_type, exc)
    return event


__all__ = [
    "WorkflowEvent",
    "WorkflowEventCallback",
    "WorkflowEventType",
    "emit_workflow_event",
    "make_workflow_event",
]
