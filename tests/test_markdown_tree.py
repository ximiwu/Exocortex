from __future__ import annotations

from pathlib import Path

import pytest

from server.services import markdown as markdown_service


def _write_markdown(path: Path, content: str = "# test\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _find_node_by_id(nodes: list[object], node_id: str):
    for node in nodes:
        if node.id == node_id:
            return node
        child = _find_node_by_id(node.children, node_id)
        if child is not None:
            return child
    return None


def _collect_leaf_paths(node) -> list[str]:
    paths: list[str] = []
    if node.path:
        paths.append(node.path)
    for child in node.children:
        paths.extend(_collect_leaf_paths(child))
    return paths


def _collect_descendant_paths(node) -> list[str]:
    paths: list[str] = []
    for child in node.children:
        paths.extend(_collect_leaf_paths(child))
    return paths


def test_build_markdown_tree_separates_group_tutor_and_other_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset"
    group_dir = asset_dir / "group_data" / "1"
    tutor_dir = group_dir / "tutor_data" / "2"

    _write_markdown(group_dir / "img_explainer_data" / "enhanced.md")
    _write_markdown(group_dir / "notes.md")
    _write_markdown(group_dir / "sub_folder" / "chapter.md")
    _write_markdown(tutor_dir / "focus.md")
    _write_markdown(tutor_dir / "extra.md")
    _write_markdown(tutor_dir / "ask_history" / "q1.md")

    monkeypatch.setattr(markdown_service, "resolve_asset_dir", lambda _asset_name: asset_dir)
    monkeypatch.setattr(markdown_service, "get_asset_config", lambda _asset_name: {})

    nodes = markdown_service.build_markdown_tree("physics/ch1")

    assert [node.id for node in nodes] == ["group:1"]

    group_node = nodes[0]
    assert group_node.kind == "group"
    assert group_node.path == "group_data/1/img_explainer_data/enhanced.md"
    assert [child.id for child in group_node.children] == ["tutor:1:2:focus", "group:1:other"]

    tutor_node = _find_node_by_id(nodes, "tutor:1:2:focus")
    assert tutor_node is not None
    assert tutor_node.kind == "tutor"
    assert tutor_node.path == "group_data/1/tutor_data/2/focus.md"
    assert [child.kind for child in tutor_node.children] == ["markdown", "ask"]
    assert [child.path for child in tutor_node.children] == [
        "group_data/1/tutor_data/2/extra.md",
        "group_data/1/tutor_data/2/ask_history/q1.md",
    ]
    assert tutor_node.path not in _collect_descendant_paths(tutor_node)

    other_node = _find_node_by_id(nodes, "group:1:other")
    assert other_node is not None
    assert other_node.kind == "folder"
    assert other_node.title == "Other"
    assert [child.id for child in other_node.children] == [
        "group:1:other/sub_folder",
        "group:1:other:notes.md",
    ]
    assert group_node.path not in _collect_descendant_paths(other_node)

    sub_folder_node = _find_node_by_id(nodes, "group:1:other/sub_folder")
    assert sub_folder_node is not None
    assert sub_folder_node.kind == "folder"
    assert [child.path for child in sub_folder_node.children] == ["group_data/1/sub_folder/chapter.md"]
