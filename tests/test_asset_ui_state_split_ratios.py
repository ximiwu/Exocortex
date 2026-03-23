from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from server.services import assets as asset_service


def test_load_ui_state_reads_split_ratios_from_asset_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        asset_service,
        "get_asset_config",
        lambda _asset_name: {
            "sidebar_width_ratio": 0.22,
            "right_rail_width_ratio": 0.41,
        },
    )

    ui_state = asset_service._load_ui_state("physics/ch1", page_count=4)

    assert ui_state.sidebarWidthRatio == 0.22
    assert ui_state.rightRailWidthRatio == 0.41


def test_update_ui_state_persists_split_ratios_as_snake_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: dict[str, object] = {}

    def _resolve_asset_dir(_asset_name: str, *, must_exist: bool = True) -> Path:
        return tmp_path

    def _save_asset_config(_asset_name: str, data: dict[str, object]) -> Path:
        saved.update(data)
        return tmp_path / "config.json"

    monkeypatch.setattr(asset_service, "resolve_asset_dir", _resolve_asset_dir)
    monkeypatch.setattr(asset_service, "get_asset_config", lambda _asset_name: {})
    monkeypatch.setattr(asset_service, "save_asset_config", _save_asset_config)
    monkeypatch.setattr(asset_service, "build_asset_state", lambda _asset_name: {"ok": True})

    result = asset_service.update_ui_state(
        "physics/ch1",
        sidebar_width_ratio=1.25,
        right_rail_width_ratio=-0.2,
    )

    assert result == {"ok": True}
    assert saved["sidebar_width_ratio"] == 1.0
    assert saved["right_rail_width_ratio"] == 0.0


def test_update_ui_state_serializes_overlapping_asset_config_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored_config: dict[str, object] = {}
    first_save_started = threading.Event()
    allow_first_save = threading.Event()
    failures: list[BaseException] = []

    def _resolve_asset_dir(_asset_name: str, *, must_exist: bool = True) -> Path:
        return tmp_path

    def _get_asset_config(_asset_name: str) -> dict[str, object]:
        return dict(stored_config)

    def _save_asset_config(_asset_name: str, data: dict[str, object]) -> Path:
        if data.get("current_page") == 5 and not first_save_started.is_set():
            first_save_started.set()
            assert allow_first_save.wait(timeout=2)
        stored_config.clear()
        stored_config.update(data)
        return tmp_path / "config.json"

    monkeypatch.setattr(asset_service, "resolve_asset_dir", _resolve_asset_dir)
    monkeypatch.setattr(asset_service, "get_asset_config", _get_asset_config)
    monkeypatch.setattr(asset_service, "save_asset_config", _save_asset_config)
    monkeypatch.setattr(asset_service, "build_asset_state", lambda _asset_name: {"ui_state": dict(stored_config)})

    def _run_update(*, current_page: int | None = None, sidebar_collapsed: bool | None = None) -> None:
        try:
            asset_service.update_ui_state(
                "physics/ch1",
                current_page=current_page,
                sidebar_collapsed=sidebar_collapsed,
            )
        except BaseException as exc:  # pragma: no cover - failure collection
            failures.append(exc)

    first = threading.Thread(target=_run_update, kwargs={"current_page": 5})
    second = threading.Thread(target=_run_update, kwargs={"sidebar_collapsed": True})

    first.start()
    assert first_save_started.wait(timeout=1)

    second.start()
    time.sleep(0.05)
    allow_first_save.set()

    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert failures == []
    assert stored_config["current_page"] == 5
    assert stored_config["sidebar_collapsed"] is True
