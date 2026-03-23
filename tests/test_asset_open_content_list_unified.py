from __future__ import annotations

import json
from pathlib import Path

import fitz

from exocortex_core.contracts import BlockData
from server.services import assets as asset_service


def _write_pdf(path: Path) -> None:
    document = fitz.open()
    document.new_page(width=72, height=72)
    document.save(path)
    document.close()


def test_build_asset_state_generates_missing_unified_content_list(
    tmp_path: Path,
    monkeypatch,
) -> None:
    asset_dir = tmp_path / "asset-open"
    asset_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = asset_dir / "raw.pdf"
    _write_pdf(pdf_path)
    (asset_dir / "content_list.json").write_text(
        json.dumps(
            [
                {
                    "type": "text",
                    "text": "opened asset",
                    "bbox": [13, 13, 39, 39],
                    "page_idx": 0,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        asset_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )
    monkeypatch.setattr(asset_service, "get_asset_pdf_path", lambda _asset_name: pdf_path)
    monkeypatch.setattr(asset_service, "load_block_data", lambda _asset_name: BlockData.empty())
    monkeypatch.setattr(asset_service, "load_group_records", lambda _asset_name: [])
    monkeypatch.setattr(asset_service, "_list_reference_names", lambda _asset_name: [])
    monkeypatch.setattr(asset_service, "get_asset_config", lambda _asset_name: {})

    state = asset_service.build_asset_state("asset-open")

    assert state.asset.name == "asset-open"
    assert state.asset.pageCount == 1
    unified_path = asset_dir / "content_list_unified.json"
    assert unified_path.is_file()

