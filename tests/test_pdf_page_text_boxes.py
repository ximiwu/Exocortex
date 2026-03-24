from __future__ import annotations

import json
from pathlib import Path

import fitz
import pytest

from server.errors import ApiError
from server.services import assets as asset_service
from server.services import pdf as pdf_service
from server.schemas import SizeModel


@pytest.fixture(autouse=True)
def _clear_text_box_cache() -> None:
    pdf_service._CONTENT_LIST_CACHE.clear()
    yield
    pdf_service._CONTENT_LIST_CACHE.clear()


def _write_content_list_unified(asset_dir: Path, payload: object) -> Path:
    asset_dir.mkdir(parents=True, exist_ok=True)
    target = asset_dir / "content_list_unified.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _write_pdf(path: Path) -> None:
    document = fitz.open()
    document.new_page(width=72, height=72)
    document.save(path)
    document.close()


def test_get_page_text_boxes_converts_page_idx_to_zero_based(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-a"
    _write_content_list_unified(
        asset_dir,
        [
            {"page_idx": 1, "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4},
            {"page_idx": 2, "x": 0.5, "y": 0.6, "width": 0.2, "height": 0.1},
        ],
    )
    monkeypatch.setattr(
        pdf_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )

    page_zero = pdf_service.get_page_text_boxes("asset-a", 0)
    page_one = pdf_service.get_page_text_boxes("asset-a", 1)

    assert page_zero.pageIndex == 0
    assert len(page_zero.items) == 1
    assert page_zero.items[0].itemIndex == 1
    assert page_zero.items[0].pageIndex == 0

    assert page_one.pageIndex == 1
    assert len(page_one.items) == 1
    assert page_one.items[0].itemIndex == 2
    assert page_one.items[0].pageIndex == 1


def test_get_page_text_boxes_cache_invalidation_when_file_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-cache"
    _write_content_list_unified(
        asset_dir,
        [{"page_idx": 1, "x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1}],
    )
    monkeypatch.setattr(
        pdf_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )

    json_load_count = 0
    original_json_loads = pdf_service.json.loads

    def _counted_json_loads(raw: str):
        nonlocal json_load_count
        json_load_count += 1
        return original_json_loads(raw)

    monkeypatch.setattr(pdf_service.json, "loads", _counted_json_loads)

    first = pdf_service.get_page_text_boxes("asset-cache", 0)
    second = pdf_service.get_page_text_boxes("asset-cache", 0)
    assert json_load_count == 1
    assert first.items[0].fractionRect.x == 0.1
    assert second.items[0].fractionRect.x == 0.1

    _write_content_list_unified(
        asset_dir,
        [{"page_idx": 1, "x": 0.25, "y": 0.2, "width": 0.1, "height": 0.1}],
    )
    third = pdf_service.get_page_text_boxes("asset-cache", 0)
    assert json_load_count == 2
    assert third.items[0].fractionRect.x == 0.25
    assert third.items[0].itemIndex == 1


def test_get_page_text_boxes_missing_file_returns_empty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-missing"
    asset_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        asset_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )
    monkeypatch.setattr(
        pdf_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )

    result = pdf_service.get_page_text_boxes("asset-missing", 3)
    assert result.pageIndex == 3
    assert result.items == []


def test_get_page_text_boxes_generates_missing_unified_file_from_content_list(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-legacy"
    asset_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = asset_dir / "raw.pdf"
    _write_pdf(pdf_path)
    (asset_dir / "content_list.json").write_text(
        json.dumps(
            [
                {
                    "type": "text",
                    "text": "legacy item",
                    "bbox": [13, 26, 65, 78],
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
    monkeypatch.setattr(
        pdf_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )
    expected_unified_path = asset_dir / "content_list_unified.json"

    def _write_generated_unified(_asset_name: str) -> Path:
        _write_content_list_unified(
            asset_dir,
            [{"page_idx": 1, "x": 0.013, "y": 0.026, "width": 0.052, "height": 0.052}],
        )
        return expected_unified_path

    monkeypatch.setattr(pdf_service, "ensure_content_list_unified", _write_generated_unified)

    result = pdf_service.get_page_text_boxes("asset-legacy", 0)

    assert result.pageIndex == 0
    assert len(result.items) == 1
    assert result.items[0].itemIndex == 1
    assert result.items[0].fractionRect.x == pytest.approx(0.013)
    assert result.items[0].fractionRect.y == pytest.approx(0.026)
    assert result.items[0].fractionRect.width == pytest.approx(0.052)
    assert result.items[0].fractionRect.height == pytest.approx(0.052)

    unified_path = asset_dir / "content_list_unified.json"
    assert unified_path.is_file()
    payload = json.loads(unified_path.read_text(encoding="utf-8"))
    assert len(payload) == 1
    assert payload[0]["page_idx"] == 1
    assert payload[0]["x"] == pytest.approx(0.013)
    assert payload[0]["y"] == pytest.approx(0.026)
    assert payload[0]["width"] == pytest.approx(0.052)
    assert payload[0]["height"] == pytest.approx(0.052)


def test_get_page_text_boxes_invalid_json_raises_stable_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-bad-json"
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "content_list_unified.json").write_text("{not valid json", encoding="utf-8")
    monkeypatch.setattr(
        pdf_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )

    with pytest.raises(ApiError) as excinfo:
        pdf_service.get_page_text_boxes("asset-bad-json", 0)

    assert excinfo.value.status_code == 500
    assert excinfo.value.code == "invalid_content_list_unified"


def test_get_page_text_boxes_invalid_page_idx_field_reports_stable_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-bad-page-idx"
    _write_content_list_unified(
        asset_dir,
        [{"page_idx": 0, "x": 0.1, "y": 0.2, "width": 0.3, "height": 0.4}],
    )
    monkeypatch.setattr(
        pdf_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )

    with pytest.raises(ApiError) as excinfo:
        pdf_service.get_page_text_boxes("asset-bad-page-idx", 0)

    assert excinfo.value.status_code == 500
    assert excinfo.value.code == "invalid_content_list_unified"
    assert excinfo.value.details == {"itemIndex": 1, "field": "page_idx"}


def test_get_page_text_boxes_invalid_rect_field_reports_stable_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asset_dir = tmp_path / "asset-bad-rect"
    _write_content_list_unified(
        asset_dir,
        [{"page_idx": 1, "x": "bad", "y": 0.2, "width": 0.3, "height": 0.4}],
    )
    monkeypatch.setattr(
        pdf_service,
        "resolve_asset_dir",
        lambda _asset_name, *, must_exist=True: asset_dir,
    )

    with pytest.raises(ApiError) as excinfo:
        pdf_service.get_page_text_boxes("asset-bad-rect", 0)

    assert excinfo.value.status_code == 500
    assert excinfo.value.code == "invalid_content_list_unified"
    assert excinfo.value.details == {"itemIndex": 1, "field": "x"}


def test_get_page_text_boxes_invalid_page_index_raises_stable_error() -> None:
    with pytest.raises(ApiError) as excinfo:
        pdf_service.get_page_text_boxes("asset-any", -1)

    assert excinfo.value.status_code == 400
    assert excinfo.value.code == "invalid_page_index"


def test_get_pdf_metadata_uses_shared_reference_dpi_page_sizes(monkeypatch: pytest.MonkeyPatch) -> None:
    pdf_path = Path("raw.pdf")
    expected_page_sizes = [
        SizeModel(width=130.0, height=260.0),
        SizeModel(width=140.0, height=280.0),
    ]

    monkeypatch.setattr(pdf_service, "_resolve_pdf_path", lambda _asset_name: pdf_path)
    monkeypatch.setattr(pdf_service, "load_page_sizes_at_reference_dpi", lambda path: expected_page_sizes if path == pdf_path else [])

    result = pdf_service.get_pdf_metadata("asset-a")

    assert result.pageCount == 2
    assert result.pageSizes == expected_page_sizes
