from __future__ import annotations

import os
from pathlib import Path

import pytest

from exocortex_core import fs as fs_utils


def test_atomic_write_text_retries_transient_replace_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "config.json"
    original_replace = os.replace
    call_count = 0

    def _flaky_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise PermissionError(32, "sharing violation", os.fspath(dst))
        original_replace(src, dst)

    monkeypatch.setattr(fs_utils.os, "replace", _flaky_replace)
    monkeypatch.setattr(fs_utils.time, "sleep", lambda _seconds: None)

    written_path = fs_utils.atomic_write_text(target, '{"ok": true}', retry_delays=(0.0,))

    assert written_path == target
    assert target.read_text(encoding="utf-8") == '{"ok": true}'
    assert call_count == 2
    assert [path.name for path in tmp_path.iterdir()] == ["config.json"]
