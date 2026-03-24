from __future__ import annotations

import time
from pathlib import Path

import pytest

from server.errors import ApiError
from server.tasking.contracts import JsonObject, TaskResult
from server.tasking.manager import TaskManager


@pytest.fixture
def task_manager() -> TaskManager:
    manager = TaskManager(max_workers=1, event_buffer_size=32)
    try:
        yield manager
    finally:
        manager.close()


def _wait_for_terminal_task(manager: TaskManager, task_id: str, timeout_seconds: float = 3.0) -> JsonObject:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        detail = manager.get_task(task_id)
        if detail["status"] in {"completed", "failed"}:
            return detail
        time.sleep(0.01)
    raise AssertionError(f"task {task_id} did not finish within {timeout_seconds} seconds")


def test_task_manager_normalizes_task_result_payload(task_manager: TaskManager) -> None:
    def _runner(_context: object) -> TaskResult:
        return TaskResult(
            message="done",
            artifact_path=Path("out/result.md"),
            payload={
                "mainPath": Path("assets/raw.pdf"),
                "nested": [Path("tmp/a"), {"leaf": Path("tmp/b")}],
            },
        )

    summary = task_manager.submit_task(
        kind="demo",
        title="Demo Task",
        asset_name="asset-1",
        runner=_runner,
    )
    detail = _wait_for_terminal_task(task_manager, summary["id"])

    assert detail["status"] == "completed"
    assert detail["result"]["message"] == "done"
    assert detail["result"]["artifactPath"] == str(Path("out/result.md"))
    assert detail["result"]["payload"] == {
        "mainPath": str(Path("assets/raw.pdf")),
        "nested": [str(Path("tmp/a")), {"leaf": str(Path("tmp/b"))}],
    }


def test_task_manager_reports_structured_payload_for_api_error(task_manager: TaskManager) -> None:
    def _runner(_context: object) -> None:
        raise ApiError(
            status_code=409,
            code="asset_locked",
            message="Asset is locked",
            details={"path": Path("assets/current")},
        )

    summary = task_manager.submit_task(
        kind="demo",
        title="Failing Task",
        asset_name="asset-2",
        runner=_runner,
    )
    detail = _wait_for_terminal_task(task_manager, summary["id"])
    payload = detail["latestEvent"]["payload"]

    assert detail["status"] == "failed"
    assert payload["code"] == "asset_locked"
    assert payload["statusCode"] == 409
    assert payload["exceptionType"] == "ApiError"
    assert payload["details"] == {"path": str(Path("assets/current"))}
    assert detail["result"]["payload"] == payload


def test_task_manager_reports_structured_payload_for_unexpected_error(task_manager: TaskManager) -> None:
    def _runner(_context: object) -> None:
        raise ValueError("unexpected boom")

    summary = task_manager.submit_task(
        kind="demo",
        title="Unexpected Failure",
        asset_name=None,
        runner=_runner,
    )
    detail = _wait_for_terminal_task(task_manager, summary["id"])
    payload = detail["latestEvent"]["payload"]

    assert detail["status"] == "failed"
    assert payload["code"] == "task_failed"
    assert payload["details"] == {"message": "unexpected boom"}
    assert payload["exceptionType"] == "ValueError"
    assert "statusCode" not in payload
    assert detail["result"]["payload"] == payload


def test_task_manager_rejects_duplicate_active_dedupe_key(task_manager: TaskManager) -> None:
    started = False

    def _runner(_context: object) -> TaskResult:
        nonlocal started
        started = True
        time.sleep(0.2)
        return TaskResult(message="done")

    task_manager.submit_task(
        kind="group_dive",
        title="Group dive: group 2",
        asset_name="asset-1",
        runner=_runner,
        dedupe_key="group_dive:asset-1:2",
    )

    deadline = time.monotonic() + 1.0
    while not started and time.monotonic() < deadline:
        time.sleep(0.01)

    with pytest.raises(ApiError) as exc_info:
        task_manager.submit_task(
            kind="group_dive",
            title="Group dive: group 2",
            asset_name="asset-1",
            runner=_runner,
            dedupe_key="group_dive:asset-1:2",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "task_already_running"
