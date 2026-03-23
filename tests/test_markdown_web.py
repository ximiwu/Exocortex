from __future__ import annotations

from pathlib import Path

from exocortex_core import markdown_web
from server.services import markdown as markdown_service


def _create_katex_vendor_dir(base_dir: Path) -> Path:
    vendor_dir = base_dir / "web" / "public" / "vendor" / "katex"
    (vendor_dir / "contrib").mkdir(parents=True, exist_ok=True)
    (vendor_dir / "fonts").mkdir(parents=True, exist_ok=True)
    (vendor_dir / "katex.min.css").write_text("/* css */", encoding="utf-8")
    (vendor_dir / "katex.min.js").write_text("// js", encoding="utf-8")
    (vendor_dir / "contrib" / "auto-render.min.js").write_text("// auto", encoding="utf-8")
    (vendor_dir / "contrib" / "copy-tex.min.js").write_text("// copy", encoding="utf-8")
    (vendor_dir / "fonts" / "KaTeX_Main-Regular.woff2").write_bytes(b"font")
    return vendor_dir


def test_katex_assets_use_checked_in_vendor_bundle(monkeypatch, tmp_path: Path) -> None:
    vendor_dir = _create_katex_vendor_dir(tmp_path)
    monkeypatch.setattr(markdown_web, "repo_root", lambda: tmp_path)

    assets = markdown_web.katex_assets()

    assert vendor_dir.as_uri() in assets
    assert "node_modules" not in assets
    assert "jsdelivr" not in assets


def test_katex_assets_prefer_built_dist_bundle(monkeypatch, tmp_path: Path) -> None:
    public_vendor_dir = _create_katex_vendor_dir(tmp_path)
    dist_vendor_dir = tmp_path / "web" / "dist" / "vendor" / "katex"
    (dist_vendor_dir / "contrib").mkdir(parents=True, exist_ok=True)
    (dist_vendor_dir / "fonts").mkdir(parents=True, exist_ok=True)
    (dist_vendor_dir / "katex.min.css").write_text("/* dist css */", encoding="utf-8")
    (dist_vendor_dir / "katex.min.js").write_text("// dist js", encoding="utf-8")
    (dist_vendor_dir / "contrib" / "auto-render.min.js").write_text("// auto", encoding="utf-8")
    (dist_vendor_dir / "contrib" / "copy-tex.min.js").write_text("// copy", encoding="utf-8")
    (dist_vendor_dir / "fonts" / "KaTeX_Main-Regular.woff2").write_bytes(b"font")
    monkeypatch.setattr(markdown_web, "repo_root", lambda: tmp_path)

    assets = markdown_web.katex_assets()

    assert dist_vendor_dir.as_uri() in assets
    assert public_vendor_dir.as_uri() not in assets


def test_server_markdown_document_uses_root_relative_vendor_assets() -> None:
    _, full_html, _, head_html = markdown_service._render_markdown_document("Inline $x$")

    assert "/vendor/katex/katex.min.css" in head_html
    assert "/vendor/katex/contrib/auto-render.min.js" in full_html
    assert "file:///" not in head_html
    assert "jsdelivr" not in head_html
