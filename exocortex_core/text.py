from __future__ import annotations

from pathlib import Path


DEFAULT_CANDIDATE_ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "gb18030")


def read_text_auto(path: Path, *, encodings: tuple[str, ...] = DEFAULT_CANDIDATE_ENCODINGS) -> str:
    raw_bytes = path.read_bytes()
    for encoding in encodings:
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def write_text_utf8(path: Path, text: str, *, newline: str = "\n") -> None:
    path.write_text(text, encoding="utf-8", newline=newline)


__all__ = [
    "DEFAULT_CANDIDATE_ENCODINGS",
    "read_text_auto",
    "write_text_utf8",
]

