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


def _build_asset_state(
    blocks: list[dict[str, object]],
    *,
    disabled_content_item_indexes: list[int] | None = None,
) -> AssetStateModel:
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
            "disabledContentItemIndexes": disabled_content_item_indexes or [],
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
                "image_explaination": "Figure 1 explanation",
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
        "Figure 1 explanation  \n"
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
    assert result.warning is None


def test_preview_merge_markdown_warns_and_falls_back_when_image_explaination_is_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-image-fallback"
    _write_content_list_unified(
        asset_dir,
        [
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
                    "fractionRect": {"x": 0.05, "y": 0.05, "width": 0.45, "height": 0.55},
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

    result = pdf_service.preview_merge_markdown("asset-image-fallback", [1])

    assert result.markdown == "Figure 1  \n![](images/chart.png)  \nCaption note"
    assert result.warning == "Image item 1 is missing image_explaination. The markdown preview fell back to img_path."


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


def test_preview_merge_markdown_skips_disabled_content_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-disabled"
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
                    "fractionRect": {"x": 0.05, "y": 0.05, "width": 0.45, "height": 0.45},
                    "groupIdx": None,
                }
            ],
            disabled_content_item_indexes=[2],
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

    result = pdf_service.preview_merge_markdown("asset-disabled", [1])

    assert result.markdown == "## Heading\n\nalpha  \nbeta"


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


def test_preview_merge_markdown_reads_asset_state_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-single-state"
    _write_content_list_unified(
        asset_dir,
        [
            {
                "page_idx": 1,
                "type": "text",
                "text": "Only once",
                "x": 0.1,
                "y": 0.1,
                "width": 0.2,
                "height": 0.08,
            }
        ],
    )

    build_calls = 0

    def _counted_build_asset_state(_asset_name: str) -> AssetStateModel:
        nonlocal build_calls
        build_calls += 1
        return _build_asset_state(
            [
                {
                    "blockId": 1,
                    "pageIndex": 0,
                    "fractionRect": {"x": 0.05, "y": 0.05, "width": 0.45, "height": 0.45},
                    "groupIdx": None,
                }
            ]
        )

    monkeypatch.setattr(pdf_service, "build_asset_state", _counted_build_asset_state)
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

    result = pdf_service.preview_merge_markdown("asset-single-state", [1])

    assert result.markdown == "Only once"
    assert build_calls == 1


def test_search_pdf_content_matches_only_rendered_markdown_fragments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-search"
    _write_content_list_unified(
        asset_dir,
        [
            {
                "page_idx": 1,
                "type": "text",
                "text": "Energy conservation",
                "x": 0.1,
                "y": 0.1,
                "width": 0.2,
                "height": 0.08,
            },
            {
                "page_idx": 1,
                "type": "table",
                "table_caption": ["Conservation Table"],
                "table_body": "<table><tr><td>Energy</td></tr></table>",
                "x": 0.15,
                "y": 0.2,
                "width": 0.25,
                "height": 0.12,
            },
            {
                "page_idx": 2,
                "type": "image",
                "image_explaination": "Energy flow diagram",
                "x": 0.2,
                "y": 0.12,
                "width": 0.2,
                "height": 0.1,
            },
            {
                "page_idx": 2,
                "type": "footnote",
                "text": "Ignored footnote",
                "x": 0.22,
                "y": 0.24,
                "width": 0.2,
                "height": 0.08,
            },
        ],
    )
    monkeypatch.setattr(
        pdf_service,
        "build_asset_state",
        lambda _asset_name: _build_asset_state([]),
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

    result = pdf_service.search_pdf_content("asset-search", "energy")

    assert result.query == "energy"
    assert [(match.itemIndex, match.pageIndex) for match in result.matches] == [
        (1, 0),
        (2, 0),
        (3, 1),
    ]


def test_search_pdf_content_skips_disabled_items(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-search-disabled"
    _write_content_list_unified(
        asset_dir,
        [
            {
                "page_idx": 1,
                "type": "text",
                "text": "Momentum theorem",
                "x": 0.1,
                "y": 0.1,
                "width": 0.2,
                "height": 0.08,
            },
            {
                "page_idx": 2,
                "type": "text",
                "text": "Momentum balance",
                "x": 0.18,
                "y": 0.2,
                "width": 0.22,
                "height": 0.08,
            },
        ],
    )
    monkeypatch.setattr(
        pdf_service,
        "build_asset_state",
        lambda _asset_name: _build_asset_state([], disabled_content_item_indexes=[2]),
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

    result = pdf_service.search_pdf_content("asset-search-disabled", "momentum")

    assert [match.itemIndex for match in result.matches] == [1]


def test_search_pdf_content_returns_empty_matches_for_blank_query(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-search-empty"
    _write_content_list_unified(asset_dir, [])
    monkeypatch.setattr(
        pdf_service,
        "build_asset_state",
        lambda _asset_name: _build_asset_state([]),
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

    result = pdf_service.search_pdf_content("asset-search-empty", "   ")

    assert result.query == ""
    assert result.matches == []


def test_search_pdf_content_reports_invalid_search_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-search-bad"
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "content_list_unified.json").write_text("{bad json", encoding="utf-8")
    monkeypatch.setattr(
        pdf_service,
        "build_asset_state",
        lambda _asset_name: _build_asset_state([]),
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
        pdf_service.search_pdf_content("asset-search-bad", "energy")

    assert excinfo.value.status_code == 500
    assert excinfo.value.code == "invalid_pdf_search_source"


def test_render_markdown_fragment_uses_table_image_fallback() -> None:
    rendered = pdf_service._render_markdown_fragment(
        {
            "type": "table",
            "table_caption": ["Table A"],
            "img_path": "images/table-a.png",
            "table_footnote": ["Table note"],
        }
    )

    assert rendered.markdown == "Table A\n![](images/table-a.png)\nTable note"
    assert rendered.warning is None


def test_render_markdown_fragment_renders_algorithm_without_code_fence() -> None:
    rendered = pdf_service._render_markdown_fragment(
        {
            "type": "code",
            "sub_type": "algorithm",
            "code_caption": ["Algorithm 1"],
            "algorithm_content": "step 1 -> step 2",
        }
    )

    assert rendered.markdown == "Algorithm 1  \nstep 1 -> step 2"
    assert rendered.warning is None
