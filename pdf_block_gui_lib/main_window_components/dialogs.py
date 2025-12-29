from __future__ import annotations

import html
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets, QtWebEngineCore, QtWebEngineWidgets

from . import markdown_helper


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


_HISTORY_ACTION_SCHEME = "exocortex-history"
_HISTORY_ACTION_HOST = "action"


class _HistoryListPage(QtWebEngineCore.QWebEnginePage):
    def __init__(self, dialog: "_WebHistoryListDialog") -> None:
        super().__init__(dialog)
        self._dialog = dialog

    def acceptNavigationRequest(  # noqa: N802
        self,
        url: QtCore.QUrl,
        nav_type: QtWebEngineCore.QWebEnginePage.NavigationType,
        is_main_frame: bool,
    ) -> bool:
        if url.scheme() == _HISTORY_ACTION_SCHEME and url.host() == _HISTORY_ACTION_HOST:
            self._dialog.handle_action_url(url)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)


class _WebHistoryListDialog(QtWidgets.QDialog):
    def __init__(
        self,
        title: str,
        *,
        empty_message: str,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumSize(360, 320)
        self.setWindowState(self.windowState() | QtCore.Qt.WindowMaximized)

        self._empty_message = empty_message
        self._base_url = QtCore.QUrl.fromLocalFile(str(Path(__file__).resolve().parent))
        self._selected_paths: list[Path] = []

        self._view = QtWebEngineWidgets.QWebEngineView(self)
        self._page = _HistoryListPage(self)
        self._view.setPage(self._page)
        self._view.setContextMenuPolicy(QtCore.Qt.NoContextMenu)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._view, 1)

    def set_items(self, items: list[tuple[str, str, Path]]) -> None:
        self._selected_paths = []
        self._view.setHtml(self._build_html(items), baseUrl=self._base_url)

    def selected_paths(self) -> list[Path]:
        return list(self._selected_paths)

    def handle_action_url(self, url: QtCore.QUrl) -> None:
        action = url.path().lstrip("/")
        if action == "cancel":
            QtCore.QTimer.singleShot(0, self.reject)
            return
        if action == "accept":
            query = QtCore.QUrlQuery(url)
            raw_paths = query.allQueryItemValues("path")
            if raw_paths:
                selected: list[Path] = []
                for raw_path in raw_paths:
                    if not raw_path:
                        continue
                    decoded = QtCore.QUrl.fromPercentEncoding(raw_path.encode("utf-8"))
                    if decoded:
                        selected.append(Path(decoded))
                self._selected_paths = selected
                QtCore.QTimer.singleShot(0, lambda: QtWidgets.QDialog.accept(self))
                return
            QtCore.QTimer.singleShot(0, self.accept)
            return
        if action == "open":
            query = QtCore.QUrlQuery(url)
            raw_path = query.queryItemValue("path")
            if raw_path:
                decoded = QtCore.QUrl.fromPercentEncoding(raw_path.encode("utf-8"))
                QtCore.QTimer.singleShot(
                    0, lambda p=Path(decoded): self._accept_single_path(p)
                )
                return

    def accept(self) -> None:
        loop = QtCore.QEventLoop(self)
        selected: list[Path] = []

        def _on_result(result: object) -> None:
            try:
                if isinstance(result, list):
                    for item in result:
                        if item:
                            selected.append(Path(str(item)))
            finally:
                loop.quit()

        timer = QtCore.QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)
        timer.start(1000)

        self._view.page().runJavaScript(
            "Array.from(document.querySelectorAll('input.item-check:checked'))"
            ".map(el => el.getAttribute('data-path'))",
            0,
            _on_result,
        )
        loop.exec()
        timer.stop()
        self._selected_paths = selected
        super().accept()

    def _accept_single_path(self, path: Path) -> None:
        self._selected_paths = [path]
        QtWidgets.QDialog.accept(self)

    def _build_html(self, items: list[tuple[str, str, Path]]) -> str:
        head_assets = markdown_helper.katex_assets()

        rows: list[str] = []
        for title, preview, path in items:
            rows.append(
                f"<div class='item' data-path='{html.escape(str(path), quote=True)}'>"
                "<label class='item-label'>"
                f"<input type='checkbox' class='item-check' data-path='{html.escape(str(path), quote=True)}'>"
                "<div class='item-body'>"
                f"<div class='item-title'>{html.escape(title)}</div>"
                f"<div class='item-preview'>{html.escape(preview)}</div>"
                "</div>"
                "</label>"
                "</div>"
            )

        list_body = (
            "".join(rows)
            if rows
            else f"<div class='empty'>{html.escape(self._empty_message)}</div>"
        )

        styles = """
        html, body { height: 100%; }
        body {
            margin: 0;
            padding: 12px;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 15px;
            color: #222;
            background: #f6f7fb;
        }
        .toolbar {
            position: sticky;
            top: 0;
            z-index: 10;
            display: flex;
            gap: 8px;
            align-items: center;
            padding: 10px 0 12px 0;
            background: linear-gradient(to bottom, rgba(246,247,251,0.98), rgba(246,247,251,0.88));
            backdrop-filter: blur(8px);
        }
        .spacer { flex: 1 1 auto; }
        .btn {
            border: 1px solid #d1d5db;
            background: #ffffff;
            color: #111827;
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 14px;
            cursor: pointer;
            user-select: none;
        }
        .btn:hover { background: #f9fafb; }
        .btn.primary {
            background: #2563eb;
            border-color: #1d4ed8;
            color: #ffffff;
        }
        .btn.primary:hover { background: #1d4ed8; }
        .hint {
            color: #6b7280;
            font-size: 13px;
            white-space: nowrap;
        }
        .count {
            color: #374151;
            font-size: 13px;
            white-space: nowrap;
        }
        .item {
            background: #ffffff;
            border: 1px solid #e3e6ef;
            border-radius: 10px;
            margin: 10px 0;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        }
        .item-label {
            display: flex;
            gap: 12px;
            padding: 14px 14px;
            cursor: pointer;
            user-select: none;
        }
        .item-check {
            width: 18px;
            height: 18px;
            margin-top: 2px;
            flex: 0 0 auto;
        }
        .item-body {
            flex: 1 1 auto;
            min-width: 0;
        }
        .item-title {
            font-weight: 700;
            color: #111827;
            margin-bottom: 6px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .item-preview {
            color: #374151;
            line-height: 1.5;
            overflow: hidden;
            text-overflow: ellipsis;
            display: -webkit-box;
            -webkit-box-orient: vertical;
            -webkit-line-clamp: 3;
        }
        .empty {
            color: #6b7280;
            font-size: 16px;
            padding: 24px 6px;
        }
        """

        accept_url = f"{_HISTORY_ACTION_SCHEME}://{_HISTORY_ACTION_HOST}/accept"
        cancel_url = f"{_HISTORY_ACTION_SCHEME}://{_HISTORY_ACTION_HOST}/cancel"
        open_url_prefix = f"{_HISTORY_ACTION_SCHEME}://{_HISTORY_ACTION_HOST}/open?path="

        scripts = """
        <script>
        function navigate(actionUrl) {
            window.location.href = actionUrl;
        }

        function openSelected() {
            const selected = getSelectedPaths();
            if (!selected.length) return;
            const query = selected.map((p) => 'path=' + encodeURIComponent(p)).join('&');
            navigate('__ACCEPT_URL__' + '?' + query);
        }

        function cancelDialog() {
            navigate('__CANCEL_URL__');
        }

        function openSingle(path) {
            if (!path) return;
            navigate('__OPEN_URL_PREFIX__' + encodeURIComponent(path));
        }

        function getSelectedPaths() {
            const selected = [];
            document.querySelectorAll('input.item-check:checked').forEach((el) => {
                const path = el.getAttribute('data-path');
                if (path) selected.push(path);
            });
            return selected;
        }

        function setAll(checked) {
            document.querySelectorAll('input.item-check').forEach((el) => {
                el.checked = checked;
            });
            updateToolbar();
        }

        function updateToolbar() {
            const all = Array.from(document.querySelectorAll('input.item-check'));
            const checked = all.filter((el) => el.checked);
            const allChecked = all.length > 0 && checked.length === all.length;
            const toggleBtn = document.getElementById('toggleAllBtn');
            if (toggleBtn) toggleBtn.textContent = allChecked ? '取消全选' : '全选';
            const countEl = document.getElementById('selectedCount');
            if (countEl) countEl.textContent = all.length ? ('已选 ' + checked.length + '/' + all.length) : '';
        }

        function toggleAll() {
            const all = Array.from(document.querySelectorAll('input.item-check'));
            const checked = all.filter((el) => el.checked);
            const allChecked = all.length > 0 && checked.length === all.length;
            setAll(!allChecked);
        }

        document.addEventListener('change', (e) => {
            if (e && e.target && e.target.classList && e.target.classList.contains('item-check')) {
                updateToolbar();
            }
        });

        document.addEventListener('dblclick', (e) => {
            const target = e && e.target;
            if (!target) return;
            if (target.closest && target.closest('.toolbar')) return;
            if (target.matches && target.matches('input.item-check')) return;
            const item = target.closest && target.closest('.item');
            if (!item) return;
            const path = item.getAttribute('data-path');
            openSingle(path);
        });

        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', updateToolbar);
        } else {
            updateToolbar();
        }
        </script>
        """
        scripts = (
            scripts.replace("__ACCEPT_URL__", accept_url)
            .replace("__CANCEL_URL__", cancel_url)
            .replace("__OPEN_URL_PREFIX__", open_url_prefix)
        )

        toolbar = (
            "<div class='toolbar'>"
            "<button id='toggleAllBtn' class='btn' type='button' onclick='toggleAll()'>全选</button>"
            "<div class='count' id='selectedCount'></div>"
            "<div class='spacer'></div>"
            "<div class='hint'>双击打开单个文件</div>"
            "<button class='btn primary' type='button' onclick='openSelected()'>打开选中</button>"
            "<button class='btn' type='button' onclick='cancelDialog()'>取消</button>"
            "</div>"
        )

        return (
            "<!DOCTYPE html>"
            "<html><head><meta charset='UTF-8'>"
            f"<style>{styles}</style>{head_assets}"
            "</head><body>"
            f"{toolbar}{list_body}"
            f"{scripts}"
            "</body></html>"
        )


class _TutorHistoryDialog(_WebHistoryListDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("History Questions", empty_message="No tutor history found.", parent=parent)


class _TutorFocusDialog(_WebHistoryListDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("History Ask Tutor", empty_message="No tutor focus found.", parent=parent)
        self.setMinimumSize(400, 320)


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
