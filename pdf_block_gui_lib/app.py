from __future__ import annotations

import sys

from PySide6 import QtWidgets

from .main_window import MainWindow


def main() -> None:
    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()
    window.resize(1200, 800)
    window.showMaximized()
    sys.exit(app.exec())
