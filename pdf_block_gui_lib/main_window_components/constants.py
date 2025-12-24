from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui

# Layout defaults
DEFAULT_SPLITTER_RATIO_LEFT = 1
DEFAULT_SPLITTER_RATIO_RIGHT = 1
_SPLITTER_SIZE_BASIS = 1200

DEFAULT_RENDER_DPI = 130
MIN_RENDER_DPI = 72
MAX_RENDER_DPI = 1200  # cap to avoid excessive memory usage at very high zoom levels

KATEX_VERSION = "0.16.9"
KATEX_CDN_BASE = f"https://cdn.jsdelivr.net/npm/katex@{KATEX_VERSION}/dist"
_LIB_DIR = Path(__file__).resolve().parents[1]
KATEX_LOCAL_DIR = _LIB_DIR / "static" / "katex"
KATEX_RENDER_SCRIPT = _LIB_DIR / "static" / "katex_render.js"

BLOCK_STYLE_DEFAULT = {
    "pen_color": QtGui.QColor(0, 160, 0),
    "pen_alpha": 100,
    "pen_width": 2,
    "pen_style": QtCore.Qt.DashLine,
    "brush_color": QtGui.QColor(0, 160, 0, 40),
    "brush_alpha": 5,
    "pen_enabled": True,
    "brush_enabled": True,
}
BLOCK_STYLE_GROUP_DEFAULT = {
    "pen_color": QtGui.QColor(147, 112, 219),
    "pen_alpha": 100,
    "pen_width": 2,
    "pen_style": QtCore.Qt.DashLine,
    "brush_color": QtGui.QColor(147, 112, 219, 50),
    "brush_alpha": 5,
    "pen_enabled": True,
    "brush_enabled": True,
}
BLOCK_STYLE_SELECTED = {
    "pen_color": QtGui.QColor(30, 144, 255),
    "pen_alpha": 255,
    "pen_width": 3,
    "pen_style": QtCore.Qt.SolidLine,
    "brush_color": QtGui.QColor(30, 144, 255, 50),
    "brush_alpha": 15,
    "pen_enabled": True,
    "brush_enabled": True,
}
BLOCK_STYLE_HOVER = {
    "pen_color": QtGui.QColor(255, 140, 0),
    "pen_alpha": 255,
    "pen_width": 3,
    "pen_style": QtCore.Qt.SolidLine,
    "brush_color": QtGui.QColor(255, 140, 0, 40),
    "brush_alpha": 10,
    "pen_enabled": True,
    "brush_enabled": True,
}
BLOCK_STYLE_GROUP_HOVER = {
    "pen_color": QtGui.QColor(186, 85, 211),
    "pen_alpha": 255,
    "pen_width": 3,
    "pen_style": QtCore.Qt.SolidLine,
    "brush_color": QtGui.QColor(186, 85, 211, 60),
    "brush_alpha": 10,
    "pen_enabled": True,
    "brush_enabled": True,
}

__all__ = [
    "_SPLITTER_SIZE_BASIS",
    "BLOCK_STYLE_DEFAULT",
    "BLOCK_STYLE_GROUP_DEFAULT",
    "BLOCK_STYLE_GROUP_HOVER",
    "BLOCK_STYLE_HOVER",
    "BLOCK_STYLE_SELECTED",
    "DEFAULT_RENDER_DPI",
    "DEFAULT_SPLITTER_RATIO_LEFT",
    "DEFAULT_SPLITTER_RATIO_RIGHT",
    "KATEX_CDN_BASE",
    "KATEX_LOCAL_DIR",
    "KATEX_RENDER_SCRIPT",
    "KATEX_VERSION",
    "MAX_RENDER_DPI",
    "MIN_RENDER_DPI",
]
