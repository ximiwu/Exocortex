from __future__ import annotations

import json
from pathlib import Path

import pytest

from server.errors import ApiError
from server.schemas import AssetStateModel
from server.services import pdf as pdf_service


@pytest.fixture(autouse=True)
def _clear_content_list_cache() -> None:
    pdf_service._CONTENT_LIST_CACHE.clear()
    yield
    pdf_service._CONTENT_LIST_CACHE.clear()


def _write_content_list_unified(asset_dir: Path, payload: object) -> Path:
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / "content_list_unified.json"
    target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return target


def _build_asset_state(blocks: list[dict[str, object]]) -> AssetStateModel:
    return AssetStateModel.model_validate(
        {
            "asset": {
                "name": "asset-a",
                "pageCount": 2,
                "pdfPath": "asset-a/raw.pdf",
            },
            "references": [],
            "blocks": blocks,
            "mergeOrder": [],
            "nextBlockId": 3,
            "groups": [],
            "uiState": {
                "currentPage": 1,
                "zoom": 1.0,
                "pdfScrollFraction": 0.0,
                "pdfScrollLeftFraction": 0.0,
                "currentMarkdownPath": None,
                "openMarkdownPaths": [],
                "sidebarCollapsed": False,
                "sidebarCollapsedNodeIds": [],
                "markdownScrollFractions": {},
                "sidebarWidthRatio": None,
                "rightRailWidthRatio": None,
            },
        }
    )


def test_preview_merge_markdown_renders_contained_items_in_original_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-a"
    _write_content_list_unified(
        asset_dir,
        [
            {
                "page_idx": 1,
                "type": "text",
                "text": "Heading",
                "text_level": 2,
                "x": 0.1,
                "y": 0.1,
                "width": 0.2,
                "height": 0.08,
            },
            {
                "page_idx": 1,
                "type": "text",
                "text": "Body paragraph",
                "x": 0.12,
                "y": 0.22,
                "width": 0.3,
                "height": 0.08,
            },
            {
                "page_idx": 1,
                "type": "list",
                "list_items": ["alpha", "beta"],
                "x": 0.14,
                "y": 0.34,
                "width": 0.3,
                "height": 0.1,
            },
            {
                "page_idx": 1,
                "type": "image",
                "img_path": "images/chart.png",
                "image_caption": ["Figure 1"],
                "image_footnote": ["Caption note"],
                "x": 0.16,
                "y": 0.46,
                "width": 0.2,
                "height": 0.08,
            },
            {
                "page_idx": 2,
                "type": "table",
                "table_caption": ["Table 1"],
                "table_body": "<table><tr><td>A</td></tr></table>",
                "table_footnote": ["Table foot"],
                "x": 0.2,
                "y": 0.1,
                "width": 0.2,
                "height": 0.1,
            },
            {
                "page_idx": 2,
                "type": "code",
                "sub_type": "code",
                "code_caption": ["Listing 1"],
                "code_body": "print('hi')",
                "guess_lang": "python",
                "x": 0.22,
                "y": 0.24,
                "width": 0.2,
                "height": 0.1,
            },
            {
                "page_idx": 2,
                "type": "equation",
                "text": "$$\na=b\n$$",
                "text_format": "latex",
                "x": 0.24,
                "y": 0.38,
                "width": 0.2,
                "height": 0.1,
            },
            {
                "page_idx": 2,
                "type": "text",
                "text": "Partially overlapping only",
                "x": 0.55,
                "y": 0.4,
                "width": 0.1,
                "height": 0.1,
            },
        ],
    )
    monkeypatch.setattr(
        pdf_service,
        "build_asset_state",
        lambda _asset_name: _build_asset_state(
            [
                {
                    "blockId": 1,
                    "pageIndex": 0,
                    "fractionRect": {"x": 0.05, "y": 0.05, "width": 0.45, "height": 0.55},
                    "groupIdx": None,
                },
                {
                    "blockId": 2,
                    "pageIndex": 1,
                    "fractionRect": {"x": 0.1, "y": 0.05, "width": 0.4, "height": 0.5},
                    "groupIdx": None,
                },
            ]
        ),
    )
    monkeypatch.setattr(
        pdf_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )
    monkeypatch.setattr(
        pdf_service,
        "ensure_content_list_unified",
        lambda _asset_name: asset_dir / "content_list_unified.json",
    )

    result = pdf_service.preview_merge_markdown("asset-a", [1, 2, 1])

    assert result.markdown == (
        "## Heading\n\n"
        "Body paragraph\n\n"
        "alpha  \n"
        "beta\n\n"
        "Figure 1  \n"
        "![](images/chart.png)  \n"
        "Caption note\n\n"
        "Table 1\n"
        "<table><tr><td>A</td></tr></table>\n"
        "Table foot\n\n"
        "Listing 1  \n"
        "```python\n"
        "print('hi')\n"
        "```\n\n"
        "$$\n"
        "a=b\n"
        "$$"
    )


def test_preview_merge_markdown_returns_empty_when_nothing_is_contained(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-empty"
    _write_content_list_unified(
        asset_dir,
        [
            {
                "page_idx": 1,
                "type": "text",
                "text": "Outside",
                "x": 0.7,
                "y": 0.7,
                "width": 0.1,
                "height": 0.1,
            }
        ],
    )
    monkeypatch.setattr(
        pdf_service,
        "build_asset_state",
        lambda _asset_name: _build_asset_state(
            [
                {
                    "blockId": 1,
                    "pageIndex": 0,
                    "fractionRect": {"x": 0.05, "y": 0.05, "width": 0.2, "height": 0.2},
                    "groupIdx": None,
                }
            ]
        ),
    )
    monkeypatch.setattr(
        pdf_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )
    monkeypatch.setattr(
        pdf_service,
        "ensure_content_list_unified",
        lambda _asset_name: asset_dir / "content_list_unified.json",
    )

    result = pdf_service.preview_merge_markdown("asset-empty", [1])

    assert result.markdown == ""


def test_preview_merge_markdown_rejects_grouped_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pdf_service,
        "build_asset_state",
        lambda _asset_name: _build_asset_state(
            [
                {
                    "blockId": 1,
                    "pageIndex": 0,
                    "fractionRect": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2},
                    "groupIdx": 9,
                }
            ]
        ),
    )

    with pytest.raises(ApiError) as excinfo:
        pdf_service.preview_merge_markdown("asset-a", [1])

    assert excinfo.value.status_code == 400
    assert excinfo.value.code == "block_already_grouped"


def test_preview_merge_markdown_reports_invalid_preview_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-bad-preview"
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "content_list_unified.json").write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr(
        pdf_service,
        "build_asset_state",
        lambda _asset_name: _build_asset_state(
            [
                {
                    "blockId": 1,
                    "pageIndex": 0,
                    "fractionRect": {"x": 0.05, "y": 0.05, "width": 0.5, "height": 0.5},
                    "groupIdx": None,
                }
            ]
        ),
    )
    monkeypatch.setattr(
        pdf_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )
    monkeypatch.setattr(
        pdf_service,
        "ensure_content_list_unified",
        lambda _asset_name: asset_dir / "content_list_unified.json",
    )

    with pytest.raises(ApiError) as excinfo:
        pdf_service.preview_merge_markdown("asset-bad-preview", [1])

    assert excinfo.value.status_code == 500
    assert excinfo.value.code == "invalid_markdown_preview_source"
