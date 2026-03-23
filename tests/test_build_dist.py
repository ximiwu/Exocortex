from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

import build_dist


def _create_katex_vendor_dir(root: Path) -> Path:
    vendor_dir = root / "vendor" / "katex"
    (vendor_dir / "contrib").mkdir(parents=True, exist_ok=True)
    (vendor_dir / "fonts").mkdir(parents=True, exist_ok=True)
    (vendor_dir / "katex.min.css").write_text("/* css */", encoding="utf-8")
    (vendor_dir / "katex.min.js").write_text("// js", encoding="utf-8")
    (vendor_dir / "contrib" / "auto-render.min.js").write_text("// auto", encoding="utf-8")
    (vendor_dir / "contrib" / "copy-tex.min.js").write_text("// copy", encoding="utf-8")
    (vendor_dir / "fonts" / "KaTeX_Main-Regular.woff2").write_bytes(b"font")
    return vendor_dir


def test_require_katex_runtime_assets_accepts_complete_vendor_bundle(tmp_path: Path) -> None:
    vendor_dir = _create_katex_vendor_dir(tmp_path)
    build_dist.require_katex_runtime_assets(vendor_dir, "KaTeX bundle")


def test_require_katex_runtime_assets_rejects_missing_runtime_file(tmp_path: Path) -> None:
    vendor_dir = _create_katex_vendor_dir(tmp_path)
    (vendor_dir / "katex.min.js").unlink()

    with pytest.raises(FileNotFoundError, match="katex.min.js"):
        build_dist.require_katex_runtime_assets(vendor_dir, "KaTeX bundle")


def test_resolve_stages_honors_skip_flags() -> None:
    args = Namespace(stages=None, skip_frontend=True, skip_installer=True)
    assert [stage.key for stage in build_dist.resolve_stages(args)] == [
        build_dist.STAGE_PACKAGE,
        build_dist.STAGE_VALIDATE,
    ]
