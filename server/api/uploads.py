from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import UploadFile
from server.errors import ApiError


@dataclass(frozen=True)
class PreparedAssetUpload:
    source_path: Path
    asset_name: str
    cleanup_dir: Path
    rendered_pdf_path: Path | None = None
    content_list_path: Path | None = None


@dataclass(frozen=True)
class PreparedUploadBatch:
    file_paths: list[Path]
    cleanup_dir: Path


def copy_upload(upload: UploadFile, target_dir: Path, *, fallback_name: str) -> Path:
    name = Path(upload.filename or fallback_name).name
    suffix = Path(name).suffix or Path(fallback_name).suffix
    target = target_dir / f"{Path(name).stem}{suffix}"
    with target.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)
    return target


def require_upload_suffix(upload: UploadFile, suffix: str, *, code: str, label: str) -> None:
    filename = upload.filename or ""
    if Path(filename).suffix.lower() != suffix.lower():
        raise ApiError(400, code, f"{label} must be a {suffix} file.")


def validate_json_upload(path: Path) -> None:
    try:
        json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        raise ApiError(400, "invalid_content_list_json", "content list file must contain valid JSON.") from exc


def resolve_asset_name(
    asset_name: str,
    asset_subfolder: str | None,
    *,
    normalize: Callable[[str], str],
) -> str:
    resolved = normalize(asset_name)
    if not asset_subfolder or not asset_subfolder.strip():
        return resolved
    parent = normalize(asset_subfolder)
    return normalize(f"{parent}/{resolved}")


def parse_asset_name(
    asset_name: str,
    *,
    normalize: Callable[[str], str],
    asset_subfolder: str | None = None,
) -> str:
    return resolve_asset_name(asset_name, asset_subfolder, normalize=normalize)


def prepare_asset_upload(
    *,
    source_file: UploadFile,
    markdown_file: UploadFile,
    content_list_file: UploadFile,
    asset_name: str,
    asset_subfolder: str | None,
    temp_prefix: str,
    normalize: Callable[[str], str],
) -> PreparedAssetUpload:
    cleanup_dir = Path(tempfile.mkdtemp(prefix=temp_prefix))
    try:
        require_upload_suffix(source_file, ".pdf", code="invalid_source_upload", label="source file")
        require_upload_suffix(markdown_file, ".md", code="invalid_markdown_upload", label="markdown file")
        require_upload_suffix(content_list_file, ".json", code="invalid_content_list_upload", label="content list file")
        rendered_pdf_path = copy_upload(source_file, cleanup_dir, fallback_name="source.pdf")
        source_path = copy_upload(markdown_file, cleanup_dir, fallback_name="source.md")
        content_list_path = copy_upload(content_list_file, cleanup_dir, fallback_name="content_list.json")
        validate_json_upload(content_list_path)
        resolved_asset_name = parse_asset_name(
            asset_name,
            normalize=normalize,
            asset_subfolder=asset_subfolder,
        )
        return PreparedAssetUpload(
            source_path=source_path,
            asset_name=resolved_asset_name,
            cleanup_dir=cleanup_dir,
            rendered_pdf_path=rendered_pdf_path,
            content_list_path=content_list_path,
        )
    except Exception:
        shutil.rmtree(cleanup_dir, ignore_errors=True)
        raise


def stage_upload_batch(
    *,
    uploads: list[UploadFile],
    temp_prefix: str,
    fallback_name_for_index: Callable[[int], str],
) -> PreparedUploadBatch:
    cleanup_dir = Path(tempfile.mkdtemp(prefix=temp_prefix))
    try:
        file_paths = [
            copy_upload(upload, cleanup_dir, fallback_name=fallback_name_for_index(index))
            for index, upload in enumerate(uploads, start=1)
        ]
        return PreparedUploadBatch(file_paths=file_paths, cleanup_dir=cleanup_dir)
    except Exception:
        cleanup_upload(cleanup_dir)
        raise


def cleanup_upload(path: Path | None) -> None:
    if path is None:
        return
    shutil.rmtree(path, ignore_errors=True)


__all__ = [
    "PreparedAssetUpload",
    "PreparedUploadBatch",
    "cleanup_upload",
    "copy_upload",
    "parse_asset_name",
    "prepare_asset_upload",
    "resolve_asset_name",
    "stage_upload_batch",
]
