from __future__ import annotations

from dataclasses import dataclass

from PySide6 import QtCore


@dataclass
class Block:
    block_id: int
    page_index: int
    rect: QtCore.QRectF
    group_idx: int | None = None
