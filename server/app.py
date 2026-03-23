from __future__ import annotations

from contextlib import asynccontextmanager
import mimetypes

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from server.api import assets, blocks, health, markdown, pdf, system, tasks
from server.config import API_PREFIX, APP_TITLE, APP_VERSION, WEB_DIST_DIR, WEB_INDEX_PATH
from server.errors import register_exception_handlers
from server.tasking import TaskManager


def _register_frontend_static_mime_types() -> None:
    # Windows can source MIME mappings from the local registry, so force stable
    # module-script types for packaged frontend assets such as the pdf.js worker.
    for suffix, media_type in (
        (".js", "text/javascript"),
        (".mjs", "text/javascript"),
        (".wasm", "application/wasm"),
    ):
        mimetypes.add_type(media_type, suffix, strict=True)
        mimetypes.add_type(media_type, suffix, strict=False)


@asynccontextmanager
async def _lifespan(app: FastAPI):
    app.state.task_manager = TaskManager()
    try:
        yield
    finally:
        app.state.task_manager.close()


def create_app() -> FastAPI:
    _register_frontend_static_mime_types()
    app = FastAPI(title=APP_TITLE, version=APP_VERSION, lifespan=_lifespan)
    register_exception_handlers(app)

    app.include_router(health.router, prefix=API_PREFIX)
    app.include_router(blocks.router, prefix=API_PREFIX)
    app.include_router(assets.router, prefix=API_PREFIX)
    app.include_router(markdown.router, prefix=API_PREFIX)
    app.include_router(pdf.router, prefix=API_PREFIX)
    app.include_router(tasks.router, prefix=API_PREFIX)
    app.include_router(system.router, prefix=API_PREFIX)

    if WEB_INDEX_PATH.is_file():
        app.mount("/", StaticFiles(directory=WEB_DIST_DIR, html=True), name="web")
    else:
        @app.get("/", include_in_schema=False)
        def root() -> HTMLResponse:
            return HTMLResponse(
                """
                <!DOCTYPE html>
                <html lang="en">
                  <head>
                    <meta charset="utf-8" />
                    <title>Exocortex Web</title>
                    <style>
                      body { font-family: Segoe UI, Arial, sans-serif; margin: 40px; color: #1f2937; }
                      .card { max-width: 720px; padding: 24px; border: 1px solid #d1d5db; border-radius: 12px; }
                      a { color: #2563eb; }
                      code { background: #f3f4f6; padding: 2px 6px; border-radius: 6px; }
                    </style>
                  </head>
                  <body>
                    <div class="card">
                      <h1>Exocortex Web API</h1>
                      <p>The backend is running. The frontend bundle is not present yet.</p>
                      <p>Use <a href="/docs">/docs</a> for the interactive API, or build the SPA under <code>web/</code>.</p>
                    </div>
                  </body>
                </html>
                """
            )

    return app


app = create_app()


__all__ = ["app", "create_app"]
