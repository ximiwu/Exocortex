from __future__ import annotations

from pathlib import Path

import pytest

from exocortex_core.contracts import (
    BlockData,
    BlockRecord,
    BlockRect,
    COORDINATE_SPACE_PAGE_FRACTION,
    COORDINATE_SPACE_REFERENCE_DPI,
)
from server.schemas import SizeModel
from server.services import assets as asset_service


def test_load_fraction_block_data_migrates_reference_coords_and_persists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_data = BlockData(
        blocks=[
            BlockRecord(
                block_id=1,
                page_index=0,
                rect=BlockRect(x=13.0, y=26.0, width=39.0, height=52.0),
                group_idx=None,
            )
        ],
        merge_order=[1],
        next_block_id=2,
        coordinate_space=COORDINATE_SPACE_REFERENCE_DPI,
    )
    saved: dict[str, object] = {}

    monkeypatch.setattr(asset_service, "load_block_data", lambda _asset_name: legacy_data)
    monkeypatch.setattr(
        asset_service,
        "_load_page_sizes_at_reference_dpi",
        lambda _pdf_path: [SizeModel(width=130.0, height=260.0)],
    )

    def _save_block_data(asset_name: str, data: BlockData) -> Path:
        saved["asset_name"] = asset_name
        saved["data"] = data
        return Path("blocks.json")

    monkeypatch.setattr(asset_service, "save_block_data", _save_block_data)

    migrated = asset_service._load_fraction_block_data("asset-a", Path("unused.pdf"))

    assert migrated.coordinate_space == COORDINATE_SPACE_PAGE_FRACTION
    assert len(migrated.blocks) == 1
    assert migrated.blocks[0].rect.x == pytest.approx(0.1)
    assert migrated.blocks[0].rect.y == pytest.approx(0.1)
    assert migrated.blocks[0].rect.width == pytest.approx(0.3)
    assert migrated.blocks[0].rect.height == pytest.approx(0.2)
    assert saved["asset_name"] == "asset-a"
    assert isinstance(saved["data"], BlockData)
    assert saved["data"].coordinate_space == COORDINATE_SPACE_PAGE_FRACTION
