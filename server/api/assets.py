from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from server.api.task_helpers import submit_asset_init_upload_task
from server.dependencies import get_task_manager
from server.schemas import (
    AssetStateModel,
    AssetSummaryModel,
    CreateTutorRequest,
    MessageResponse,
    TaskSummaryModel,
    TutorSessionModel,
)
from server.services import assets as asset_service
from server.services import system as system_service
from server.tasking import TaskManager


router = APIRouter(tags=["assets"])


@router.get("/assets", response_model=list[AssetSummaryModel])
def list_assets() -> list[AssetSummaryModel]:
    return asset_service.list_asset_summaries()


@router.get("/assets/{asset_name:path}/state", response_model=AssetStateModel)
def get_asset_state(asset_name: str) -> AssetStateModel:
    return asset_service.build_asset_state(asset_name)


@router.post(
    "/assets/import",
    response_model=TaskSummaryModel,
    status_code=status.HTTP_202_ACCEPTED,
)
def import_asset(
    source_file: UploadFile = File(...),
    asset_name: str = Form(...),
    asset_subfolder: str | None = Form(None),
    skip_img2md_markdown_file: UploadFile | None = File(None),
    compress_enabled: bool = Form(False),
    task_manager: TaskManager = Depends(get_task_manager),
) -> TaskSummaryModel:
    task = submit_asset_init_upload_task(
        task_manager=task_manager,
        source_file=source_file,
        asset_name=asset_name,
        asset_subfolder=asset_subfolder,
        skip_img2md_markdown_file=skip_img2md_markdown_file,
        temp_prefix="exocortex_web_asset_import_",
    )
    return TaskSummaryModel(**task)


@router.get("/assets/{asset_name:path}/references/{name}", response_class=FileResponse)
def get_reference(asset_name: str, name: str) -> FileResponse:
    path = asset_service.resolve_reference_file(asset_name, name)
    return FileResponse(path, media_type="text/markdown; charset=utf-8", filename=path.name)


@router.post("/assets/{asset_name:path}/reveal", response_model=MessageResponse)
def reveal_asset(asset_name: str, path: str | None = Query(None, min_length=1)) -> MessageResponse:
    target = system_service.reveal_asset_file(asset_name, path) if path else system_service.reveal_asset(asset_name)
    return MessageResponse(message=f"Revealed {target}.")


@router.delete(
    "/assets/{asset_name:path}/groups/{group_idx}/tutors/{tutor_idx}/questions",
    response_model=MessageResponse,
)
def delete_question(
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    path: str = Query(..., min_length=1),
) -> MessageResponse:
    asset_service.delete_question(asset_name, group_idx, tutor_idx, path)
    return MessageResponse(message=f"Deleted question '{Path(path).name}'.")


@router.post(
    "/assets/{asset_name:path}/groups/{group_idx}/tutors",
    response_model=TutorSessionModel,
    status_code=status.HTTP_201_CREATED,
)
def create_tutor_session(asset_name: str, group_idx: int, request: CreateTutorRequest) -> TutorSessionModel:
    return asset_service.create_tutor_session(asset_name, group_idx, request.focusMarkdown)


@router.delete("/assets/{asset_name:path}", response_model=MessageResponse)
def delete_asset(asset_name: str) -> MessageResponse:
    normalized = asset_service.normalize_asset_name(asset_name)
    asset_service.delete_asset(normalized)
    return MessageResponse(message=f"Deleted asset '{normalized}'.")


__all__ = ["router"]
