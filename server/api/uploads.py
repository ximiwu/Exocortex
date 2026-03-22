from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import UploadFile


@dataclass(frozen=True)
class PreparedAssetUpload:
    source_path: Path
    asset_name: str
    cleanup_dir: Path
    rendered_pdf_path: Path | None = None


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
    asset_name: str,
    asset_subfolder: str | None,
    skip_img2md_markdown_file: UploadFile | None,
    temp_prefix: str,
    normalize: Callable[[str], str],
) -> PreparedAssetUpload:
    cleanup_dir = Path(tempfile.mkdtemp(prefix=temp_prefix))
    try:
        source_path = copy_upload(source_file, cleanup_dir, fallback_name="source.pdf")
        rendered_pdf_path: Path | None = None
        if skip_img2md_markdown_file is not None:
            rendered_pdf_path = source_path
            source_path = copy_upload(skip_img2md_markdown_file, cleanup_dir, fallback_name="skip.md")
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
