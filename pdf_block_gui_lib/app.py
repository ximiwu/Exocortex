from __future__ import annotations

import os
import sys

def _append_qtwebengine_chromium_flags(*extra_flags: str) -> None:
    existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "").strip()
    parts = existing.split() if existing else []
    for flag in extra_flags:
        if not flag:
            continue
        if flag not in parts:
            parts.append(flag)
    if parts:
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = " ".join(parts)


def _configure_webengine_runtime() -> None:
    raw = os.environ.get("EXOCORTEX_WEBENGINE_DISABLE_GPU", "").strip().lower()
    if raw not in {"1", "true", "yes", "on"}:
        return
    _append_qtwebengine_chromium_flags("--disable-gpu", "--disable-gpu-compositing")


_configure_webengine_runtime()

from PySide6 import QtWidgets

from .main_window import MainWindow


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 800)
    window.showMaximized()
    sys.exit(app.exec())
