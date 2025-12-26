from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets


class _ManuscriptDropList(QtWidgets.QListWidget):
    files_dropped = QtCore.Signal(list)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        paths: list[Path] = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.exists():
                    paths.append(path)

        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
            return
        event.ignore()


class _FeynmanManuscriptDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Upload deduction images")
        self.setModal(True)
        self.setMinimumSize(520, 420)
        self.setAcceptDrops(True)

        self._paths: list[Path] = []
        self._icon_size = QtCore.QSize(96, 96)

        hint = QtWidgets.QLabel("Drag & drop images here, or click \"add image\" to pick one.")
        hint.setWordWrap(True)

        self._list = _ManuscriptDropList(self)
        self._list.setIconSize(self._icon_size)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._list.files_dropped.connect(self._add_images)

        self._add_button = QtWidgets.QPushButton("add image", self)
        self._add_button.clicked.connect(self._on_add_clicked)

        self._remove_button = QtWidgets.QPushButton("remove selected", self)
        self._remove_button.clicked.connect(self._remove_selected)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.addWidget(self._add_button)
        toolbar.addWidget(self._remove_button)
        toolbar.addStretch(1)

        self._buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, parent=self
        )
        self._buttons.accepted.connect(self.accept)
        self._buttons.rejected.connect(self.reject)
        ok_button = self._buttons.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_button:
            ok_button.setEnabled(False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addLayout(toolbar)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._buttons)

    def selected_paths(self) -> list[Path]:
        return list(self._paths)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dragMoveEvent(self, event: QtGui.QDragMoveEvent) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event: QtGui.QDropEvent) -> None:  # noqa: N802
        if not event.mimeData().hasUrls():
            event.ignore()
            return

        paths: list[Path] = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.exists():
                    paths.append(path)

        if paths:
            self._add_images(paths)
            event.acceptProposedAction()
            return
        event.ignore()

    def _set_ok_enabled(self) -> None:
        ok_button = self._buttons.button(QtWidgets.QDialogButtonBox.Ok)
        if ok_button:
            ok_button.setEnabled(bool(self._paths))

    def _on_add_clicked(self) -> None:
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select an image of your deduction",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff);;All Files (*.*)",
        )
        if not file_path:
            return
        self._add_images([Path(file_path)])

    @QtCore.Slot(list)
    def _add_images(self, paths: list[Path]) -> None:
        failed: list[str] = []
        for path in paths:
            if path in self._paths:
                continue
            image = QtGui.QImage(str(path))
            if image.isNull():
                failed.append(str(path))
                continue

            pixmap = QtGui.QPixmap.fromImage(image)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(
                    self._icon_size,
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            item = QtWidgets.QListWidgetItem(path.name)
            item.setData(QtCore.Qt.UserRole, str(path))
            item.setToolTip(str(path))
            if not pixmap.isNull():
                item.setIcon(QtGui.QIcon(pixmap))
            self._list.addItem(item)
            self._paths.append(path)

        self._set_ok_enabled()

        if failed:
            QtWidgets.QMessageBox.warning(
                self,
                "Skipped files",
                "Some files could not be loaded as images:\n" + "\n".join(failed[:10]),
            )

    def _remove_selected(self) -> None:
        selected = list(self._list.selectedItems())
        if not selected:
            return

        for item in selected:
            path_raw = item.data(QtCore.Qt.UserRole)
            if path_raw:
                try:
                    path = Path(path_raw)
                except Exception:
                    path = None
                if path and path in self._paths:
                    self._paths.remove(path)
            row = self._list.row(item)
            self._list.takeItem(row)

        self._set_ok_enabled()


class _TutorHistoryDialog(QtWidgets.QDialog):
    def __init__(self, items: list[tuple[str, Path]], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("History Questions")
        self.setModal(True)
        self.setMinimumSize(360, 320)
        self.setWindowState(self.windowState() | QtCore.Qt.WindowMaximized)

        self._list = QtWidgets.QListWidget(self)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        for label, path in items:
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, path)
            self._list.addItem(item)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._list)
        layout.addWidget(buttons)

    def selected_paths(self) -> list[Path]:
        return [
            Path(item.data(QtCore.Qt.UserRole))
            for item in self._list.selectedItems()
            if item.data(QtCore.Qt.UserRole)
        ]


class _TutorFocusDialog(QtWidgets.QDialog):
    def __init__(self, items: list[tuple[str, Path]], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("History Ask Tutor")
        self.setModal(True)
        self.setMinimumSize(400, 320)
        self.setWindowState(self.windowState() | QtCore.Qt.WindowMaximized)

        self._list = QtWidgets.QListWidget(self)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        for label, path in items:
            item = QtWidgets.QListWidgetItem(label)
            item.setData(QtCore.Qt.UserRole, path)
            item.setToolTip(str(path))
            self._list.addItem(item)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._list)
        layout.addWidget(buttons)

    def selected_paths(self) -> list[Path]:
        return [
            Path(item.data(QtCore.Qt.UserRole))
            for item in self._list.selectedItems()
            if item.data(QtCore.Qt.UserRole)
        ]


class _AssetProgressDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Initializing Asset")
        self.setModal(True)
        self.setMinimumSize(400, 250)
        self._log = QtWidgets.QPlainTextEdit(self)
        self._log.setReadOnly(True)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._log)

    @QtCore.Slot(str)
    def append_message(self, message: str) -> None:
        self._log.appendPlainText(message)
        self._log.verticalScrollBar().setValue(self._log.verticalScrollBar().maximum())


class _PreviewDialog(QtWidgets.QDialog):
    def __init__(
        self,
        image_path: Path,
        width: int,
        height: int,
        size_bytes: int,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("img2md input preview")
        self.setModal(True)
        self.setWindowState(self.windowState() | QtCore.Qt.WindowMaximized)

        info_label = QtWidgets.QLabel(
            f"Resolution: {width} x {height}    Size: {self._format_size(size_bytes)}    Path: {image_path}"
        )
        pixmap = QtGui.QPixmap(str(image_path))
        pixmap_label = QtWidgets.QLabel()
        pixmap_label.setAlignment(QtCore.Qt.AlignCenter)
        pixmap_label.setPixmap(pixmap)

        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(pixmap_label)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(info_label)
        layout.addWidget(scroll_area, 1)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"
        kb = size_bytes / 1024
        if kb < 1024:
            return f"{kb:.1f} KB"
        return f"{kb / 1024:.1f} MB"


class _NewAssetDialog(QtWidgets.QDialog):
    def __init__(self, default_name: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Asset")
        self.setModal(True)
        self.setMinimumWidth(360)

        self._name_input = QtWidgets.QLineEdit(default_name, self)
        self._subfolder_input = QtWidgets.QLineEdit(self)
        self._subfolder_input.setPlaceholderText("e.g. folder1/folder2")
        self._compress_switch = QtWidgets.QCheckBox("page compress", self)

        form = QtWidgets.QFormLayout()
        form.addRow("Asset name:", self._name_input)
        form.addRow("Asset sub folder:", self._subfolder_input)
        compress_row = QtWidgets.QHBoxLayout()
        compress_row.addWidget(self._compress_switch)
        compress_row.addStretch(1)
        form.addRow("Options:", compress_row)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def asset_name(self) -> str:
        return self._name_input.text().strip()

    def asset_subfolder(self) -> str:
        return self._subfolder_input.text().strip()

    def compress_enabled(self) -> bool:
        return self._compress_switch.isChecked()


class _AssetSelectionDialog(QtWidgets.QDialog):
    def __init__(
        self,
        assets: list[str],
        title: str,
        *,
        multi: bool,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(320, 400)
        self.setWindowState(self.windowState() | QtCore.Qt.WindowMaximized)

        self._tree = QtWidgets.QTreeWidget(self)
        self._tree.setHeaderHidden(True)
        selection_mode = (
            QtWidgets.QAbstractItemView.ExtendedSelection
            if multi
            else QtWidgets.QAbstractItemView.SingleSelection
        )
        self._tree.setSelectionMode(selection_mode)
        self._tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self._populate_asset_tree(assets)
        self._tree.expandAll()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._tree)
        layout.addWidget(buttons)

    def selected_assets(self) -> list[str]:
        selected: list[str] = []
        for item in self._tree.selectedItems():
            asset_path = item.data(0, QtCore.Qt.UserRole)
            if asset_path:
                selected.append(asset_path)
        return selected

    def _populate_asset_tree(self, assets: list[str]) -> None:
        self._tree.clear()
        root = self._tree.invisibleRootItem()
        for asset in assets:
            parts = [part for part in asset.split("/") if part]
            if not parts:
                continue
            parent = root
            for part in parts:
                child = None
                for idx in range(parent.childCount()):
                    candidate = parent.child(idx)
                    if candidate.text(0) == part:
                        child = candidate
                        break
                if child is None:
                    child = QtWidgets.QTreeWidgetItem([part])
                    parent.addChild(child)
                parent = child
            parent.setData(0, QtCore.Qt.UserRole, asset)
            parent.setToolTip(0, asset)

        def _apply_flags(item: QtWidgets.QTreeWidgetItem) -> None:
            for idx in range(item.childCount()):
                _apply_flags(item.child(idx))
            asset_path = item.data(0, QtCore.Qt.UserRole)
            flags = item.flags()
            if asset_path:
                item.setFlags(flags | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled)
            else:
                item.setFlags(flags & ~QtCore.Qt.ItemIsSelectable)

        for idx in range(root.childCount()):
            _apply_flags(root.child(idx))

    def _on_item_double_clicked(self, item: QtWidgets.QTreeWidgetItem) -> None:
        if item.data(0, QtCore.Qt.UserRole):
            self.accept()


__all__ = [
    "_AssetProgressDialog",
    "_AssetSelectionDialog",
    "_NewAssetDialog",
    "_PreviewDialog",
    "_TutorFocusDialog",
    "_TutorHistoryDialog",
]
