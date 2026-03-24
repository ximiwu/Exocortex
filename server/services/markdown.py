from __future__ import annotations

import re
from pathlib import Path

from exocortex_core.fs import atomic_write_text
try:
    import markdown as py_markdown
except ImportError:  # pragma: no cover - dependency guard
    py_markdown = None

try:
    import pymdownx.arithmatex  # type: ignore  # noqa: F401

    _ARITHMATEX_AVAILABLE = True
except ImportError:  # pragma: no cover - dependency guard
    _ARITHMATEX_AVAILABLE = False

from exocortex_core.markdown_web import (
    katex_assets,
    normalize_details_markdown,
    normalize_math_content,
    normalize_paragraph_list_separation,
)
from exocortex_core.text import read_text_auto
from server.domain.assets import asset_config_write_lock, get_asset_config, save_asset_config
from server.errors import ApiError
from server.schemas import MarkdownContentModel, MarkdownTreeNodeModel

from .assets import resolve_asset_dir, resolve_relative_file


_ALIAS_SUFFIX = ".alias"
_ROOT_PARENT_ID = "__root__"


def _markdown_alias_path(path: Path) -> Path:
    return path.with_name(path.name + _ALIAS_SUFFIX)


def _read_alias(path: Path) -> str | None:
    try:
        text = read_text_auto(path).strip()
    except Exception:
        return None
    return text or None


def _display_title(path: Path, fallback: str) -> str:
    alias = _read_alias(_markdown_alias_path(path))
    return alias or fallback


def _group_title(group_dir: Path, group_idx: int) -> str:
    alias = _read_alias(group_dir / "group.alias")
    return alias or f"Group {group_idx}"


def _atomic_write_text(path: Path, value: str) -> None:
    atomic_write_text(path, value, newline="\n")


def _write_alias(path: Path, alias: str, fallback: str) -> str:
    cleaned = alias.strip()
    if not cleaned or cleaned == fallback:
        path.unlink(missing_ok=True)
        return fallback
    _atomic_write_text(path, cleaned)
    return cleaned


def _normalize_parent_storage_key(parent_id: str | None) -> str:
    return parent_id or _ROOT_PARENT_ID


def _load_sidebar_order(asset_name: str) -> dict[str, list[str]]:
    config = get_asset_config(asset_name)
    raw = config.get("sidebar_order")
    if not isinstance(raw, dict):
        return {}
    result: dict[str, list[str]] = {}
    for key, value in raw.items():
        if not isinstance(key, str) or not isinstance(value, list):
            continue
        normalized: list[str] = []
        for item in value:
            if isinstance(item, str) and item and item not in normalized:
                normalized.append(item)
        result[key] = normalized
    return result


def _save_sidebar_order(asset_name: str, sidebar_order: dict[str, list[str]]) -> None:
    with asset_config_write_lock(asset_name):
        config = get_asset_config(asset_name)
        config["sidebar_order"] = sidebar_order
        save_asset_config(asset_name, config)


def _apply_saved_order(
    children: list[MarkdownTreeNodeModel],
    parent_id: str | None,
    saved_order: dict[str, list[str]],
) -> list[MarkdownTreeNodeModel]:
    if not children:
        return children

    ordered_ids = saved_order.get(_normalize_parent_storage_key(parent_id), [])
    if not ordered_ids:
        return children

    child_by_id = {child.id: child for child in children}
    result: list[MarkdownTreeNodeModel] = []
    seen: set[str] = set()

    for child_id in ordered_ids:
        child = child_by_id.get(child_id)
        if child is None or child_id in seen:
            continue
        seen.add(child_id)
        result.append(child)

    for child in children:
        if child.id in seen:
            continue
        result.append(child)

    return result


def _walk_tree(
    nodes: list[MarkdownTreeNodeModel],
    *,
    parent_id: str | None = None,
) -> list[tuple[MarkdownTreeNodeModel, str | None]]:
    result: list[tuple[MarkdownTreeNodeModel, str | None]] = []
    for node in nodes:
        result.append((node, parent_id))
        if node.children:
            result.extend(_walk_tree(node.children, parent_id=node.id))
    return result


def _find_tree_node(
    nodes: list[MarkdownTreeNodeModel],
    node_id: str,
) -> tuple[MarkdownTreeNodeModel, str | None] | None:
    for node, parent_id in _walk_tree(nodes):
        if node.id == node_id:
            return node, parent_id
    return None


def _render_markdown_body(content: str) -> tuple[str, str]:
    if py_markdown is None:
        raise ApiError(500, "markdown_unavailable", "Missing 'markdown' package.")
    if not _ARITHMATEX_AVAILABLE:
        raise ApiError(500, "markdown_unavailable", "Missing 'pymdown-extensions' package.")

    normalized = normalize_math_content(content.lstrip("\ufeff"))
    normalized = normalize_details_markdown(normalized)
    normalized = normalize_paragraph_list_separation(normalized)

    extensions = ["extra", "sane_lists", "fenced_code", "tables", "pymdownx.arithmatex"]
    extension_configs = {"pymdownx.arithmatex": {"generic": True}}
    renderer = py_markdown.Markdown(extensions=extensions, extension_configs=extension_configs)
    block_elements = renderer.block_level_elements
    if isinstance(block_elements, set):
        block_elements.update({"details", "summary"})
    else:
        for tag in ("details", "summary"):
            if tag not in block_elements:
                block_elements.append(tag)
    body = renderer.convert(normalized)
    return normalized, body


def _render_markdown_document(content: str) -> tuple[str, str, str, str]:
    normalized, body = _render_markdown_body(content)
    assets = katex_assets(asset_root="/vendor/katex")
    styles = (
        "body { font-family: 'Times New Roman','Segoe UI',sans-serif; font-size: 16px; "
        "line-height: 1.6; color: #333; padding: 16px; background: #fff; } "
        "img { max-width: 100%; } pre { overflow-x: auto; } "
        "details.note-container { background-color: #fff9e6; border-left: 5px solid #e6c200; "
        "margin: 15px 0; padding: 12px 16px; border-radius: 0 4px 4px 0; } "
        "details.note-container summary { font-weight: 700; color: #b38600; cursor: pointer; }"
    )
    head_html = f"<meta charset='UTF-8'><style>{styles}</style>{assets}"
    full_html = f"<!DOCTYPE html><html><head>{head_html}</head><body>{body}</body></html>"
    return normalized, full_html, body, head_html


def _markdown_leaf(asset_dir: Path, path: Path, *, node_id: str, title: str, kind: str = "markdown") -> MarkdownTreeNodeModel:
    return MarkdownTreeNodeModel(
        id=node_id,
        kind=kind,
        title=title,
        path=path.relative_to(asset_dir).as_posix(),
        children=[],
    )


def _entry_sort_key(path: Path) -> tuple[int, int, int, str]:
    raw_name = path.name if path.is_dir() else path.stem
    numeric_value = -1
    numeric_rank = 1
    if re.fullmatch(r"\d+", raw_name):
        numeric_rank = 0
        numeric_value = int(raw_name)

    return (0 if path.is_dir() else 1, numeric_rank, numeric_value, path.name.lower())


def _markdown_kind_for_path(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    if "ask_history" in parts:
        return "ask"
    return "markdown"


def _build_markdown_children(
    asset_dir: Path,
    directory: Path,
    *,
    node_id: str,
    saved_order: dict[str, list[str]] | None = None,
    leaf_kind: str = "markdown",
    excluded_dir_names: set[str] | None = None,
) -> list[MarkdownTreeNodeModel]:
    saved_order = saved_order or {}
    excluded_dir_names = excluded_dir_names or set()
    children: list[MarkdownTreeNodeModel] = []
    for entry in sorted(directory.iterdir(), key=_entry_sort_key):
        if entry.name.endswith(_ALIAS_SUFFIX):
            continue
        if entry.is_dir():
            if entry.name in excluded_dir_names:
                continue
            child = _build_recursive_markdown_folder(
                asset_dir,
                entry,
                node_id=f"{node_id}/{entry.name}",
                title=entry.name.replace("_", " "),
                saved_order=saved_order,
                kind="folder",
                leaf_kind=leaf_kind,
                excluded_dir_names=excluded_dir_names,
            )
            if child is not None and child.children:
                children.append(child)
        elif entry.suffix.lower() == ".md":
            children.append(
                _markdown_leaf(
                    asset_dir,
                    entry,
                    node_id=f"{node_id}:{entry.name}",
                    title=_display_title(entry, entry.name),
                    kind=_markdown_kind_for_path(entry) if leaf_kind == "markdown" else leaf_kind,
                )
            )
    return children


def _collect_folder_children(
    asset_dir: Path,
    directory: Path,
    *,
    node_id: str,
    saved_order: dict[str, list[str]] | None = None,
    excluded_dir_names: set[str] | None = None,
) -> list[MarkdownTreeNodeModel]:
    saved_order = saved_order or {}
    children = _build_markdown_children(
        asset_dir,
        directory,
        node_id=node_id,
        saved_order=saved_order,
        excluded_dir_names=excluded_dir_names,
    )
    return _apply_saved_order(children, node_id, saved_order)


def _build_recursive_markdown_folder(
    asset_dir: Path,
    directory: Path,
    *,
    node_id: str,
    title: str,
    saved_order: dict[str, list[str]] | None = None,
    kind: str = "folder",
    leaf_kind: str = "markdown",
    excluded_dir_names: set[str] | None = None,
) -> MarkdownTreeNodeModel | None:
    saved_order = saved_order or {}
    children = _build_markdown_children(
        asset_dir,
        directory,
        node_id=node_id,
        saved_order=saved_order,
        leaf_kind=leaf_kind,
        excluded_dir_names=excluded_dir_names,
    )
    if not children:
        return None
    children = _apply_saved_order(children, node_id, saved_order)
    return MarkdownTreeNodeModel(id=node_id, kind=kind, title=title, path=None, children=children)


def _build_other_folder(
    children: list[MarkdownTreeNodeModel],
    *,
    node_id: str,
) -> MarkdownTreeNodeModel | None:
    if not children:
        return None
    return MarkdownTreeNodeModel(id=node_id, kind="folder", title="Other", path=None, children=children)


def _build_tutor_tree(
    asset_dir: Path,
    tutor_dir: Path,
    *,
    group_idx: int,
    tutor_idx: int,
    saved_order: dict[str, list[str]] | None = None,
) -> MarkdownTreeNodeModel | None:
    saved_order = saved_order or {}
    focus_path = tutor_dir / "focus.md"
    node_id = f"tutor:{group_idx}:{tutor_idx}:focus"
    path_value = focus_path.relative_to(asset_dir).as_posix() if focus_path.is_file() else None
    title = _display_title(focus_path, focus_path.name) if focus_path.is_file() else f"Tutor {tutor_idx}"

    children = _collect_folder_children(
        asset_dir,
        tutor_dir,
        node_id=node_id,
        saved_order=saved_order,
        excluded_dir_names={"ask_history"},
    )
    children = [child for child in children if child.path != path_value]

    ask_history_dir = tutor_dir / "ask_history"
    if ask_history_dir.is_dir():
        for entry in sorted(ask_history_dir.iterdir(), key=_entry_sort_key):
            if entry.name.endswith(_ALIAS_SUFFIX) or entry.suffix.lower() != ".md":
                continue
            children.append(
                _markdown_leaf(
                    asset_dir,
                    entry,
                    node_id=f"tutor:{group_idx}:{tutor_idx}:history:{entry.stem}",
                    title=_display_title(entry, entry.name),
                    kind="ask",
                )
            )

    if path_value is None and not children:
        return None

    children = _apply_saved_order(children, node_id, saved_order)
    return MarkdownTreeNodeModel(
        id=node_id,
        kind="tutor",
        title=title,
        path=path_value,
        children=children,
    )


def _build_group_tree(
    asset_dir: Path,
    group_dir: Path,
    *,
    group_idx: int,
    saved_order: dict[str, list[str]] | None = None,
) -> MarkdownTreeNodeModel | None:
    saved_order = saved_order or {}
    group_node_id = f"group:{group_idx}"
    enhanced_path = group_dir / "img_explainer_data" / "enhanced.md"
    path_value = enhanced_path.relative_to(asset_dir).as_posix() if enhanced_path.is_file() else None

    children: list[MarkdownTreeNodeModel] = []

    tutor_root = group_dir / "tutor_data"
    if tutor_root.is_dir():
        for tutor_dir in sorted(tutor_root.iterdir(), key=_entry_sort_key):
            if not tutor_dir.is_dir() or not tutor_dir.name.isdigit():
                continue
            tutor_node = _build_tutor_tree(
                asset_dir,
                tutor_dir,
                group_idx=group_idx,
                tutor_idx=int(tutor_dir.name),
                saved_order=saved_order,
            )
            if tutor_node is not None:
                children.append(tutor_node)

    other_children: list[MarkdownTreeNodeModel] = []
    other_children.extend(
        _collect_folder_children(
            asset_dir,
            group_dir,
            node_id=f"{group_node_id}:other",
            saved_order=saved_order,
            excluded_dir_names={"img_explainer_data", "tutor_data"},
        )
    )
    img_explainer_dir = group_dir / "img_explainer_data"
    if img_explainer_dir.is_dir():
        img_children = _collect_folder_children(
            asset_dir,
            img_explainer_dir,
            node_id=f"{group_node_id}:other/img_explainer_data",
            saved_order=saved_order,
        )
        other_children.extend([child for child in img_children if child.path != path_value])

    other_folder = _build_other_folder(other_children, node_id=f"{group_node_id}:other")
    if other_folder is not None:
        children.append(other_folder)

    if path_value is None and not children:
        return None

    children = _apply_saved_order(children, group_node_id, saved_order)
    return MarkdownTreeNodeModel(
        id=group_node_id,
        kind="group",
        title=_group_title(group_dir, group_idx),
        path=path_value,
        children=children,
    )


def build_markdown_tree(asset_name: str) -> list[MarkdownTreeNodeModel]:
    asset_dir = resolve_asset_dir(asset_name)
    saved_order = _load_sidebar_order(asset_name)
    nodes: list[MarkdownTreeNodeModel] = []

    group_root = asset_dir / "group_data"
    if group_root.is_dir():
        for group_dir in sorted(group_root.iterdir(), key=_entry_sort_key):
            if not group_dir.is_dir() or not group_dir.name.isdigit():
                continue
            group_idx = int(group_dir.name)
            group_node = _build_group_tree(asset_dir, group_dir, group_idx=group_idx, saved_order=saved_order)
            if group_node is not None:
                nodes.append(group_node)

    return _apply_saved_order(nodes, None, saved_order)


def set_markdown_node_alias(
    asset_name: str,
    node_id: str,
    path: str | None,
    alias: str,
) -> dict[str, str | None]:
    resolve_asset_dir(asset_name)
    nodes = build_markdown_tree(asset_name)
    match = _find_tree_node(nodes, node_id)
    if match is None:
        raise ApiError(404, "markdown_node_not_found", f"Markdown node '{node_id}' not found.")

    node, _parent_id = match
    path_value = path.strip() if isinstance(path, str) and path.strip() else None

    if node.kind == "group":
        group_match = re.fullmatch(r"group:(\d+)", node.id)
        if group_match is None:
            raise ApiError(400, "invalid_markdown_node", "Invalid group node id.")
        if path_value and path_value != node.path:
            raise ApiError(400, "invalid_markdown_node_path", "Group node path does not match.")
        group_idx = int(group_match.group(1))
        group_dir = resolve_asset_dir(asset_name) / "group_data" / str(group_idx)
        if not group_dir.is_dir():
            raise ApiError(404, "group_not_found", f"Group {group_idx} not found.")
        title = _write_alias(group_dir / "group.alias", alias, f"Group {group_idx}")
        return {"nodeId": node.id, "path": node.path, "title": title}

    if node.kind == "tutor":
        tutor_match = re.fullmatch(r"tutor:(\d+):(\d+):focus", node.id)
        if tutor_match is None or not node.path:
            raise ApiError(400, "invalid_markdown_node", "Invalid tutor node id.")
        if path_value and path_value != node.path:
            raise ApiError(400, "invalid_markdown_node_path", "Tutor node path does not match.")
        resolved_path = resolve_relative_file(asset_name, node.path)
        if resolved_path.name != "focus.md":
            raise ApiError(400, "invalid_markdown_node_path", "Tutor alias can only target focus.md.")
        title = _write_alias(_markdown_alias_path(resolved_path), alias, resolved_path.name)
        return {"nodeId": node.id, "path": node.path, "title": title}

    if node.kind == "folder" or node.path is None or node.children:
        raise ApiError(400, "invalid_markdown_node", "Alias can only be changed for real content nodes.")

    if not path_value:
        raise ApiError(400, "invalid_markdown_node_path", "Leaf markdown alias requires a matching path.")
    if path_value != node.path:
        raise ApiError(400, "invalid_markdown_node_path", "Leaf markdown path does not match the node.")

    resolved_path = resolve_relative_file(asset_name, path_value)
    if resolved_path.suffix.lower() != ".md":
        raise ApiError(400, "invalid_markdown_node_path", "Alias can only target markdown files.")
    title = _write_alias(_markdown_alias_path(resolved_path), alias, resolved_path.name)
    return {"nodeId": node.id, "path": node.path, "title": title}


def reorder_markdown_siblings(
    asset_name: str,
    parent_id: str | None,
    ordered_node_ids: list[str],
) -> dict[str, object]:
    resolve_asset_dir(asset_name)
    normalized_ids: list[str] = []
    for item in ordered_node_ids:
        if not isinstance(item, str) or not item or item in normalized_ids:
            raise ApiError(400, "invalid_sidebar_order", "orderedNodeIds must be unique non-empty strings.")
        normalized_ids.append(item)
    if not normalized_ids:
        raise ApiError(400, "invalid_sidebar_order", "orderedNodeIds must not be empty.")

    nodes = build_markdown_tree(asset_name)
    siblings: list[MarkdownTreeNodeModel]
    normalized_parent_id = parent_id if isinstance(parent_id, str) and parent_id else None

    if normalized_parent_id is None:
        siblings = nodes
    else:
        parent_match = _find_tree_node(nodes, normalized_parent_id)
        if parent_match is None:
            raise ApiError(404, "markdown_parent_not_found", f"Markdown parent '{normalized_parent_id}' not found.")
        parent_node, _ = parent_match
        if not parent_node.children:
            raise ApiError(400, "invalid_sidebar_parent", "Only nodes with children can be reordered.")
        siblings = parent_node.children

    sibling_ids = [node.id for node in siblings]
    if set(sibling_ids) != set(normalized_ids) or len(sibling_ids) != len(normalized_ids):
        raise ApiError(400, "invalid_sidebar_order", "orderedNodeIds must be a complete sibling permutation.")

    sidebar_order = _load_sidebar_order(asset_name)
    sidebar_order[_normalize_parent_storage_key(normalized_parent_id)] = normalized_ids
    _save_sidebar_order(asset_name, sidebar_order)
    return {"parentId": normalized_parent_id, "orderedNodeIds": normalized_ids}


def get_markdown_content(asset_name: str, raw_path: str) -> MarkdownContentModel:
    path = resolve_relative_file(asset_name, raw_path)
    if path.suffix.lower() != ".md":
        raise ApiError(400, "invalid_markdown_path", "Only markdown files can be loaded from this endpoint.")
    markdown = read_text_auto(path)
    normalized, full_html, body_html, head_html = _render_markdown_document(markdown)
    return MarkdownContentModel(
        path=path.relative_to(resolve_asset_dir(asset_name)).as_posix(),
        title=_display_title(path, path.name),
        markdown=normalized,
        html=full_html,
        bodyHtml=body_html,
        headHtml=head_html,
    )


__all__ = [
    "build_markdown_tree",
    "get_markdown_content",
    "reorder_markdown_siblings",
    "set_markdown_node_alias",
]
