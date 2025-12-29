from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AssetInitResult:
    asset_dir: Path
    references_dir: Path
    raw_pdf_path: Path
    reference_files: list[Path]


@dataclass(frozen=True)
class BlockRect:
    x: float
    y: float
    width: float
    height: float

    @classmethod
    def from_dict(cls, data: dict) -> BlockRect:
        try:
            return cls(
                x=float(data["x"]),
                y=float(data["y"]),
                width=float(data["width"]),
                height=float(data["height"]),
            )
        except Exception as exc:  # pragma: no cover - defensive parsing
            raise ValueError(f"Invalid rect: {data}") from exc

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
        }


@dataclass(frozen=True)
class BlockRecord:
    block_id: int
    page_index: int
    rect: BlockRect
    group_idx: int | None = None

    @classmethod
    def from_dict(cls, data: dict) -> BlockRecord:
        try:
            block_id = int(data.get("block_id", data.get("id")))
            page_index = int(data["page_index"])
            rect = BlockRect.from_dict(data["rect"])
            group_idx_raw = data.get("group_idx")
            group_idx = int(group_idx_raw) if group_idx_raw is not None else None
        except Exception as exc:  # pragma: no cover - defensive parsing
            raise ValueError(f"Invalid block record: {data}") from exc
        return cls(block_id=block_id, page_index=page_index, rect=rect, group_idx=group_idx)

    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "page_index": self.page_index,
            "rect": self.rect.to_dict(),
            "group_idx": self.group_idx,
        }


@dataclass(frozen=True)
class BlockData:
    blocks: list[BlockRecord]
    merge_order: list[int]
    next_block_id: int

    @classmethod
    def empty(cls) -> BlockData:
        return cls(blocks=[], merge_order=[], next_block_id=1)

    @classmethod
    def from_dict(cls, data: dict) -> BlockData:
        blocks_raw = data.get("blocks", [])
        merge_order_raw = data.get("merge_order", [])
        next_block_id = int(data.get("next_block_id", 1))

        blocks: list[BlockRecord] = []
        for entry in blocks_raw:
            try:
                blocks.append(BlockRecord.from_dict(entry))
            except ValueError as exc:  # pragma: no cover - defensive parsing
                logging.warning("Skipping invalid block entry: %s", exc)

        merge_order: list[int] = []
        for bid in merge_order_raw:
            try:
                merge_order.append(int(bid))
            except Exception:  # pragma: no cover - defensive parsing
                logging.warning("Invalid merge_order entry: %s", bid)

        if next_block_id <= 0:
            next_block_id = 1
        return cls(blocks=blocks, merge_order=merge_order, next_block_id=next_block_id)

    def to_dict(self) -> dict:
        return {
            "blocks": [block.to_dict() for block in self.blocks],
            "merge_order": self.merge_order,
            "next_block_id": self.next_block_id,
        }


@dataclass(frozen=True)
class GroupRecord:
    group_idx: int
    block_ids: list[int]

    @classmethod
    def from_dict(cls, data: dict, *, default_idx: int | None = None) -> GroupRecord:
        try:
            idx_value = data.get("group_idx", default_idx)
            if idx_value is None:
                raise ValueError("Missing group_idx")
            group_idx = int(idx_value)
            raw_block_ids = data.get("block_ids", data.get("blocks", []))
            block_ids = list(dict.fromkeys(int(bid) for bid in raw_block_ids))
        except Exception as exc:  # pragma: no cover - defensive parsing
            raise ValueError(f"Invalid group record: {data}") from exc
        if not block_ids:
            raise ValueError("Group record must contain block_ids.")
        return cls(group_idx=group_idx, block_ids=block_ids)

    def to_dict(self) -> dict:
        return {
            "group_idx": self.group_idx,
            "block_ids": self.block_ids,
        }

