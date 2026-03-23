from __future__ import annotations

from pathlib import Path

from fastapi.responses import FileResponse
import pytest

from server.api import pdf as pdf_api


def test_pdf_file_endpoint_returns_raw_pdf_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "raw.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n")

    monkeypatch.setattr(pdf_api.pdf_service, "resolve_pdf_path", lambda _asset_name: pdf_path)

    response = pdf_api.get_pdf_file("asset-a")

    assert isinstance(response, FileResponse)
    assert response.media_type == "application/pdf"
    assert Path(response.path) == pdf_path
    assert "raw.pdf" in response.headers.get("content-disposition", "")
