from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Literal

from .contracts import JsonObject, JsonValue, TaskFailure, TaskResult


TaskStatus = Literal["queued", "running", "completed", "failed"]
TaskEventType = Literal["queued", "started", "progress", "log", "artifact", "completed", "failed"]
TaskEventPayload = JsonObject | TaskFailure | None
TaskRunnerResult = TaskResult | JsonValue | Path | None
TaskRunner = Callable[["TaskContext"], TaskRunnerResult]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(slots=True)
class TaskEvent:
    task_id: str
    kind: str
    asset_name: str | None
    status: TaskStatus
    event_type: TaskEventType
    message: str
    progress: float | None = None
    artifact_path: str | None = None
    payload: TaskEventPayload = None
    timestamp: datetime = field(default_factory=utc_now)

    def to_wire(self) -> JsonObject:
        payload: JsonObject | None
        if isinstance(self.payload, TaskFailure):
            payload = self.payload.to_payload()
        else:
            payload = self.payload
        return {
            "taskId": self.task_id,
            "kind": self.kind,
            "assetName": self.asset_name,
            "status": self.status,
            "eventType": self.event_type,
            "message": self.message,
            "progress": self.progress,
            "artifactPath": self.artifact_path,
            "payload": payload,
            "timestamp": isoformat_z(self.timestamp),
        }


@dataclass(slots=True)
class TaskRecord:
    id: str
    kind: str
    title: str
    asset_name: str | None
    status: TaskStatus
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    events: list[TaskEvent] = field(default_factory=list)
    result: TaskResult | None = None

    def summary(self) -> JsonObject:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "title": self.title,
            "assetName": self.asset_name,
            "createdAt": isoformat_z(self.created_at),
            "updatedAt": isoformat_z(self.updated_at),
        }

    def detail(self) -> JsonObject:
        latest_event = self.events[-1].to_wire() if self.events else None
        data = self.summary()
        data["events"] = [event.to_wire() for event in self.events]
        data["latestEvent"] = latest_event
        data["result"] = self.result.to_wire() if self.result is not None else None
        return data


class TaskContext:
    def __init__(self, manager: "TaskManagerProtocol", record: TaskRecord) -> None:
        self._manager = manager
        self._record = record

    @property
    def task_id(self) -> str:
        return self._record.id

    @property
    def kind(self) -> str:
        return self._record.kind

    @property
    def title(self) -> str:
        return self._record.title

    @property
    def asset_name(self) -> str | None:
        return self._record.asset_name

    def emit(
        self,
        event_type: TaskEventType,
        message: str,
        *,
        progress: float | None = None,
        artifact_path: str | Path | None = None,
        payload: JsonObject | None = None,
    ) -> None:
        self._manager.publish_event(
            self._record.id,
            event_type,
            message,
            progress=progress,
            artifact_path=artifact_path,
            payload=payload,
        )

    def log(self, message: str, *, payload: JsonObject | None = None) -> None:
        self.emit("log", message, payload=payload)

    def progress(self, message: str, value: float | None = None) -> None:
        self.emit("progress", message, progress=value)

    def artifact(
        self,
        path: str | Path,
        message: str,
        *,
        payload: JsonObject | None = None,
    ) -> None:
        self.emit("artifact", message, artifact_path=path, payload=payload)


class TaskManagerProtocol:
    def publish_event(
        self,
        task_id: str,
        event_type: TaskEventType,
        message: str,
        *,
        progress: float | None = None,
        artifact_path: str | Path | None = None,
        payload: TaskEventPayload = None,
    ) -> TaskEvent:
        raise NotImplementedError


__all__ = [
    "TaskContext",
    "TaskEvent",
    "TaskEventPayload",
    "TaskEventType",
    "TaskRecord",
    "TaskRunner",
    "TaskRunnerResult",
    "TaskStatus",
    "isoformat_z",
    "utc_now",
]
