from __future__ import annotations

import re
from pathlib import Path

from exocortex_core.markdown import normalize_paragraph_list_separation

from agent_manager import clean_markdown_file as _agent_clean_markdown_file


def clean_markdown_file(file_path: Path) -> None:
    _agent_clean_markdown_file(file_path)
    content = file_path.read_text(encoding="utf-8-sig").lstrip("\ufeff")
    content = normalize_paragraph_list_separation(content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    file_path.write_text(content, encoding="utf-8", newline="\n")

