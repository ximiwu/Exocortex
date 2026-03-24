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


def test_build_asset_state_reads_disabled_content_item_indexes_from_asset_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(asset_service, "resolve_asset_dir", lambda _asset_name, *, must_exist=True: tmp_path)
    monkeypatch.setattr(asset_service, "get_asset_pdf_path", lambda _asset_name: tmp_path / "raw.pdf")
    monkeypatch.setattr(asset_service, "ensure_content_list_unified", lambda _asset_name: None)
    monkeypatch.setattr(asset_service, "_load_page_sizes_at_reference_dpi", lambda _pdf_path: [])
    monkeypatch.setattr(asset_service, "_load_fraction_block_data", lambda _asset_name, _pdf_path: asset_service.BlockData.empty())
    monkeypatch.setattr(asset_service, "load_group_records", lambda _asset_name: [])
    monkeypatch.setattr(asset_service, "_list_reference_names", lambda _asset_name: [])
    monkeypatch.setattr(asset_service, "relative_to_assets_root", lambda path: str(path))
    monkeypatch.setattr(
        asset_service,
        "get_asset_config",
        lambda _asset_name: {
            "disabled_content_item_indexes": [5, "2", 5, 0, -1, True, "bad"],
        },
    )

    result = asset_service.build_asset_state("physics/ch1")

    assert result.disabledContentItemIndexes == [2, 5]


def test_update_disabled_content_items_persists_sorted_unique_indexes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: dict[str, object] = {}

    monkeypatch.setattr(asset_service, "resolve_asset_dir", lambda _asset_name, *, must_exist=True: tmp_path)
    monkeypatch.setattr(asset_service, "get_asset_config", lambda _asset_name: {})

    def _save_asset_config(_asset_name: str, data: dict[str, object]) -> Path:
        saved.update(data)
        return tmp_path / "config.json"

    monkeypatch.setattr(asset_service, "save_asset_config", _save_asset_config)
    monkeypatch.setattr(
        asset_service,
        "build_asset_state",
        lambda _asset_name: {"disabledContentItemIndexes": saved.get("disabled_content_item_indexes", [])},
    )

    result = asset_service.update_disabled_content_items("physics/ch1", [4, 2, 4, 0, -1, True, 3])

    assert result == {"disabledContentItemIndexes": [2, 3, 4]}
    assert saved["disabled_content_item_indexes"] == [2, 3, 4]
