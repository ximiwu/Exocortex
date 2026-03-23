from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile

from server.api import uploads


def _make_upload(filename: str, content: bytes) -> UploadFile:
    return UploadFile(file=BytesIO(content), filename=filename)


def _normalize(value: str) -> str:
    return value.strip().replace("\\", "/").strip("/")


def test_parse_asset_name_with_subfolder() -> None:
    resolved = uploads.parse_asset_name(
        "  chapter-1  ",
        normalize=_normalize,
        asset_subfolder="  physics  ",
    )
    assert resolved == "physics/chapter-1"


def test_prepare_asset_upload_with_pdf_markdown_and_content_list() -> None:
    prepared = uploads.prepare_asset_upload(
        source_file=_make_upload("../paper.pdf", b"pdf-bytes"),
        markdown_file=_make_upload("../notes.md", b"# notes"),
        content_list_file=_make_upload("content_list.json", b'{"items": []}'),
        asset_name="  chapter-1  ",
        asset_subfolder="  physics  ",
        temp_prefix="pytest-upload-",
        normalize=_normalize,
    )
    try:
        assert prepared.asset_name == "physics/chapter-1"
        assert prepared.source_path.name == "notes.md"
        assert prepared.source_path.read_bytes() == b"# notes"
        assert prepared.rendered_pdf_path is not None
        assert prepared.rendered_pdf_path.name == "paper.pdf"
        assert prepared.rendered_pdf_path.read_bytes() == b"pdf-bytes"
        assert prepared.content_list_path is not None
        assert prepared.content_list_path.name == "content_list.json"
        assert prepared.content_list_path.read_bytes() == b'{"items": []}'
        assert prepared.cleanup_dir.exists()
    finally:
        uploads.cleanup_upload(prepared.cleanup_dir)
    assert not prepared.cleanup_dir.exists()


def test_prepare_asset_upload_rejects_invalid_json() -> None:
    with pytest.raises(Exception, match="content list file must contain valid JSON"):
        uploads.prepare_asset_upload(
            source_file=_make_upload("source.pdf", b"%PDF"),
            markdown_file=_make_upload("source.md", b"# markdown"),
            content_list_file=_make_upload("content_list.json", b"{not json"),
            asset_name="asset-a",
            asset_subfolder=None,
            temp_prefix="pytest-upload-",
            normalize=_normalize,
        )


def test_prepare_asset_upload_rejects_non_pdf_source() -> None:
    with pytest.raises(Exception, match="source file must be a .pdf file"):
        uploads.prepare_asset_upload(
            source_file=_make_upload("source.txt", b"not a pdf"),
            markdown_file=_make_upload("source.md", b"# markdown"),
            content_list_file=_make_upload("content_list.json", b'{"items": []}'),
            asset_name="asset-a",
            asset_subfolder=None,
            temp_prefix="pytest-upload-",
            normalize=_normalize,
        )


def test_prepare_asset_upload_cleans_temp_dir_when_copy_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    original_copy_upload = uploads.copy_upload
    seen_dirs: list[Path] = []
    call_count = 0

    def _copy_with_failure(upload: UploadFile, target_dir: Path, *, fallback_name: str) -> Path:
        nonlocal call_count
        call_count += 1
        seen_dirs.append(target_dir)
        if call_count == 2:
            raise RuntimeError("forced failure while writing content list file")
        return original_copy_upload(upload, target_dir, fallback_name=fallback_name)

    monkeypatch.setattr(uploads, "copy_upload", _copy_with_failure)

    with pytest.raises(RuntimeError):
        uploads.prepare_asset_upload(
            source_file=_make_upload("source.pdf", b"%PDF"),
            markdown_file=_make_upload("source.md", b"# markdown"),
            content_list_file=_make_upload("content_list.json", b'{"items": []}'),
            asset_name="asset-a",
            asset_subfolder="sub",
            temp_prefix="pytest-upload-",
            normalize=_normalize,
        )

    assert seen_dirs, "prepare_asset_upload should create a temp directory before copy"
    assert not seen_dirs[0].exists(), "temp upload directory should be cleaned on failure"


def test_stage_upload_batch_success() -> None:
    staged = uploads.stage_upload_batch(
        uploads=[
            _make_upload("first.png", b"first"),
            _make_upload("second.png", b"second"),
        ],
        temp_prefix="pytest-upload-batch-",
        fallback_name_for_index=lambda index: f"manuscript_{index}.png",
    )
    try:
        assert [path.name for path in staged.file_paths] == ["first.png", "second.png"]
        assert [path.read_bytes() for path in staged.file_paths] == [b"first", b"second"]
    finally:
        uploads.cleanup_upload(staged.cleanup_dir)


def test_stage_upload_batch_cleans_temp_dir_when_copy_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    original_copy_upload = uploads.copy_upload
    seen_dirs: list[Path] = []
    call_count = 0

    def _copy_with_failure(upload: UploadFile, target_dir: Path, *, fallback_name: str) -> Path:
        nonlocal call_count
        call_count += 1
        seen_dirs.append(target_dir)
        if call_count == 2:
            raise RuntimeError("forced failure while writing staged upload")
        return original_copy_upload(upload, target_dir, fallback_name=fallback_name)

    monkeypatch.setattr(uploads, "copy_upload", _copy_with_failure)

    with pytest.raises(RuntimeError):
        uploads.stage_upload_batch(
            uploads=[
                _make_upload("first.png", b"first"),
                _make_upload("second.png", b"second"),
            ],
            temp_prefix="pytest-upload-batch-",
            fallback_name_for_index=lambda index: f"manuscript_{index}.png",
        )

    assert seen_dirs, "stage_upload_batch should create a temp directory before copy"
    assert not seen_dirs[0].exists(), "temp upload directory should be cleaned on failure"
