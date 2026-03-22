from __future__ import annotations

import asyncio
import dataclasses
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from server.config import TASK_EVENT_BUFFER_SIZE, TASK_MAX_WORKERS, TASK_SUBSCRIBER_QUEUE_SIZE
from server.errors import ApiError

from .contracts import JsonObject, JsonValue, TaskFailure, TaskResult
from .models import TaskContext, TaskEvent, TaskEventPayload, TaskEventType, TaskRecord, TaskRunner


logger = logging.getLogger(__name__)


@dataclasses.dataclass(slots=True)
class _Subscriber:
    id: str
    loop: asyncio.AbstractEventLoop
    queue: asyncio.Queue[JsonObject]


class TaskManager:
    def __init__(
        self,
        *,
        max_workers: int = TASK_MAX_WORKERS,
        event_buffer_size: int = TASK_EVENT_BUFFER_SIZE,
    ) -> None:
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="exocortex-task")
        self._event_buffer_size = max(16, event_buffer_size)
        self._records: dict[str, TaskRecord] = {}
        self._subscribers: dict[str, _Subscriber] = {}
        self._lock = threading.RLock()

    def close(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)

    def list_tasks(self) -> list[JsonObject]:
        with self._lock:
            records = sorted(self._records.values(), key=lambda item: item.created_at, reverse=True)
            return [record.summary() for record in records]

    def get_task(self, task_id: str) -> JsonObject:
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                raise KeyError(task_id)
            return record.detail()

    def iter_events(self) -> list[JsonObject]:
        with self._lock:
            records = sorted(self._records.values(), key=lambda item: item.created_at)
            return [event.to_wire() for record in records for event in record.events]

    async def register_subscriber(self) -> tuple[str, asyncio.Queue[JsonObject]]:
        loop = asyncio.get_running_loop()
        subscriber_id = f"ws_{uuid.uuid4().hex[:12]}"
        queue: asyncio.Queue[JsonObject] = asyncio.Queue(maxsize=TASK_SUBSCRIBER_QUEUE_SIZE)
        with self._lock:
            self._subscribers[subscriber_id] = _Subscriber(id=subscriber_id, loop=loop, queue=queue)
        return subscriber_id, queue

    def unregister_subscriber(self, subscriber_id: str) -> None:
        with self._lock:
            self._subscribers.pop(subscriber_id, None)

    def submit_task(
        self,
        *,
        kind: str,
        title: str,
        asset_name: str | None,
        runner: TaskRunner,
    ) -> JsonObject:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        record = TaskRecord(
            id=task_id,
            kind=kind,
            title=title,
            asset_name=asset_name,
            status="queued",
        )
        with self._lock:
            self._records[task_id] = record
        self.publish_event(task_id, "queued", f"{title} queued.")
        self._executor.submit(self._run_task, task_id, runner)
        return record.summary()

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
        with self._lock:
            record = self._records.get(task_id)
            if record is None:
                raise KeyError(task_id)
            status = self._status_for(record.status, event_type)
            normalized_payload = self._normalize_event_payload(payload)
            event = TaskEvent(
                task_id=task_id,
                kind=record.kind,
                status=status,
                event_type=event_type,
                message=message,
                progress=progress,
                artifact_path=str(artifact_path) if artifact_path is not None else None,
                payload=normalized_payload,
            )
            record.status = status
            record.updated_at = event.timestamp
            record.events.append(event)
            if len(record.events) > self._event_buffer_size:
                record.events = record.events[-self._event_buffer_size :]
            if event_type in {"completed", "failed"}:
                record.result = TaskResult(
                    message=message,
                    artifact_path=event.artifact_path,
                    payload=normalized_payload,
                )
            subscribers = list(self._subscribers.values())
        wire = event.to_wire()
        for subscriber in subscribers:
            try:
                subscriber.loop.call_soon_threadsafe(self._enqueue_event, subscriber.queue, wire)
            except RuntimeError:
                logger.debug("Dropped websocket event for closed loop subscriber %s", subscriber.id)
        return event

    @staticmethod
    def _enqueue_event(queue: asyncio.Queue[JsonObject], payload: JsonObject) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass

    @staticmethod
    def _status_for(current_status: str, event_type: TaskEventType) -> str:
        if event_type == "queued":
            return "queued"
        if event_type in {"started", "progress", "log", "artifact"}:
            return "running"
        if event_type == "completed":
            return "completed"
        if event_type == "failed":
            return "failed"
        return current_status

    @staticmethod
    def _normalize_payload(value: object) -> JsonValue:
        if value is None:
            return None
        if isinstance(value, Path):
            return str(value)
        if dataclasses.is_dataclass(value):
            return TaskManager._normalize_payload(dataclasses.asdict(value))
        if isinstance(value, dict):
            return {str(key): TaskManager._normalize_payload(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [TaskManager._normalize_payload(item) for item in value]
        if isinstance(value, (str, int, float, bool)):
            return value
        return str(value)

    @staticmethod
    def _normalize_object_payload(value: object) -> JsonObject | None:
        normalized = TaskManager._normalize_payload(value)
        if normalized is None:
            return None
        if isinstance(normalized, dict):
            return normalized
        return {"result": normalized}

    @staticmethod
    def _normalize_event_payload(payload: TaskEventPayload) -> JsonObject | None:
        if payload is None:
            return None
        if isinstance(payload, TaskFailure):
            return payload.to_payload()
        return TaskManager._normalize_object_payload(payload)

    def _run_task(self, task_id: str, runner: TaskRunner) -> None:
        with self._lock:
            record = self._records[task_id]
        self.publish_event(task_id, "started", f"{record.title} started.")
        context = TaskContext(self, record)
        try:
            result = runner(context)
            message = f"{record.title} completed."
            artifact_path: str | None = None
            payload: JsonObject | None = None

            if isinstance(result, TaskResult):
                message = result.message or message
                artifact_path = str(result.artifact_path) if result.artifact_path is not None else None
                payload = self._normalize_object_payload(result.payload)
            else:
                normalized = self._normalize_payload(result)
                if isinstance(normalized, dict):
                    artifact_raw = normalized.get("artifactPath")
                    artifact_path = str(artifact_raw) if artifact_raw is not None else None
                    message = str(normalized.get("message") or message)
                    payload_raw = normalized.get("payload")
                    payload = self._normalize_object_payload(payload_raw)
                    extra = {key: value for key, value in normalized.items() if key not in {"artifactPath", "message", "payload"}}
                    if extra:
                        payload = {**(payload or {}), **extra}
                elif isinstance(normalized, str):
                    artifact_path = normalized
                elif normalized is not None:
                    payload = {"result": normalized}

            self.publish_event(
                task_id,
                "completed",
                message,
                artifact_path=artifact_path,
                payload=payload,
            )
        except ApiError as exc:
            self.publish_event(
                task_id,
                "failed",
                f"{record.title} failed: {exc.message}",
                payload=TaskFailure(
                    code=exc.code,
                    details=self._normalize_payload(exc.details),
                    exception_type=type(exc).__name__,
                    status_code=exc.status_code,
                ),
            )
        except Exception as exc:
            self.publish_event(
                task_id,
                "failed",
                f"{record.title} failed: {exc}",
                payload=TaskFailure(
                    code="task_failed",
                    details={"message": str(exc)},
                    exception_type=type(exc).__name__,
                ),
            )


__all__ = ["TaskManager"]
