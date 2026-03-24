from __future__ import annotations

import json
from pathlib import Path

import assets_manager
import fitz
import pytest


def _make_pdf(path: Path) -> None:
    document = fitz.open()
    document.new_page(width=72, height=144)
    document.new_page(width=144, height=72)
    document.save(path)
    document.close()


def test_write_unified_content_list_from_top_level_array(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_pdf(pdf_path)
    source_path = tmp_path / "content_list.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "type": "text",
                    "text": "Finite Element Method Simulation of 3D Deformable Solids",
                    "bbox": [13, 26, 65, 78],
                    "page_idx": 0,
                },
                {
                    "type": "text",
                    "text": "Second page block",
                    "bbox": [26, 13, 78, 39],
                    "page_idx": 1,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    target_path = tmp_path / "content_list_unified.json"

    item_count = assets_manager.write_unified_content_list(
        source_path=source_path,
        pdf_path=pdf_path,
        target_path=target_path,
    )

    assert item_count == 2
    payload = json.loads(target_path.read_text(encoding="utf-8"))
    assert payload[0]["text"] == "Finite Element Method Simulation of 3D Deformable Solids"
    assert payload[0]["page_idx"] == 1
    assert "bbox" not in payload[0]
    assert payload[0]["x"] == pytest.approx(0.013)
    assert payload[0]["y"] == pytest.approx(0.026)
    assert payload[0]["width"] == pytest.approx(0.052)
    assert payload[0]["height"] == pytest.approx(0.052)
    assert payload[1]["text"] == "Second page block"
    assert payload[1]["page_idx"] == 2
    assert "bbox" not in payload[1]
    assert payload[1]["x"] == pytest.approx(0.026)
    assert payload[1]["y"] == pytest.approx(0.013)
    assert payload[1]["width"] == pytest.approx(0.052)
    assert payload[1]["height"] == pytest.approx(0.026)


def test_write_unified_content_list_from_items_wrapper(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_pdf(pdf_path)
    source_path = tmp_path / "content_list.json"
    source_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "type": "text",
                        "text": "Wrapped item",
                        "bbox": [13, 52, 39, 104],
                        "page_idx": 0,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    target_path = tmp_path / "content_list_unified.json"

    assets_manager.write_unified_content_list(
        source_path=source_path,
        pdf_path=pdf_path,
        target_path=target_path,
    )

    payload = json.loads(target_path.read_text(encoding="utf-8"))
    assert len(payload) == 1
    assert payload[0]["text"] == "Wrapped item"
    assert payload[0]["page_idx"] == 1
    assert "bbox" not in payload[0]
    assert payload[0]["x"] == pytest.approx(0.013)
    assert payload[0]["y"] == pytest.approx(0.052)
    assert payload[0]["width"] == pytest.approx(0.026)
    assert payload[0]["height"] == pytest.approx(0.052)


def test_write_unified_content_list_preserves_list_entry_fields(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_pdf(pdf_path)
    source_path = tmp_path / "content_list.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "type": "list",
                    "sub_type": "text",
                    "list_items": [
                        "4.6 Free Software for Model Reduction 47",
                        "4.7 Deformation Warping 48",
                    ],
                    "bbox": [29, 16, 93, 32],
                    "page_idx": 0,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    target_path = tmp_path / "content_list_unified.json"

    assets_manager.write_unified_content_list(
        source_path=source_path,
        pdf_path=pdf_path,
        target_path=target_path,
    )

    payload = json.loads(target_path.read_text(encoding="utf-8"))
    assert len(payload) == 1
    assert payload[0]["type"] == "list"
    assert payload[0]["sub_type"] == "text"
    assert payload[0]["list_items"] == [
        "4.6 Free Software for Model Reduction 47",
        "4.7 Deformation Warping 48",
    ]
    assert "text" not in payload[0]
    assert payload[0]["page_idx"] == 1
    assert "bbox" not in payload[0]
    assert payload[0]["x"] == pytest.approx(0.029)
    assert payload[0]["y"] == pytest.approx(0.016)
    assert payload[0]["width"] == pytest.approx(0.064)
    assert payload[0]["height"] == pytest.approx(0.016)


def test_write_unified_content_list_preserves_image_entry_fields(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_pdf(pdf_path)
    source_path = tmp_path / "content_list.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "type": "image",
                    "img_path": "images/example.jpg",
                    "image_caption": [
                        "Figure 4.9: Precomputation utility to compute linear modes."
                    ],
                    "image_footnote": [
                        "BSD license."
                    ],
                    "bbox": [41, 26, 76, 52],
                    "page_idx": 1,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    target_path = tmp_path / "content_list_unified.json"

    assets_manager.write_unified_content_list(
        source_path=source_path,
        pdf_path=pdf_path,
        target_path=target_path,
    )

    payload = json.loads(target_path.read_text(encoding="utf-8"))
    assert len(payload) == 1
    assert payload[0]["type"] == "image"
    assert payload[0]["img_path"] == "images/example.jpg"
    assert payload[0]["image_caption"] == [
        "Figure 4.9: Precomputation utility to compute linear modes."
    ]
    assert payload[0]["image_footnote"] == ["BSD license."]
    assert "text" not in payload[0]
    assert payload[0]["page_idx"] == 2
    assert "bbox" not in payload[0]
    assert payload[0]["x"] == pytest.approx(0.041)
    assert payload[0]["y"] == pytest.approx(0.026)
    assert payload[0]["width"] == pytest.approx(0.035)
    assert payload[0]["height"] == pytest.approx(0.026)


def test_write_unified_content_list_keeps_only_supported_entry_types(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_pdf(pdf_path)
    source_path = tmp_path / "content_list.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "type": "text",
                    "text": "Kept text",
                    "bbox": [13, 26, 65, 78],
                    "page_idx": 0,
                },
                {
                    "type": "abandon",
                    "text": "Dropped entry",
                    "bbox": [20, 20, 40, 40],
                    "page_idx": 0,
                },
                {
                    "type": "page_number",
                    "text": "12",
                    "bbox": [22, 22, 42, 42],
                    "page_idx": 0,
                },
                {
                    "type": "container",
                    "sub_type": "code",
                    "code_body": "print('ok')",
                    "bbox": [26, 13, 78, 39],
                    "page_idx": 1,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    target_path = tmp_path / "content_list_unified.json"

    item_count = assets_manager.write_unified_content_list(
        source_path=source_path,
        pdf_path=pdf_path,
        target_path=target_path,
    )

    payload = json.loads(target_path.read_text(encoding="utf-8"))
    assert item_count == 2
    assert [entry["type"] for entry in payload] == ["text", "container"]
    assert payload[0]["text"] == "Kept text"
    assert payload[1]["sub_type"] == "code"


def test_write_unified_content_list_rejects_out_of_range_page_index(tmp_path: Path) -> None:
    pdf_path = tmp_path / "source.pdf"
    _make_pdf(pdf_path)
    source_path = tmp_path / "content_list.json"
    source_path.write_text(
        json.dumps(
            [
                {
                    "type": "text",
                    "text": "Broken item",
                    "bbox": [13, 26, 65, 78],
                    "page_idx": 2,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="outside the PDF page range"):
        assets_manager.write_unified_content_list(
            source_path=source_path,
            pdf_path=pdf_path,
            target_path=tmp_path / "content_list_unified.json",
        )


def test_save_asset_content_lists_writes_original_and_unified_json(tmp_path: Path) -> None:
    pdf_path = tmp_path / "raw.pdf"
    _make_pdf(pdf_path)
    source_path = tmp_path / "incoming_content_list.json"
    source_payload = [
        {
            "type": "text",
            "text": "Saved beside raw pdf",
            "bbox": [13, 26, 65, 78],
            "page_idx": 0,
        }
    ]
    source_path.write_text(json.dumps(source_payload, ensure_ascii=False), encoding="utf-8")
    asset_dir = tmp_path / "asset"
    asset_dir.mkdir()

    content_list_path, unified_path, item_count = assets_manager.save_asset_content_lists(
        asset_dir=asset_dir,
        source_path=source_path,
        pdf_path=pdf_path,
    )

    assert item_count == 1
    assert content_list_path == asset_dir / "content_list.json"
    assert unified_path == asset_dir / "content_list_unified.json"
    assert json.loads(content_list_path.read_text(encoding="utf-8")) == source_payload
    unified_payload = json.loads(unified_path.read_text(encoding="utf-8"))
    assert unified_payload[0]["text"] == "Saved beside raw pdf"
    assert unified_payload[0]["page_idx"] == 1
    assert "bbox" not in unified_payload[0]
    assert unified_payload[0]["x"] == pytest.approx(0.013)
    assert unified_payload[0]["y"] == pytest.approx(0.026)
    assert unified_payload[0]["width"] == pytest.approx(0.052)
    assert unified_payload[0]["height"] == pytest.approx(0.052)
