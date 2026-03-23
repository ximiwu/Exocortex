from __future__ import annotations

import asyncio
import mimetypes
from pathlib import Path

import pytest
from starlette.routing import Mount

import server.app as server_app


def test_static_mjs_assets_are_served_with_javascript_mime_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    index_path = dist_dir / "index.html"
    index_path.write_text("<!doctype html><html><body>ok</body></html>\n", encoding="utf-8")

    asset_dir = dist_dir / "assets"
    asset_dir.mkdir()
    worker_path = asset_dir / "pdf.worker.min-test.mjs"
    worker_path.write_text("export default 1;\n", encoding="utf-8")

    mimetypes.add_type("text/plain", ".mjs", strict=True)

    monkeypatch.setattr(server_app, "WEB_DIST_DIR", dist_dir)
    monkeypatch.setattr(server_app, "WEB_INDEX_PATH", index_path)

    app = server_app.create_app()
    web_mount = next(route for route in app.routes if isinstance(route, Mount) and route.name == "web")

    response = asyncio.run(
        web_mount.app.get_response(
            "assets/pdf.worker.min-test.mjs",
            {
                "type": "http",
                "method": "GET",
                "path": "/assets/pdf.worker.min-test.mjs",
                "headers": [],
            },
        )
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
