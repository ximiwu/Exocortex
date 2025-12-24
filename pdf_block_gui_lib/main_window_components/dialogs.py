from __future__ import annotations

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets


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

