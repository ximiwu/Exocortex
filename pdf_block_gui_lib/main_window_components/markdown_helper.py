from __future__ import annotations

import re

from PySide6 import QtCore

from .constants import KATEX_CDN_BASE, KATEX_LOCAL_DIR, KATEX_RENDER_SCRIPT

try:
    import markdown
except ImportError:  # pragma: no cover - optional dependency guard
    markdown = None

try:
    import pymdownx.arithmatex  # type: ignore  # noqa: F401

    _ARITHMETEX_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    _ARITHMETEX_AVAILABLE = False


_BOLD_SYMBOL_PATTERN = re.compile(r"\\mathbf\\s*\\{\\s*(\\\\[A-Za-z]+)\\s*\\}")
_DETAILS_BLOCK_PATTERN = re.compile(r"<details\b[^>]*>.*?</details>", re.IGNORECASE | re.DOTALL)
_DETAILS_TAG_PATTERN = re.compile(r"<details\b([^>]*)>", re.IGNORECASE)
_DIV_TAG_PATTERN = re.compile(r"<div\b([^>]*)>", re.IGNORECASE)
_CLASS_ATTR_PATTERN = re.compile(r"\bclass\s*=\s*(\"([^\"]*)\"|'([^']*)')", re.IGNORECASE)
_MARKDOWN_ATTR_PATTERN = re.compile(r"\bmarkdown\s*=", re.IGNORECASE)
_LIST_MARKER_PATTERN = re.compile(r"^(?P<indent>[ \t]{0,3})(?P<marker>(?:\d+[.)]|[-+*]))\s+")
_FENCE_PATTERN = re.compile(r"^(?P<indent>[ \t]*)(?P<fence>[`~]{3,}).*$")


def normalize_math_content(content: str) -> str:
    """Adjust math macros to keep KaTeX happy (e.g., bold Greek via \\boldsymbol)."""
    return _BOLD_SYMBOL_PATTERN.sub(r"\\boldsymbol{\1}", content)


def normalize_details_attrs(attrs: str) -> tuple[str, bool]:
    attrs_text = attrs
    class_match = _CLASS_ATTR_PATTERN.search(attrs_text)
    has_note = False
    if class_match:
        class_value = class_match.group(2) or class_match.group(3) or ""
        classes = class_value.split()
        has_note = "note" in classes or "note-container" in classes
        if has_note and "note-container" not in classes:
            classes.append("note-container")
            new_value = " ".join(classes)
            attrs_text = (
                attrs_text[: class_match.start()]
                + f' class="{new_value}"'
                + attrs_text[class_match.end() :]
            )
    if not _MARKDOWN_ATTR_PATTERN.search(attrs_text):
        attrs_text = attrs_text.rstrip() + ' markdown="1"'
    return attrs_text, has_note


def normalize_note_content_divs(block: str) -> str:
    def replace_div(match: re.Match[str]) -> str:
        attrs = match.group(1)
        if not _MARKDOWN_ATTR_PATTERN.search(attrs):
            return match.group(0)
        class_match = _CLASS_ATTR_PATTERN.search(attrs)
        if class_match:
            class_value = class_match.group(2) or class_match.group(3) or ""
            classes = class_value.split()
            if "note-content" not in classes:
                classes.append("note-content")
                new_value = " ".join(classes)
                attrs = (
                    attrs[: class_match.start()]
                    + f' class="{new_value}"'
                    + attrs[class_match.end() :]
                )
        else:
            attrs = f' class="note-content"{attrs}'
        return f"<div{attrs}>"

    return _DIV_TAG_PATTERN.sub(replace_div, block)


def normalize_details_markdown(content: str) -> str:
    def replace_block(match: re.Match[str]) -> str:
        block = match.group(0)
        tag_match = _DETAILS_TAG_PATTERN.search(block)
        if not tag_match:
            return block
        attrs = tag_match.group(1)
        new_attrs, has_note = normalize_details_attrs(attrs)
        block = block.replace(tag_match.group(0), f"<details{new_attrs}>", 1)
        if has_note:
            block = normalize_note_content_divs(block)
        return block

    return _DETAILS_BLOCK_PATTERN.sub(replace_block, content)


def normalize_list_spacing_markdown(content: str) -> str:
    """Insert blank lines so Python-Markdown recognizes lists consistently."""

    def list_info(line: str) -> tuple[int, str] | None:
        match = _LIST_MARKER_PATTERN.match(line)
        if not match:
            return None
        indent = len(match.group("indent").expandtabs(4))
        marker = match.group("marker")
        kind = "ordered" if marker[0].isdigit() else "bullet"
        return indent, kind

    lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out_lines: list[str] = []
    in_fence = False
    fence_marker: str | None = None
    fence_len = 0

    for line in lines:
        stripped = line.lstrip()
        fence_match = _FENCE_PATTERN.match(line)
        if fence_match:
            fence = fence_match.group("fence")
            if not in_fence:
                in_fence = True
                fence_marker = fence[0]
                fence_len = len(fence)
            elif fence_marker and stripped.startswith(fence_marker * fence_len):
                in_fence = False
                fence_marker = None
                fence_len = 0
            out_lines.append(line)
            continue

        if in_fence:
            out_lines.append(line)
            continue

        current_info = list_info(line)
        if current_info and out_lines and out_lines[-1].strip():
            previous_info = list_info(out_lines[-1])
            if previous_info is None:
                out_lines.append("")
            else:
                prev_indent, prev_kind = previous_info
                cur_indent, cur_kind = current_info
                if prev_indent == cur_indent and prev_kind != cur_kind:
                    out_lines.append("")

        out_lines.append(line)

    return "\n".join(out_lines)


def katex_assets() -> str:
    local_available = (KATEX_LOCAL_DIR / "katex.min.js").is_file()
    if local_available:
        base_url = QtCore.QUrl.fromLocalFile(str(KATEX_LOCAL_DIR)).toString(QtCore.QUrl.FullyEncoded)
        css = (
            f'<link rel="stylesheet" href="{base_url}/katex.min.css">'
            f'<link rel="stylesheet" href="{base_url}/contrib/copy-tex.css">'
        )
        scripts = (
            f'<script src="{base_url}/katex.min.js"></script>'
            f'<script src="{base_url}/contrib/copy-tex.min.js"></script>'
            f'<script src="{base_url}/contrib/auto-render.min.js"></script>'
        )
    else:
        css = (
            f'<link rel="stylesheet" href="{KATEX_CDN_BASE}/katex.min.css">'
            f'<link rel="stylesheet" href="{KATEX_CDN_BASE}/contrib/copy-tex.css">'
        )
        scripts = (
            f'<script src="{KATEX_CDN_BASE}/katex.min.js"></script>'
            f'<script src="{KATEX_CDN_BASE}/contrib/copy-tex.min.js"></script>'
            f'<script src="{KATEX_CDN_BASE}/contrib/auto-render.min.js"></script>'
        )
    render_helper_url = QtCore.QUrl.fromLocalFile(str(KATEX_RENDER_SCRIPT)).toString(QtCore.QUrl.FullyEncoded)
    scripts += f'<script src="{render_helper_url}"></script>'
    return css + scripts


def render_markdown_content(content: str) -> str:
    if markdown is None:
        raise RuntimeError("Missing 'markdown' package for rendering.")
    if not _ARITHMETEX_AVAILABLE:
        raise RuntimeError("Missing 'pymdown-extensions' for math rendering (pip install pymdown-extensions).")

    extensions = ["extra", "sane_lists", "fenced_code", "tables", "pymdownx.arithmatex"]
    extension_configs = {"pymdownx.arithmatex": {"generic": True}}
    normalized = normalize_math_content(content.lstrip("\ufeff"))
    normalized = normalize_details_markdown(normalized)
    normalized = normalize_list_spacing_markdown(normalized)
    md = markdown.Markdown(
        extensions=extensions,
        extension_configs=extension_configs,
    )
    block_elements = md.block_level_elements
    if isinstance(block_elements, set):
        block_elements.update({"details", "summary"})
    else:
        for tag in ("details", "summary"):
            if tag not in block_elements:
                block_elements.append(tag)
    body = md.convert(normalized)
    styles = """
body { font-family: 'Times New Roman','Segoe UI','Helvetica Neue',Arial,sans-serif; font-size: 16px; line-height: 1.6; color: #222; padding: 16px; }
p { margin: 0.6em 0; }
pre { background: #f7f7f7; padding: 10px; border: 1px solid #e0e0e0; overflow-x: auto; }
code { font-family: 'JetBrains Mono','Consolas',monospace; font-size: 0.95em; }
img { max-width: 100%; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; }
th, td { border: 1px solid #dcdcdc; padding: 10px 12px; vertical-align: top; }
thead th { background: #f5f5f5; font-weight: 600; }
.katex { font-size: 1.05em; }
.katex-display { margin: 1em 0; }
details.note-container { background-color: #F8F6E4; border-left: 5px solid #E0D785; margin: 10px 0; padding: 10px; border-radius: 4px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); transition: all 0.3s ease; }
details.note-container summary { font-weight: bold; color: #f57f17; cursor: pointer; list-style: none; outline: none; }
details.note-container summary::after { content: '+'; float: right; font-weight: bold; }
details.note-container[open] summary::after { content: '-'; }
.note-content { margin-top: 10px; color: #333; font-size: 0.9em; line-height: 1.5; }
"""

    head_assets = katex_assets()
    html_text = (
        "<!DOCTYPE html>"
        "<html><head><meta charset='UTF-8'>"
        f"<style>{styles}</style>{head_assets}"
        "</head><body>"
        f"{body}"
        "</body></html>"
    )
    return html_text


__all__ = [
    "katex_assets",
    "normalize_details_attrs",
    "normalize_details_markdown",
    "normalize_list_spacing_markdown",
    "normalize_math_content",
    "normalize_note_content_divs",
    "render_markdown_content",
]

