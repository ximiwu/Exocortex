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


def test_load_ui_state_normalizes_lists_and_scroll_maps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        asset_service,
        "get_asset_config",
        lambda _asset_name: {
            "open_markdown_paths": ["notes.md", "", "notes.md", "summary.md", 3],
            "sidebar_collapsed_node_ids": ["group:1", "", "group:1", None, "group:2"],
            "markdown_scroll_fractions": {
                "notes.md": 1.25,
                "summary.md": "0.4",
                "": 0.3,
                "broken.md": "bad",
            },
        },
    )

    ui_state = asset_service._load_ui_state("physics/ch1", page_count=4)

    assert ui_state.openMarkdownPaths == ["notes.md", "summary.md"]
    assert ui_state.sidebarCollapsedNodeIds == ["group:1", "group:2"]
    assert ui_state.markdownScrollFractions == {
        "notes.md": 1.0,
        "summary.md": 0.4,
    }


def test_update_ui_state_normalizes_lists_and_scroll_maps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    saved: dict[str, object] = {}

    monkeypatch.setattr(asset_service, "resolve_asset_dir", lambda _asset_name, *, must_exist=True: tmp_path)
    monkeypatch.setattr(asset_service, "get_asset_config", lambda _asset_name: {})

    def _save_asset_config(_asset_name: str, data: dict[str, object]) -> Path:
        saved.clear()
        saved.update(data)
        return tmp_path / "config.json"

    monkeypatch.setattr(asset_service, "save_asset_config", _save_asset_config)
    monkeypatch.setattr(asset_service, "build_asset_state", lambda _asset_name: {"ui_state": dict(saved)})

    asset_service.update_ui_state(
        "physics/ch1",
        open_markdown_paths=["notes.md", "", "notes.md", "summary.md"],
        sidebar_collapsed_node_ids=["group:1", "", "group:1", "group:2"],
        markdown_scroll_fractions={
            "notes.md": 1.25,
            "summary.md": "0.4",
            "": 0.3,
            "broken.md": "bad",
        },
    )

    assert saved["open_markdown_paths"] == ["notes.md", "summary.md"]
    assert saved["sidebar_collapsed_node_ids"] == ["group:1", "group:2"]
    assert saved["markdown_scroll_fractions"] == {
        "notes.md": 1.0,
        "summary.md": 0.4,
    }


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


@pytest.mark.parametrize(
    ("markdown_content", "expected_alias"),
    [
        ("# Heading\n\nBody", "Heading"),
        ("###   Heading", "Heading"),
        ("＃＃　中文标题", "中文标题"),
        ("## Title  with  kept spaces", "Title  with  kept spaces"),
        ("Plain title", "Plain title"),
        ("##", ""),
        ("", ""),
        ("#  keep inner  spaces", "keep inner  spaces"),
    ],
)
def test_extract_group_alias_from_markdown(
    markdown_content: str,
    expected_alias: str,
) -> None:
    assert asset_service._extract_group_alias_from_markdown(markdown_content) == expected_alias


def test_merge_group_writes_group_alias_from_markdown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset"
    group_dir = asset_dir / "group_data" / "7"
    saved_block_data: dict[str, object] = {}

    monkeypatch.setattr(asset_service, "_normalize_asset_name", lambda asset_name: asset_name)
    monkeypatch.setattr(asset_service, "resolve_asset_dir", lambda _asset_name, *, must_exist=True: asset_dir)
    monkeypatch.setattr(asset_service, "get_asset_pdf_path", lambda _asset_name: asset_dir / "raw.pdf")
    monkeypatch.setattr(
        asset_service,
        "_load_fraction_block_data",
        lambda _asset_name, _pdf_path: asset_service.BlockData(
            blocks=[
                asset_service.BlockRecord(
                    block_id=3,
                    page_index=0,
                    rect=asset_service.BlockRect(x=0.1, y=0.2, width=0.3, height=0.4),
                    group_idx=None,
                )
            ],
            merge_order=[],
            next_block_id=4,
            coordinate_space=asset_service.COORDINATE_SPACE_PAGE_FRACTION,
        ),
    )
    monkeypatch.setattr(
        asset_service,
        "create_group_record",
        lambda _asset_name, block_ids, group_idx=None: type(
            "GroupRecordStub",
            (),
            {"group_idx": 7, "block_ids": list(block_ids)},
        )(),
    )
    monkeypatch.setattr(
        asset_service,
        "save_block_data",
        lambda _asset_name, data: saved_block_data.update(
            {
                "merge_order": list(data.merge_order),
                "group_idxs": [block.group_idx for block in data.blocks],
            }
        ),
    )
    monkeypatch.setattr(asset_service, "build_asset_state", lambda _asset_name: {"ok": True})

    result = asset_service.merge_group("physics/ch1", block_ids=[3], markdown_content="##   Merged Title\n\nBody")

    assert result == {"ok": True}
    assert saved_block_data == {"merge_order": [], "group_idxs": [7]}
    assert (group_dir / "content.md").read_text(encoding="utf-8") == "##   Merged Title\n\nBody"
    assert (group_dir / "group.alias").read_text(encoding="utf-8") == "Merged Title"


def test_merge_group_removes_group_alias_when_markdown_heading_is_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset"
    group_dir = asset_dir / "group_data" / "5"
    group_dir.mkdir(parents=True, exist_ok=True)
    (group_dir / "group.alias").write_text("Old alias", encoding="utf-8")

    monkeypatch.setattr(asset_service, "_normalize_asset_name", lambda asset_name: asset_name)
    monkeypatch.setattr(asset_service, "resolve_asset_dir", lambda _asset_name, *, must_exist=True: asset_dir)
    monkeypatch.setattr(asset_service, "get_asset_pdf_path", lambda _asset_name: asset_dir / "raw.pdf")
    monkeypatch.setattr(
        asset_service,
        "_load_fraction_block_data",
        lambda _asset_name, _pdf_path: asset_service.BlockData(
            blocks=[
                asset_service.BlockRecord(
                    block_id=9,
                    page_index=0,
                    rect=asset_service.BlockRect(x=0.0, y=0.0, width=0.1, height=0.1),
                    group_idx=None,
                )
            ],
            merge_order=[],
            next_block_id=10,
            coordinate_space=asset_service.COORDINATE_SPACE_PAGE_FRACTION,
        ),
    )
    monkeypatch.setattr(
        asset_service,
        "create_group_record",
        lambda _asset_name, block_ids, group_idx=None: type(
            "GroupRecordStub",
            (),
            {"group_idx": 5, "block_ids": list(block_ids)},
        )(),
    )
    monkeypatch.setattr(asset_service, "save_block_data", lambda _asset_name, data: data)
    monkeypatch.setattr(asset_service, "build_asset_state", lambda _asset_name: {"ok": True})

    asset_service.merge_group("physics/ch1", block_ids=[9], markdown_content="###   \n\nBody")

    assert not (group_dir / "group.alias").exists()
