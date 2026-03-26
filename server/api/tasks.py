from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, WebSocket, WebSocketDisconnect, status

from server.api.task_helpers import submit_asset_init_upload_task, submit_bug_finder_upload_task
from server.dependencies import get_task_manager
from server.errors import ApiError
from server.schemas import (
    AskTutorWorkflowRequest,
    CompressTaskRequest,
    FixLatexWorkflowRequest,
    GroupWorkflowRequest,
    ReTutorWorkflowRequest,
    TaskDetailModel,
    TaskSummaryModel,
    TutorWorkflowRequest,
)
from server.services import workflows
from server.tasking import TaskManager


router = APIRouter(tags=["tasks"])


@router.get("/tasks", response_model=list[TaskSummaryModel])
def list_tasks(task_manager: TaskManager = Depends(get_task_manager)) -> list[TaskSummaryModel]:
    return [TaskSummaryModel(**task) for task in task_manager.list_tasks()]


@router.get("/tasks/{task_id}", response_model=TaskDetailModel)
def get_task(task_id: str, task_manager: TaskManager = Depends(get_task_manager)) -> TaskDetailModel:
    try:
        detail = task_manager.get_task(task_id)
    except KeyError as exc:
        raise ApiError(404, "task_not_found", f"Task '{task_id}' not found.") from exc
    return TaskDetailModel(**detail)


@router.post("/tasks/asset-init", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_asset_init(
    source_file: UploadFile = File(...),
    markdown_file: UploadFile = File(...),
    content_list_file: UploadFile = File(...),
    asset_name: str = Form(...),
    asset_subfolder: str | None = Form(None),
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = submit_asset_init_upload_task(
        task_manager=task_manager,
        source_file=source_file,
        markdown_file=markdown_file,
        content_list_file=content_list_file,
        asset_name=asset_name,
        asset_subfolder=asset_subfolder,
        temp_prefix="exocortex_web_asset_task_",
    )
    return TaskSummaryModel(**task)


@router.post("/tasks/compress-preview", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_compress_preview(
    request: CompressTaskRequest,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = workflows.submit_compress_preview_task(
        task_manager,
        asset_name=request.assetName,
        fraction_rect=(
            request.fractionRect.x,
            request.fractionRect.y,
            request.fractionRect.width,
            request.fractionRect.height,
        ),
        ratio=request.ratio,
        compress_scale=request.compressScale,
        draw_badge=request.drawBadge,
        badge_position=request.badgePosition,
    )
    return TaskSummaryModel(**task)


@router.post("/tasks/compress-execute", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_compress_execute(
    request: CompressTaskRequest,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = workflows.submit_compress_execute_task(
        task_manager,
        asset_name=request.assetName,
        fraction_rect=(
            request.fractionRect.x,
            request.fractionRect.y,
            request.fractionRect.width,
            request.fractionRect.height,
        ),
        ratio=request.ratio,
        compress_scale=request.compressScale,
        draw_badge=request.drawBadge,
        badge_position=request.badgePosition,
    )
    return TaskSummaryModel(**task)


@router.post("/tasks/group-dive", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_group_dive(
    request: GroupWorkflowRequest,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = workflows.submit_group_dive_task(task_manager, asset_name=request.assetName, group_idx=request.groupIdx)
    return TaskSummaryModel(**task)


@router.post("/tasks/flashcard", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_flashcard(
    request: GroupWorkflowRequest,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = workflows.submit_flashcard_task(task_manager, asset_name=request.assetName, group_idx=request.groupIdx)
    return TaskSummaryModel(**task)


@router.post("/tasks/ask-tutor", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_ask_tutor(
    request: AskTutorWorkflowRequest,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = workflows.submit_ask_tutor_task(
        task_manager,
        asset_name=request.assetName,
        group_idx=request.groupIdx,
        tutor_idx=request.tutorIdx,
        question=request.question,
    )
    return TaskSummaryModel(**task)


@router.post("/tasks/re-tutor", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_re_tutor(
    request: ReTutorWorkflowRequest,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = workflows.submit_re_tutor_task(
        task_manager,
        asset_name=request.assetName,
        group_idx=request.groupIdx,
        tutor_idx=request.tutorIdx,
        question=request.question,
    )
    return TaskSummaryModel(**task)


@router.post("/tasks/integrate", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_integrate(
    request: TutorWorkflowRequest,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = workflows.submit_integrate_task(
        task_manager,
        asset_name=request.assetName,
        group_idx=request.groupIdx,
        tutor_idx=request.tutorIdx,
    )
    return TaskSummaryModel(**task)


@router.post("/tasks/bug-finder", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_bug_finder(
    assetName: str = Form(...),
    groupIdx: int = Form(...),
    tutorIdx: int = Form(...),
    manuscript_files: list[UploadFile] = File(...),
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = submit_bug_finder_upload_task(
        task_manager=task_manager,
        asset_name=assetName,
        group_idx=groupIdx,
        tutor_idx=tutorIdx,
        manuscript_files=manuscript_files,
        temp_prefix="exocortex_web_bug_finder_",
    )
    return TaskSummaryModel(**task)


@router.post("/tasks/student-note", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_student_note(
    request: TutorWorkflowRequest,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = workflows.submit_student_note_task(
        task_manager,
        asset_name=request.assetName,
        group_idx=request.groupIdx,
        tutor_idx=request.tutorIdx,
    )
    return TaskSummaryModel(**task)


@router.post("/tasks/fix-latex", response_model=TaskSummaryModel, status_code=status.HTTP_202_ACCEPTED)
def submit_fix_latex(
    request: FixLatexWorkflowRequest,
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = workflows.submit_fix_latex_task(
        task_manager,
        asset_name=request.assetName,
        markdown_path=request.markdownPath,
    )
    return TaskSummaryModel(**task)


@router.websocket("/ws/tasks")
async def tasks_websocket(
    websocket: WebSocket,
    replay: bool = Query(False),
    task_manager: TaskManager = Depends(get_task_manager),
) -> None:
    await websocket.accept()
    subscriber_id, queue = await task_manager.register_subscriber()
    try:
        if replay:
            for event in task_manager.iter_events():
                await websocket.send_json(event)
        while True:
            queue_task = asyncio.create_task(queue.get())
            receive_task = asyncio.create_task(websocket.receive())
            done, pending = await asyncio.wait(
                {queue_task, receive_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for pending_task in pending:
                pending_task.cancel()

            if receive_task in done:
                message = receive_task.result()
                if message.get("type") == "websocket.disconnect":
                    break

            if queue_task in done:
                await websocket.send_json(queue_task.result())
    except WebSocketDisconnect:
        return
    finally:
        task_manager.unregister_subscriber(subscriber_id)


__all__ = ["router"]
