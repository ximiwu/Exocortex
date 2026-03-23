from __future__ import annotations

from fastapi import UploadFile

from server.domain.workflows.contracts import AssetInitCommand
from server.services import assets as asset_service
from server.services import workflows
from server.tasking import JsonObject, TaskManager

from .uploads import cleanup_upload, parse_asset_name, prepare_asset_upload, stage_upload_batch


def submit_asset_init_upload_task(
    *,
    task_manager: TaskManager,
    source_file: UploadFile,
    markdown_file: UploadFile,
    content_list_file: UploadFile,
    asset_name: str,
    asset_subfolder: str | None,
    temp_prefix: str,
) -> JsonObject:
    prepared = prepare_asset_upload(
        source_file=source_file,
        markdown_file=markdown_file,
        content_list_file=content_list_file,
        asset_name=asset_name,
        asset_subfolder=asset_subfolder,
        temp_prefix=temp_prefix,
        normalize=asset_service.normalize_asset_name,
    )
    return workflows.submit_asset_init_task(
        task_manager,
        command=AssetInitCommand(
            asset_name=prepared.asset_name,
            source_path=prepared.source_path,
            rendered_pdf_path=prepared.rendered_pdf_path,
            content_list_path=prepared.content_list_path,
        ),
        cleanup_dir=prepared.cleanup_dir,
    )


def submit_bug_finder_upload_task(
    *,
    task_manager: TaskManager,
    asset_name: str,
    group_idx: int,
    tutor_idx: int,
    manuscript_files: list[UploadFile],
    temp_prefix: str,
) -> JsonObject:
    staged = stage_upload_batch(
        uploads=manuscript_files,
        temp_prefix=temp_prefix,
        fallback_name_for_index=lambda index: f"manuscript_{index}.png",
    )
    try:
        normalized_asset_name = parse_asset_name(asset_name, normalize=asset_service.normalize_asset_name)
        return workflows.submit_bug_finder_task(
            task_manager,
            asset_name=normalized_asset_name,
            group_idx=group_idx,
            tutor_idx=tutor_idx,
            manuscript_files=staged.file_paths,
            cleanup_dir=staged.cleanup_dir,
        )
    except Exception:
        cleanup_upload(staged.cleanup_dir)
        raise


__all__ = [
    "submit_asset_init_upload_task",
    "submit_bug_finder_upload_task",
]
