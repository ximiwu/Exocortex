from __future__ import annotations

import re
from pathlib import Path

from .text import read_text_auto, write_text_utf8


_FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
_BLOCKQUOTE_PREFIX_PATTERN = re.compile(r"^(?:\s{0,3}>\s?)+")
_LIST_START_PATTERN = re.compile(r"^(?:\s{0,3})(?:[*+-]\s+|\d+[.)]\s+)")


def normalize_paragraph_list_separation(content: str) -> str:
    """
    Insert a blank line between a paragraph line and a following list item.

    Python-Markdown requires a blank line between a paragraph and a list to parse
    list blocks. Without it, list markers are treated as literal text.
    """

    lines = content.splitlines()
    if len(lines) < 2:
        return content

    out: list[str] = []
    in_fenced_code = False
    fence_marker: str | None = None

    for idx, line in enumerate(lines):
        out.append(line)

        fence_match = _FENCE_PATTERN.match(line)
        if fence_match:
            marker = fence_match.group(1)[0]
            if not in_fenced_code:
                in_fenced_code = True
                fence_marker = marker
            elif fence_marker == marker:
                in_fenced_code = False
                fence_marker = None

        if in_fenced_code:
            continue
        if idx >= len(lines) - 1:
            continue

        next_line = lines[idx + 1]
        if not line.strip():
            continue
        if not next_line.strip():
            continue

        current_prefix_match = _BLOCKQUOTE_PREFIX_PATTERN.match(line)
        next_prefix_match = _BLOCKQUOTE_PREFIX_PATTERN.match(next_line)
        current_prefix = current_prefix_match.group(0) if current_prefix_match else ""
        next_prefix = next_prefix_match.group(0) if next_prefix_match else ""
        if current_prefix != next_prefix:
            continue

        current_content = line[len(current_prefix) :]
        next_content = next_line[len(next_prefix) :]
        if _LIST_START_PATTERN.match(current_content):
            continue
        if not _LIST_START_PATTERN.match(next_content):
            continue

        out.append(current_prefix.rstrip())

    return "\n".join(out)


def clean_markdown_text(content: str) -> str:
    def fix_latex_syntax(text: str) -> str:
        return text.replace("\\\\", "\\")

    content = content.lstrip("\ufeff")
    content = re.sub(r"\\\[(.*?)\\\]", r"$$\1$$", content, flags=re.DOTALL)
    content = re.sub(r"\\\((.*?)\\\)", r"$\1$", content, flags=re.DOTALL)

    def clean_inline(match: re.Match[str]) -> str:
        inner = fix_latex_syntax(match.group(1))
        inner = inner.replace("\u00A0", " ").replace("\u3000", " ").strip()
        return f"${inner}$"

    content = re.sub(
        r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)", clean_inline, content, flags=re.DOTALL
    )

    pattern = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)

    def reform_block(match: re.Match[str]) -> str:
        math_content = fix_latex_syntax(match.group(1))
        lines = math_content.splitlines()
        clean_lines = []
        for line in lines:
            stripped = line.strip().replace("\u00A0", " ").replace("\u3000", " ")
            stripped = stripped.replace("\u200b", " ").replace("\ufeff", " ")
            if stripped:
                clean_lines.append(stripped)
        cleaned_math_body = "\n".join(clean_lines)
        return f"\n\n$$\n{cleaned_math_body}\n$$\n\n"

    new_content = pattern.sub(reform_block, content)

    lines = new_content.splitlines()
    processed_lines = []
    in_code_block = False
    strip_chars = " \t\u00A0\u3000"

    for line in lines:
        if re.match(r"^\s*```", line):
            in_code_block = not in_code_block
            processed_lines.append(line.lstrip(strip_chars))
            continue
        if in_code_block:
            processed_lines.append(line)
        else:
            processed_lines.append(line.lstrip(strip_chars))

    new_content = "\n".join(processed_lines)
    new_content = re.sub(r"\n{3,}", "\n\n", new_content)
    return new_content


def clean_markdown_file(path: Path) -> None:
    content = read_text_auto(path)
    cleaned = clean_markdown_text(content)
    write_text_utf8(path, cleaned, newline="\n")


__all__ = [
    "clean_markdown_file",
    "clean_markdown_text",
    "normalize_paragraph_list_separation",
]

