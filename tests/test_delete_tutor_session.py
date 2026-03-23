from __future__ import annotations

from pathlib import Path

import pytest

from server.errors import ApiError
from server.services import assets as asset_service


def test_delete_tutor_session_removes_only_targeted_folder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-a"
    target_dir = asset_dir / "group_data" / "1" / "tutor_data" / "2"
    untouched_dir = asset_dir / "group_data" / "1" / "tutor_data" / "3"
    target_dir.mkdir(parents=True, exist_ok=True)
    untouched_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "focus.md").write_text("# focus", encoding="utf-8")
    (untouched_dir / "focus.md").write_text("# keep", encoding="utf-8")

    def _resolve_asset_dir(_asset_name: str, *, must_exist: bool = True) -> Path:
        return asset_dir

    monkeypatch.setattr(asset_service, "resolve_asset_dir", _resolve_asset_dir)

    asset_service.delete_tutor_session("asset-a", group_idx=1, tutor_idx=2)

    assert not target_dir.exists()
    assert untouched_dir.exists()


def test_delete_tutor_session_rejects_symlink_escape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-b"
    tutor_root = asset_dir / "group_data" / "7" / "tutor_data"
    tutor_root.mkdir(parents=True, exist_ok=True)
    outside_dir = tmp_path / "outside-session"
    outside_dir.mkdir(parents=True, exist_ok=True)
    (outside_dir / "focus.md").write_text("# outside", encoding="utf-8")
    escape_link = tutor_root / "9"

    try:
        escape_link.symlink_to(outside_dir, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("Symlinks are not available in this runtime.")

    def _resolve_asset_dir(_asset_name: str, *, must_exist: bool = True) -> Path:
        return asset_dir

    monkeypatch.setattr(asset_service, "resolve_asset_dir", _resolve_asset_dir)

    with pytest.raises(ApiError) as excinfo:
        asset_service.delete_tutor_session("asset-b", group_idx=7, tutor_idx=9)

    assert excinfo.value.code == "invalid_tutor_session_path"
    assert outside_dir.exists()
