from __future__ import annotations

import logging
import math
import os
import stat
import shutil
import re
from pathlib import Path
import tempfile
from typing import Callable, Dict, List, Set

from PySide6 import QtCore, QtGui, QtWidgets, QtWebEngineCore, QtWebEngineWidgets

from assets_manager import convert_pdf_to_images
from ..pymupdf_compat import fitz
from .constants import (
    BLOCK_STYLE_DEFAULT,
    BLOCK_STYLE_GROUP_DEFAULT,
    BLOCK_STYLE_GROUP_HOVER,
    BLOCK_STYLE_HOVER,
    BLOCK_STYLE_SELECTED,
    DEFAULT_RENDER_DPI,
    DEFAULT_SPLITTER_RATIO_LEFT,
    DEFAULT_SPLITTER_RATIO_RIGHT,
    KATEX_CDN_BASE,
    KATEX_LOCAL_DIR,
    KATEX_RENDER_SCRIPT,
    MAX_RENDER_DPI,
    MIN_RENDER_DPI,
    _SPLITTER_SIZE_BASIS,
)
from . import markdown_helper

logger = logging.getLogger(__name__)

from assets_manager import (
    BlockData,
    BlockRecord,
    BlockRect,
    GroupRecord,
    _clean_markdown_file,
    asset_init,
    init_tutor,
    ask_tutor,
    create_group_record,
    delete_group_record,
    integrate,
    group_dive_in,
    get_asset_dir,
    get_asset_pdf_path,
    load_asset_config,
    get_group_data_dir,
    list_assets,
    load_block_data,
    load_group_records,
    next_group_idx,
    save_block_data,
    save_asset_config,
    save_group_record,
)
from ..models import Block
from ..renderer import PdfRenderer
from ..widgets import PdfPageView
from .tasks import (
    _AskTutorTask,
    _AssetInitTask,
    _CompressPreviewTask,
    _CompressTask,
    _FixLatexTask,
    _GroupDiveTask,
    _IntegrateTask,
    _RenderTask,
)
from .dialogs import (
    _AssetProgressDialog,
    _AssetSelectionDialog,
    _NewAssetDialog,
    _PreviewDialog,
    _TutorFocusDialog,
    _TutorHistoryDialog,
)
from .graphics_items import _BlockGraphicsItem


class MainWindow(QtWidgets.QMainWindow):
    _PROMPT_MIN_HEIGHT = 35
    _PROMPT_MAX_HEIGHT = 150

    def __init__(self) -> None:
        super().__init__()
        self._base_title = "Exocortex"
        self._dirty = False
        self.setWindowTitle(self._base_title)

        self._reference_dpi = DEFAULT_RENDER_DPI
        self._max_render_dpi = MAX_RENDER_DPI
        self._renderer = PdfRenderer(dpi=self._reference_dpi)
        self._default_zoom = self._clamp_zoom(self._calculate_default_zoom())
        self._current_page = 0
        self._current_asset_name: str | None = None
        self._next_block_id = 1
        self._blocks: Dict[int, Block] = {}
        self._blocks_by_page: Dict[int, List[int]] = {}
        self._merge_order: List[int] = []
        self._selected_blocks: Set[int] = set()
        self._block_items: Dict[int, _BlockGraphicsItem] = {}
        self._blocks_by_group: Dict[int, Set[int]] = {}
        self._hovered_block_id: int | None = None
        self._hovered_group_idx: int | None = None
        self._next_group_idx = 1
        self._zoom = self._default_zoom
        self._page_count = 0
        self._page_offsets: List[int] = []
        self._page_heights: List[int] = []
        self._page_widths: List[int] = []
        self._page_pixmaps: Dict[int, QtWidgets.QGraphicsPixmapItem] = {}
        self._pages_loaded: Set[int] = set()
        self._pending_renders: Set[int] = set()
        self._desired_pages: Set[int] = set()
        self._render_generation = 0
        self._render_pool = QtCore.QThreadPool(self)
        self._render_pool.setMaxThreadCount(1)
        self._task_pool = QtCore.QThreadPool(self)
        self._task_pool.setMaxThreadCount(1)
        self._ask_pool = QtCore.QThreadPool(self)
        self._ask_pool.setMaxThreadCount(1)
        self._integrate_pool = QtCore.QThreadPool(self)
        self._integrate_pool.setMaxThreadCount(1)
        self._group_dive_pool = QtCore.QThreadPool(self)
        self._group_dive_pool.setMaxThreadCount(1)
        self._fix_latex_pool = QtCore.QThreadPool(self)
        self._fix_latex_pool.setMaxThreadCount(1)
        self._drag_active = False
        self._asset_init_in_progress = False
        self._asset_progress_dialog: _AssetProgressDialog | None = None
        self._current_references_dir: Path | None = None
        self._markdown_views: Dict[Path, QtWebEngineWidgets.QWebEngineView] = {}
        self._markdown_placeholder_index: int | None = None
        self._markdown_warmup_view: QtWebEngineWidgets.QWebEngineView | None = None
        self._markdown_pdf_page: QtWebEngineCore.QWebEnginePage | None = None
        self._markdown_pdf_context: dict[str, object] | None = None
        self._markdown_pdf_temp_path: Path | None = None
        self._group_dive_in_progress = False
        self._ask_in_progress = False
        self._integrate_in_progress = False
        self._fix_latex_in_progress = False
        self._block_action_proxy: QtWidgets.QGraphicsProxyWidget | None = None
        self._block_action_block_id: int | None = None
        self._current_markdown_path: Path | None = None
        self._markdown_clipboard_capture_token = 0
        self._markdown_clipboard_capture_handler: Callable[[], None] | None = None
        self._asset_config_persist_suspended = False
        self._compress_mode_active = False
        self._compress_in_progress = False
        self._compress_preview_in_progress = False
        self._compress_source_pdf_path: Path | None = None
        self._pending_asset_name_for_compress: str | None = None
        self._compress_block_fraction: QtCore.QRectF | None = None
        self._compress_block_items: Dict[int, QtWidgets.QGraphicsRectItem] = {}

        self._order_label = QtWidgets.QLabel("Selection: (none)")
        self._dpi_label = QtWidgets.QLabel()

        self._new_asset_button = QtWidgets.QPushButton("New Asset")
        self._load_asset_button = QtWidgets.QPushButton("Load Asset")
        self._delete_asset_button = QtWidgets.QPushButton("Delete Asset")
        self._page_input = QtWidgets.QSpinBox()
        self._page_input.setMinimum(1)
        self._page_input.setEnabled(False)
        self._page_label = QtWidgets.QLabel("Page: -/-")
        self._show_info_button = QtWidgets.QPushButton("show info")
        self._history_button = QtWidgets.QPushButton("history question")
        self._delete_question_button = QtWidgets.QPushButton("delete question")
        self._tutor_focus_button = QtWidgets.QPushButton("history ask tutor")
        self._integrate_button = QtWidgets.QPushButton("finish_ask")
        self._show_initial_button = QtWidgets.QPushButton("show initial")
        self._fix_latex_button = QtWidgets.QPushButton("fix latex")
        self._crop_head_button = QtWidgets.QPushButton("crop head")
        self._crop_tail_button = QtWidgets.QPushButton("crop tail")
        self._reveal_button = QtWidgets.QPushButton("reveal in file explorer")
        self._reference_buttons = [
            self._show_info_button,
        ]
        self._zoom_in_button = QtWidgets.QPushButton("+")
        self._zoom_out_button = QtWidgets.QPushButton("-")
        self._zoom_reset_button = QtWidgets.QPushButton("Reset")
        self._about_button = QtWidgets.QPushButton("About")
        self._ask_button = QtWidgets.QPushButton("Ask")
        self._prompt_input = QtWidgets.QPlainTextEdit()
        self._prompt_input.setPlaceholderText("Type your question...")
        self._prompt_input.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._prompt_input.textChanged.connect(self._on_prompt_text_changed)
        self._prompt_input.setLineWrapMode(QtWidgets.QPlainTextEdit.WidgetWidth)
        self._prompt_input.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed
        )
        self._prompt_input.installEventFilter(self)
        doc_layout = self._prompt_input.document().documentLayout()
        if doc_layout:
            doc_layout.documentSizeChanged.connect(self._update_prompt_height)
        self._prompt_input.blockCountChanged.connect(lambda _count: self._update_prompt_height())

        self._group_elements_combo = QtWidgets.QComboBox()
        for value in (1, 4, 9, 16, 25, 36):
            self._group_elements_combo.addItem(str(value), value)
        self._group_elements_combo.setCurrentIndex(1)

        self._numbering_checkbox = QtWidgets.QCheckBox("add numbering")
        self._numbering_checkbox.setChecked(True)
        self._badge_position_combo = QtWidgets.QComboBox()
        self._badge_position_combo.addItem("left-top", "top_left")
        self._badge_position_combo.addItem("right-top", "top_right")
        self._badge_position_combo.addItem("left-bottom", "bottom_left")
        self._badge_position_combo.addItem("right-bottom", "bottom_right")

        self._compress_scale_input = QtWidgets.QDoubleSpinBox()
        self._compress_scale_input.setMinimum(0.1)
        self._compress_scale_input.setMaximum(4.0)
        self._compress_scale_input.setDecimals(2)
        self._compress_scale_input.setSingleStep(0.1)
        self._compress_scale_input.setValue(1.0)

        self._compress_result_label = QtWidgets.QLabel("compress result: -")
        self._preview_button = QtWidgets.QPushButton("img2md input preview")
        self._compress_button = QtWidgets.QPushButton("compress")

        compress_bar = QtWidgets.QHBoxLayout()
        compress_bar.setContentsMargins(0, 0, 0, 0)
        compress_bar.addWidget(QtWidgets.QLabel("group_ele_num"))
        compress_bar.addWidget(self._group_elements_combo)
        compress_bar.addWidget(self._numbering_checkbox)
        compress_bar.addWidget(self._badge_position_combo)
        compress_bar.addWidget(QtWidgets.QLabel("compress_ratio"))
        compress_bar.addWidget(self._compress_scale_input)
        compress_bar.addWidget(self._compress_result_label)
        compress_bar.addStretch(1)
        compress_bar.addWidget(self._preview_button)
        compress_bar.addWidget(self._compress_button)
        self._compress_controls = QtWidgets.QWidget()
        self._compress_controls.setLayout(compress_bar)
        self._compress_controls.setVisible(False)

        self._new_asset_button.clicked.connect(self._new_asset)
        self._load_asset_button.clicked.connect(self._load_asset)
        self._delete_asset_button.clicked.connect(self._delete_asset)
        self._page_input.valueChanged.connect(self._on_page_input)
        self._zoom_in_button.clicked.connect(lambda: self._adjust_zoom(0.1))
        self._zoom_out_button.clicked.connect(lambda: self._adjust_zoom(-0.1))
        self._zoom_reset_button.clicked.connect(lambda: self._set_zoom(self._default_zoom))
        self._about_button.clicked.connect(self._show_about_dialog)
        self._show_info_button.clicked.connect(self._show_reference_info)
        self._history_button.clicked.connect(self._show_history_questions)
        self._delete_question_button.clicked.connect(self._delete_current_question)
        self._tutor_focus_button.clicked.connect(self._show_tutor_focus_list)
        self._integrate_button.clicked.connect(self._handle_integrate)
        self._show_initial_button.clicked.connect(self._show_initial_markdown)
        self._fix_latex_button.clicked.connect(self._handle_fix_latex)
        self._crop_head_button.clicked.connect(self._crop_focus_head)
        self._crop_tail_button.clicked.connect(self._crop_focus_tail)
        self._reveal_button.clicked.connect(self._reveal_in_explorer)
        self._ask_button.clicked.connect(self._handle_ask)
        self._group_elements_combo.currentIndexChanged.connect(self._on_group_elements_changed)
        self._compress_scale_input.valueChanged.connect(lambda _v: self._update_compress_result_label())
        self._numbering_checkbox.toggled.connect(self._badge_position_combo.setEnabled)
        self._preview_button.clicked.connect(self._on_preview_clicked)
        self._compress_button.clicked.connect(self._on_compress_clicked)
        for button in self._reference_buttons:
            button.setVisible(False)
        self._history_button.setVisible(False)
        self._delete_question_button.setVisible(False)
        self._tutor_focus_button.setVisible(False)
        self._integrate_button.setVisible(False)
        self._show_initial_button.setVisible(False)
        self._fix_latex_button.setEnabled(False)
        self._crop_head_button.setVisible(False)
        self._crop_tail_button.setVisible(False)
        self._reveal_button.setEnabled(False)

        top_bar = QtWidgets.QHBoxLayout()
        top_bar.addWidget(self._new_asset_button)
        top_bar.addWidget(self._load_asset_button)
        top_bar.addWidget(self._delete_asset_button)
        top_bar.addWidget(QtWidgets.QLabel("Page:"))
        top_bar.addWidget(self._page_input)
        top_bar.addWidget(self._page_label)
        top_bar.addWidget(self._show_info_button)
        top_bar.addWidget(self._reveal_button)
        top_bar.addWidget(self._show_initial_button)
        top_bar.addWidget(self._fix_latex_button)
        top_bar.addWidget(self._history_button)
        top_bar.addWidget(self._delete_question_button)
        top_bar.addWidget(self._tutor_focus_button)
        top_bar.addWidget(self._integrate_button)
        top_bar.addWidget(self._crop_head_button)
        top_bar.addWidget(self._crop_tail_button)
        top_bar.addStretch(1)
        top_bar.addWidget(self._zoom_out_button)
        top_bar.addWidget(self._zoom_in_button)
        top_bar.addWidget(self._zoom_reset_button)
        top_bar.addWidget(self._about_button)

        prompt_bar = QtWidgets.QHBoxLayout()
        prompt_bar.setContentsMargins(0, 0, 0, 0)
        prompt_bar.addWidget(self._prompt_input, 1)
        prompt_bar.addWidget(self._ask_button)
        self._prompt_container = QtWidgets.QWidget()
        self._prompt_container.setLayout(prompt_bar)

        self._scene = QtWidgets.QGraphicsScene(self)
        self._view = PdfPageView()
        self._view.setScene(self._scene)
        self._view.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignTop)
        self._view.selection_finished.connect(self._handle_selection)
        self._view.block_clicked.connect(self._toggle_block_selection)
        self._view.block_right_clicked.connect(self._delete_block)
        self._view.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self._view.drag_started.connect(lambda: setattr(self, "_drag_active", True))
        self._view.drag_finished.connect(lambda: setattr(self, "_drag_active", False))

        self._markdown_tabs = QtWidgets.QTabWidget()
        self._markdown_tabs.setDocumentMode(True)
        self._markdown_tabs.setMovable(True)
        self._markdown_tabs.setTabsClosable(True)
        self._markdown_tabs.tabCloseRequested.connect(self._close_markdown_tab)
        self._markdown_tabs.currentChanged.connect(self._on_markdown_tab_changed)
        self._reset_markdown_tabs()
        QtCore.QTimer.singleShot(0, self._warm_up_markdown_engine)

        self._ask_tutor_action = QtGui.QAction("ask tutor", self)
        self._ask_tutor_action.setShortcut(QtGui.QKeySequence("Ctrl+Alt+T"))
        self._ask_tutor_action.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self._ask_tutor_action.triggered.connect(self._ask_tutor_at_markdown_selection)
        self.addAction(self._ask_tutor_action)

        markdown_container = QtWidgets.QWidget()
        markdown_layout = QtWidgets.QVBoxLayout(markdown_container)
        markdown_layout.setContentsMargins(0, 0, 0, 0)
        markdown_layout.addWidget(self._markdown_tabs)

        pdf_container = QtWidgets.QWidget()
        pdf_layout = QtWidgets.QVBoxLayout(pdf_container)
        pdf_layout.setContentsMargins(0, 0, 0, 0)
        pdf_layout.addWidget(self._view)

        markdown_container.setMinimumWidth(0)
        pdf_container.setMinimumWidth(0)

        self._splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self._splitter.addWidget(markdown_container)
        self._splitter.addWidget(pdf_container)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, False)
        self._splitter.setStretchFactor(0, DEFAULT_SPLITTER_RATIO_LEFT)
        self._splitter.setStretchFactor(1, DEFAULT_SPLITTER_RATIO_RIGHT)

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.addLayout(top_bar)
        layout.addWidget(self._splitter, 1)
        layout.addWidget(self._compress_controls)
        layout.addWidget(self._prompt_container)
        self.setCentralWidget(central)

        self._update_prompt_height()
        self._update_prompt_visibility()

        self.statusBar().addPermanentWidget(self._order_label)
        self.statusBar().addPermanentWidget(self._dpi_label)
        QtCore.QTimer.singleShot(0, self._apply_splitter_ratio)
        self._set_zoom(self._default_zoom)
        self._update_dpi_label()
        self._update_window_title()
        self.statusBar().showMessage("Create or load an asset to start.")

    def _new_asset(self) -> None:
        if self._asset_init_in_progress:
            self.statusBar().showMessage("Asset initialization already in progress.")
            return
        if self._compress_in_progress:
            self.statusBar().showMessage("Page compression already in progress.")
            return
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select PDF/Markdown for new asset",
            "",
            "PDF or Markdown Files (*.pdf *.md);;PDF Files (*.pdf);;Markdown Files (*.md)",
        )
        if not path:
            return
        selected_path = Path(path)
        default_name = selected_path.stem
        dialog = _NewAssetDialog(default_name, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        asset_name = (dialog.asset_name() or default_name).strip()
        subfolder = dialog.asset_subfolder()
        if subfolder:
            normalized = subfolder.replace("\\", "/").strip().strip("/")
            if not normalized:
                subfolder = ""
            else:
                parts = [part for part in normalized.split("/") if part]
                if not parts or any(part in {".", ".."} for part in parts) or ":" in normalized:
                    self.statusBar().showMessage("Asset sub folder is invalid.")
                    return
                asset_name = (Path(*parts) / asset_name).as_posix()
        if not asset_name:
            self.statusBar().showMessage("Asset name is required.")
            return
        self._reset_compress_state(clear_rect=True)
        if dialog.compress_enabled():
            if selected_path.suffix.lower() == ".md":
                self.statusBar().showMessage("Page compress only supports PDF inputs.")
            else:
                self._start_page_compress(selected_path, asset_name)
                return
        self._start_asset_initialization(selected_path, asset_name)

    def _start_asset_initialization(self, source_path: str | Path, asset_name: str) -> None:
        source_path = Path(source_path)
        if source_path.suffix.lower() == ".md":
            self._start_markdown_asset_initialization(source_path, asset_name)
            return
        self._asset_init_in_progress = True
        self._show_asset_progress_dialog()
        if self._asset_progress_dialog:
            self._asset_progress_dialog.append_message(f"Starting asset '{asset_name}'...")
        self.statusBar().showMessage(f"Initializing asset '{asset_name}'...")
        self._start_asset_init_task(source_path, asset_name)

    def _start_asset_init_task(
        self,
        source_path: Path,
        asset_name: str,
        *,
        rendered_pdf_path: Path | None = None,
    ) -> None:
        task = _AssetInitTask(
            str(source_path),
            asset_name,
            str(rendered_pdf_path) if rendered_pdf_path else None,
        )
        task.signals.finished.connect(self._on_asset_init_finished)
        task.signals.failed.connect(self._on_asset_init_failed)
        task.signals.progress.connect(self._on_asset_init_progress)
        self._task_pool.start(task)

    def _start_markdown_asset_initialization(self, markdown_path: Path, asset_name: str) -> None:
        self._asset_init_in_progress = True
        self._show_asset_progress_dialog()
        if self._asset_progress_dialog:
            self._asset_progress_dialog.append_message(f"Rendering markdown for '{asset_name}'...")
        self.statusBar().showMessage(f"Rendering markdown for '{asset_name}'...")

        self._clear_markdown_pdf_state()
        temp_dir = Path(tempfile.mkdtemp(prefix="md_pdf_"))
        pdf_path = temp_dir / "raw.pdf"
        temp_md_path = temp_dir / "input.md"
        self._markdown_pdf_temp_path = pdf_path

        try:
            temp_md_path.write_text(
                markdown_path.read_text(encoding="utf-8-sig"),
                encoding="utf-8",
                newline="\n",
            )
            _clean_markdown_file(temp_md_path)
            content = temp_md_path.read_text(encoding="utf-8")
            html = markdown_helper.render_markdown_content(content)
        except Exception as exc:
            self._on_asset_init_failed(str(exc))
            return

        self._markdown_pdf_context = {
            "asset_name": asset_name,
            "markdown_path": markdown_path,
            "pdf_path": pdf_path,
        }
        page = QtWebEngineCore.QWebEnginePage(self)
        self._markdown_pdf_page = page
        page.loadFinished.connect(self._on_markdown_pdf_load_finished)
        page.pdfPrintingFinished.connect(self._on_markdown_pdf_print_finished)
        base_url = QtCore.QUrl.fromLocalFile(str(markdown_path.parent))
        page.setHtml(html, baseUrl=base_url)

    def _clear_markdown_pdf_state(self) -> None:
        if self._markdown_pdf_page:
            try:
                self._markdown_pdf_page.loadFinished.disconnect(self._on_markdown_pdf_load_finished)
            except Exception:
                pass
            try:
                self._markdown_pdf_page.pdfPrintingFinished.disconnect(self._on_markdown_pdf_print_finished)
            except Exception:
                pass
        self._markdown_pdf_page = None
        self._markdown_pdf_context = None

    def _cleanup_markdown_pdf_temp(self) -> None:
        temp_path = self._markdown_pdf_temp_path
        if not temp_path:
            return
        self._markdown_pdf_temp_path = None
        try:
            temp_dir = temp_path.parent
            if temp_dir.is_dir() and temp_dir.name.startswith("md_pdf_"):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _on_markdown_pdf_load_finished(self, ok: bool) -> None:
        if not ok:
            self._clear_markdown_pdf_state()
            self._on_asset_init_failed("Failed to load markdown for PDF rendering.")
            return
        QtCore.QTimer.singleShot(800, self._print_markdown_pdf)

    def _print_markdown_pdf(self) -> None:
        if not self._markdown_pdf_page or not self._markdown_pdf_context:
            return
        pdf_path = self._markdown_pdf_context["pdf_path"]
        if isinstance(pdf_path, Path):
            self._markdown_pdf_page.printToPdf(str(pdf_path))

    def _on_markdown_pdf_print_finished(self, path: str, success: bool) -> None:
        context = self._markdown_pdf_context
        if not context:
            return
        asset_name = context["asset_name"]
        markdown_path = context["markdown_path"]
        pdf_path = Path(path) if path else context["pdf_path"]

        if not success or not isinstance(pdf_path, Path) or not pdf_path.is_file():
            self._clear_markdown_pdf_state()
            self._on_asset_init_failed("Failed to render markdown to PDF.")
            return

        if self._asset_progress_dialog:
            self._asset_progress_dialog.append_message("Markdown rendered to PDF.")
            self._asset_progress_dialog.append_message(f"Starting asset '{asset_name}'...")
        self.statusBar().showMessage(f"Initializing asset '{asset_name}'...")
        if isinstance(markdown_path, Path):
            self._start_asset_init_task(markdown_path, asset_name, rendered_pdf_path=pdf_path)
        self._clear_markdown_pdf_state()

    def _on_asset_init_finished(self, asset_name: str) -> None:
        self._asset_init_in_progress = False
        self._close_asset_progress_dialog(success=True, message=f"Asset '{asset_name}' initialized.")
        self.statusBar().showMessage(f"Asset '{asset_name}' initialized.")
        self._open_asset(asset_name)
        self._cleanup_markdown_pdf_temp()

    def _on_asset_init_failed(self, error: str) -> None:
        self._asset_init_in_progress = False
        self._close_asset_progress_dialog(success=False, message=f"Asset initialization failed: {error}")
        self.statusBar().showMessage(f"Asset initialization failed: {error}")
        self._cleanup_markdown_pdf_temp()

    def _on_asset_init_progress(self, message: str) -> None:
        if self._asset_progress_dialog:
            self._asset_progress_dialog.append_message(message)

    def _start_page_compress(self, pdf_path: Path, asset_name: str) -> None:
        self._clear_current_asset_state()
        self._compress_mode_active = True
        self._compress_in_progress = False
        self._compress_preview_in_progress = False
        self._compress_source_pdf_path = pdf_path
        self._pending_asset_name_for_compress = asset_name
        self._clear_compress_overlays(reset_rect=True)
        self._group_elements_combo.setCurrentIndex(1)
        self._compress_scale_input.setValue(1.0)
        self._numbering_checkbox.setChecked(True)
        self._badge_position_combo.setEnabled(self._numbering_checkbox.isChecked())
        self._compress_controls.setVisible(True)
        self._compress_button.setEnabled(True)
        self._preview_button.setEnabled(True)
        self._set_dirty(False)
        self._update_window_title()
        if not self._load_pdf_for_compress(pdf_path):
            self._reset_compress_state(clear_rect=True)
            return
        self._update_compress_result_label()
        self.statusBar().showMessage("Select compress block (applies to all pages).")

    def _load_pdf_for_compress(self, pdf_path: Path) -> bool:
        self._renderer.close()
        try:
            self._renderer.open(str(pdf_path))
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to open PDF: {exc}")
            return False
        self._renderer.set_dpi(self._reference_dpi)
        self._update_dpi_label()
        self._render_generation += 1
        self._page_count = self._renderer.page_count
        self._update_page_metrics()
        self._current_page = 0
        self._reset_blocks()
        self._page_input.setEnabled(True)
        self._page_input.setMaximum(self._page_count)
        self._page_input.setValue(1)
        self._set_zoom(self._default_zoom)
        self._rebuild_scene(center_on_current=True)
        self._update_compress_result_label()
        return True

    def _current_group_elements(self) -> int:
        data = self._group_elements_combo.currentData()
        try:
            return max(1, int(data))
        except Exception:
            return 1

    def _on_group_elements_changed(self, _index: int) -> None:
        self._update_compress_result_label()

    def _update_compress_result_label(self) -> None:
        ratio = self._current_group_elements()
        if self._page_count > 0 and ratio > 0:
            reduced = math.ceil(self._page_count / ratio)
            self._compress_result_label.setText(f"compress result: {reduced}")
            return
        self._compress_result_label.setText("compress result: -")

    def _clear_compress_overlays(self, *, reset_rect: bool) -> None:
        for item in list(self._compress_block_items.values()):
            try:
                scene = item.scene()
                if scene:
                    scene.removeItem(item)
            except RuntimeError:
                pass
        self._compress_block_items.clear()
        if reset_rect:
            self._compress_block_fraction = None

    def _handle_compress_selection(self, scene_rect: QtCore.QRectF) -> None:
        if self._compress_in_progress:
            return
        if not self._page_offsets or not self._page_heights:
            return
        center_y = scene_rect.center().y()
        page_index = self._page_at_y(center_y)
        if page_index is None:
            self.statusBar().showMessage("Selection not within a page.")
            return
        y_offset = self._page_offsets[page_index]
        local_rect = QtCore.QRectF(
            scene_rect.x(),
            scene_rect.y() - y_offset,
            scene_rect.width(),
            scene_rect.height(),
        )
        normalized = local_rect.normalized()
        if normalized.width() <= 0 or normalized.height() <= 0:
            self.statusBar().showMessage("Compress block is empty.")
            return
        page_width = self._page_widths[page_index] if page_index < len(self._page_widths) else 0
        page_height = self._page_heights[page_index] if page_index < len(self._page_heights) else 0
        if page_width <= 0 or page_height <= 0:
            self.statusBar().showMessage("Page size unavailable for compression.")
            return
        self._compress_block_fraction = QtCore.QRectF(
            normalized.x() / page_width,
            normalized.y() / page_height,
            normalized.width() / page_width,
            normalized.height() / page_height,
        )
        self._clear_compress_overlays(reset_rect=False)
        for page in list(self._pages_loaded):
            self._render_compress_overlay_for_page(page)
        self.statusBar().showMessage("Compress block updated for all pages.")

    def _render_compress_overlay_for_page(self, page_index: int) -> None:
        item = self._compress_block_items.pop(page_index, None)
        if item:
            try:
                scene = item.scene()
                if scene:
                    scene.removeItem(item)
            except RuntimeError:
                pass
        if not self._compress_mode_active or not self._compress_block_fraction:
            return
        if page_index >= len(self._page_offsets):
            return
        y_offset = self._page_offsets[page_index]
        page_width = self._page_widths[page_index] if page_index < len(self._page_widths) else 0
        page_height = self._page_heights[page_index] if page_index < len(self._page_heights) else 0
        if page_width <= 0 or page_height <= 0:
            return
        frac = self._compress_block_fraction.normalized()
        current_rect = QtCore.QRectF(
            frac.x() * page_width,
            frac.y() * page_height,
            frac.width() * page_width,
            frac.height() * page_height,
        )
        translated = QtCore.QRectF(
            current_rect.x(),
            current_rect.y() + y_offset,
            current_rect.width(),
            current_rect.height(),
        )
        pen = QtGui.QPen(QtGui.QColor(220, 120, 0))
        pen.setWidth(2)
        pen.setStyle(QtCore.Qt.DashLine)
        brush = QtGui.QBrush(QtGui.QColor(220, 120, 0, 40))
        overlay = self._scene.addRect(translated, pen, brush)
        overlay.setZValue(6)
        self._compress_block_items[page_index] = overlay

    def _compress_fraction_rect(self) -> tuple[float, float, float, float]:
        if not self._compress_block_fraction:
            raise ValueError("Compress block is not set.")
        rect = self._compress_block_fraction.normalized()
        return (rect.left(), rect.top(), rect.right(), rect.bottom())

    def _on_preview_clicked(self) -> None:
        if not self._compress_mode_active:
            self.statusBar().showMessage("Enable page compress first.")
            return
        if self._compress_in_progress:
            self.statusBar().showMessage("Page compression already in progress.")
            return
        if self._compress_preview_in_progress:
            self.statusBar().showMessage("Preview already in progress.")
            return
        if not self._compress_block_fraction:
            self.statusBar().showMessage("Select a compress block first.")
            return
        if not self._compress_source_pdf_path:
            self.statusBar().showMessage("Missing compress context.")
            return
        fraction_rect = self._compress_fraction_rect()
        ratio = self._current_group_elements()
        if ratio <= 0:
            self.statusBar().showMessage("group_ele_num must be positive.")
            return
        compress_scale = float(self._compress_scale_input.value())
        if compress_scale <= 0:
            self.statusBar().showMessage("compress_ratio must be positive.")
            return
        draw_badge = self._numbering_checkbox.isChecked()
        badge_position = self._badge_position_combo.currentData() or "top_left"

        output_dir = Path(tempfile.mkdtemp(prefix="compress_preview_"))
        task = _CompressPreviewTask(
            self._compress_source_pdf_path,
            fraction_rect,
            ratio,
            output_dir,
            compress_scale=compress_scale,
            draw_badge=draw_badge,
            badge_position=badge_position,
        )
        task.signals.finished.connect(self._on_preview_finished)
        task.signals.failed.connect(self._on_preview_failed)
        self._compress_preview_in_progress = True
        self._preview_button.setEnabled(False)
        self.statusBar().showMessage("Generating img2md preview...")
        self._task_pool.start(task)

    @QtCore.Slot(str, int, int, int)
    def _on_preview_finished(self, image_path: str, width: int, height: int, size_bytes: int) -> None:
        self._compress_preview_in_progress = False
        self._preview_button.setEnabled(not self._compress_in_progress)
        dialog = _PreviewDialog(Path(image_path), width, height, size_bytes, parent=self)
        dialog.exec()
        size_text = _PreviewDialog._format_size(size_bytes)
        self.statusBar().showMessage(f"Preview ready: {width} x {height}, {size_text}.")

    @QtCore.Slot(str)
    def _on_preview_failed(self, error: str) -> None:
        self._compress_preview_in_progress = False
        self._preview_button.setEnabled(not self._compress_in_progress)
        self.statusBar().showMessage(f"Preview failed: {error}")

    def _on_compress_clicked(self) -> None:
        if not self._compress_mode_active:
            self.statusBar().showMessage("Enable page compress first.")
            return
        if self._compress_in_progress:
            self.statusBar().showMessage("Page compression already in progress.")
            return
        if self._compress_preview_in_progress:
            self.statusBar().showMessage("Preview already in progress.")
            return
        if self._asset_init_in_progress:
            self.statusBar().showMessage("Asset initialization already in progress.")
            return
        if not self._compress_block_fraction:
            self.statusBar().showMessage("Select a compress block first.")
            return
        if not self._compress_source_pdf_path or not self._pending_asset_name_for_compress:
            self.statusBar().showMessage("Missing compress context.")
            return
        fraction_rect = self._compress_fraction_rect()
        ratio = self._current_group_elements()
        if ratio <= 0:
            self.statusBar().showMessage("group_ele_num must be positive.")
            return
        compress_scale = float(self._compress_scale_input.value())
        if compress_scale <= 0:
            self.statusBar().showMessage("compress_ratio must be positive.")
            return
        draw_badge = self._numbering_checkbox.isChecked()
        badge_position = self._badge_position_combo.currentData() or "top_left"
        output_path = get_asset_pdf_path(self._pending_asset_name_for_compress)
        self._compress_in_progress = True
        self._compress_button.setEnabled(False)
        self._preview_button.setEnabled(False)
        self.statusBar().showMessage("Compressing pages...")
        task = _CompressTask(
            self._compress_source_pdf_path,
            fraction_rect,
            ratio,
            output_path,
            compress_scale=compress_scale,
            draw_badge=draw_badge,
            badge_position=badge_position,
        )
        task.signals.finished.connect(self._on_compress_finished)
        task.signals.failed.connect(self._on_compress_failed)
        self._task_pool.start(task)

    @QtCore.Slot(str)
    def _on_compress_finished(self, output_path: str) -> None:
        asset_name = self._pending_asset_name_for_compress
        self._compress_in_progress = False
        self._compress_button.setEnabled(True)
        self._preview_button.setEnabled(True)
        self._reset_compress_state(clear_rect=True)
        if not asset_name:
            self.statusBar().showMessage("Page compression finished, but asset name is missing.")
            return
        self.statusBar().showMessage("Compression finished. Initializing asset...")
        self._start_asset_initialization(output_path, asset_name)

    @QtCore.Slot(str)
    def _on_compress_failed(self, error: str) -> None:
        self._compress_in_progress = False
        self._compress_button.setEnabled(True)
        self._preview_button.setEnabled(True)
        self.statusBar().showMessage(f"Page compression failed: {error}")

    def _reset_compress_state(self, *, clear_rect: bool) -> None:
        self._compress_mode_active = False
        self._compress_in_progress = False
        self._compress_preview_in_progress = False
        self._compress_source_pdf_path = None
        self._pending_asset_name_for_compress = None
        self._clear_compress_overlays(reset_rect=clear_rect)
        self._compress_controls.setVisible(False)
        self._compress_button.setEnabled(True)
        self._preview_button.setEnabled(True)
        if clear_rect:
            self._compress_result_label.setText("compress result: -")
            self._compress_block_fraction = None
            self._group_elements_combo.setCurrentIndex(1)
            self._compress_scale_input.setValue(1.0)
            self._numbering_checkbox.setChecked(True)
            self._badge_position_combo.setEnabled(self._numbering_checkbox.isChecked())
        else:
            self._update_compress_result_label()

    def _select_assets(
        self, *, title: str, multi: bool, empty_message: str
    ) -> list[str] | None:
        assets = list_assets()
        if not assets:
            self.statusBar().showMessage(empty_message)
            return None
        dialog = _AssetSelectionDialog(assets, title, multi=multi, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return None
        return dialog.selected_assets()

    def _load_asset(self) -> None:
        if self._compress_in_progress:
            self.statusBar().showMessage("Page compression already in progress.")
            return
        if self._compress_mode_active:
            self.statusBar().showMessage("Finish page compress first.")
            return
        selected = self._select_assets(
            title="Load Asset", multi=False, empty_message="No assets found. Create a new asset first."
        )
        if selected is None:
            return
        if not selected:
            self.statusBar().showMessage("No asset selected.")
            return
        self._open_asset(selected[0])

    def _delete_asset(self) -> None:
        if self._compress_in_progress:
            self.statusBar().showMessage("Page compression already in progress.")
            return
        if self._compress_mode_active:
            self.statusBar().showMessage("Finish page compress first.")
            return
        selected = self._select_assets(
            title="Delete Asset", multi=True, empty_message="No assets found to delete."
        )
        if selected is None:
            return
        if not selected:
            self.statusBar().showMessage("No assets selected for deletion.")
            return
        names = ", ".join(selected)
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Delete Assets",
            f"Delete the selected asset(s)?\n{names}",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        deleting_current = self._current_asset_name in selected
        if deleting_current:
            self._clear_current_asset_state()

        failures: list[str] = []
        for asset_name in selected:
            error = self._remove_asset_directory(asset_name)
            if error:
                failures.append(error)

        if failures:
            self.statusBar().showMessage(f"Failed to delete: {'; '.join(failures)}")
        else:
            self.statusBar().showMessage("Selected assets deleted.")

    def _notify_incomplete_asset(self, asset_name: str, details: str) -> None:
        message = f"Asset '{asset_name}' is incomplete: {details}"
        QtWidgets.QMessageBox.warning(self, "Asset Incomplete", message)
        self.statusBar().showMessage(message)

    def _validate_asset_files(self, asset_name: str) -> Path | None:
        pdf_path = get_asset_pdf_path(asset_name)
        if not pdf_path.is_file():
            self._notify_incomplete_asset(asset_name, f"Missing raw PDF at {pdf_path}.")
            return None

        references_dir = pdf_path.parent / "references"
        required_refs = {
            "background.md": references_dir / "background.md",
            "concept.md": references_dir / "concept.md",
            "formula.md": references_dir / "formula.md",
        }
        missing = [name for name, path in required_refs.items() if not path.is_file()]
        if missing:
            missing_list = ", ".join(missing)
            self._notify_incomplete_asset(asset_name, f"Missing reference file(s): {missing_list}")
            return None

        return pdf_path

    def _open_asset(self, asset_name: str) -> None:
        self._persist_asset_ui_state()
        self._reset_compress_state(clear_rect=True)
        pdf_path = self._validate_asset_files(asset_name)
        if not pdf_path:
            return
        self._renderer.close()
        try:
            self._renderer.open(str(pdf_path))
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to open asset: {exc}")
            return
        self._renderer.set_dpi(self._reference_dpi)
        self._update_dpi_label()

        self._current_references_dir = pdf_path.parent / "references"
        self._asset_config_persist_suspended = True
        try:
            self._reset_markdown_tabs()
            self._set_reference_buttons_visible(True)
            self._current_asset_name = asset_name
            self._update_window_title()
            self._render_generation += 1
            self._page_count = self._renderer.page_count
            self._update_page_metrics()
            self._current_page = 0
            self._reset_blocks()
            self._page_input.setEnabled(True)
            self._page_input.setMaximum(self._page_count)
            self._page_input.setValue(1)
            self._load_blocks_from_storage()
            self._set_zoom(self._default_zoom)
            self._rebuild_scene(center_on_current=True)
            self._restore_asset_ui_state(asset_name)
        finally:
            self._asset_config_persist_suspended = False
        self._persist_asset_ui_state()
        self.statusBar().showMessage(f"Loaded asset: {asset_name}")

    def _reset_blocks(self) -> None:
        self._blocks.clear()
        self._blocks_by_page.clear()
        self._merge_order.clear()
        self._selected_blocks.clear()
        self._block_items.clear()
        self._blocks_by_group.clear()
        self._hovered_block_id = None
        self._hovered_group_idx = None
        self._hide_block_action_overlay()
        self._page_pixmaps.clear()
        self._pages_loaded.clear()
        self._pending_renders.clear()
        self._desired_pages.clear()
        self._scene.clear()
        self._clear_compress_overlays(reset_rect=False)
        self._next_block_id = 1
        self._next_group_idx = 1
        self._update_merge_order_label()

    def _reset_markdown_tabs(self) -> None:
        self._markdown_tabs.clear()
        self._markdown_views.clear()
        self._markdown_placeholder_index = None
        self._markdown_tabs.setTabsClosable(False)
        self._set_current_markdown_path(None)
        self._show_markdown_placeholder()

    def _warm_up_markdown_engine(self) -> None:
        """Initialize WebEngine early to avoid first-open flicker."""
        if self._markdown_warmup_view:
            return
        view = QtWebEngineWidgets.QWebEngineView(self)
        view.setAttribute(QtCore.Qt.WA_DontShowOnScreen, True)
        view.setUpdatesEnabled(False)
        view.hide()
        view.setHtml("<html><body></body></html>")
        self._markdown_warmup_view = view

    def _clear_current_asset_state(self) -> None:
        self._persist_asset_ui_state()
        self._reset_compress_state(clear_rect=True)
        self._renderer.close()
        self._current_asset_name = None
        self._current_references_dir = None
        self._render_generation += 1
        self._page_count = 0
        self._page_offsets = []
        self._page_heights = []
        self._page_widths = []
        self._current_page = 0
        self._reset_blocks()
        self._reset_markdown_tabs()
        self._set_reference_buttons_visible(False)
        self._page_input.setEnabled(False)
        self._page_input.blockSignals(True)
        self._page_input.setValue(1)
        self._page_input.blockSignals(False)
        self._page_label.setText("Page: -/-")

    def _remove_asset_directory(self, asset_name: str) -> str | None:
        asset_dir = get_asset_pdf_path(asset_name).parent
        if not asset_dir.exists():
            return None

        def _on_error(func, path, _exc_info) -> None:
            try:
                os.chmod(path, stat.S_IWRITE)
                func(path)
            except Exception as exc:  # pragma: no cover - GUI runtime path
                raise exc

        try:
            shutil.rmtree(asset_dir, onerror=_on_error)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            return f"{asset_name}: {exc}"

        if asset_dir.exists():
            return f"{asset_name}: directory still exists after delete"
        return None

    def _clear_blocks_only(self) -> None:
        for item in self._block_items.values():
            scene = item.scene()
            if scene:
                scene.removeItem(item)
        self._blocks.clear()
        self._blocks_by_page.clear()
        self._merge_order.clear()
        self._selected_blocks.clear()
        self._block_items.clear()
        self._next_block_id = 1
        self._blocks_by_group.clear()
        self._hovered_block_id = None
        self._hovered_group_idx = None
        self._next_group_idx = 1
        self._hide_block_action_overlay()
        self._update_merge_order_label()

    def _show_asset_progress_dialog(self) -> None:
        if self._asset_progress_dialog:
            return
        self._asset_progress_dialog = _AssetProgressDialog(self)
        self._asset_progress_dialog.show()

    def _close_asset_progress_dialog(self, *, success: bool, message: str) -> None:
        if self._asset_progress_dialog:
            self._asset_progress_dialog.append_message(message)
            self._asset_progress_dialog.accept()
            self._asset_progress_dialog = None

    def _set_reference_buttons_visible(self, visible: bool) -> None:
        for button in self._reference_buttons:
            button.setVisible(visible)

    def _show_markdown_placeholder(self) -> None:
        if self._markdown_placeholder_index is not None:
            return
        placeholder = QtWidgets.QLabel("Load an asset and open a reference to view markdown.")
        placeholder.setAlignment(QtCore.Qt.AlignCenter)
        placeholder.setWordWrap(True)
        index = self._markdown_tabs.addTab(placeholder, "Markdown")
        tab_bar = self._markdown_tabs.tabBar()
        tab_bar.setTabButton(index, QtWidgets.QTabBar.LeftSide, None)
        tab_bar.setTabButton(index, QtWidgets.QTabBar.RightSide, None)
        self._markdown_placeholder_index = index

    def _remove_markdown_placeholder(self) -> None:
        if self._markdown_placeholder_index is None:
            return
        self._markdown_tabs.removeTab(self._markdown_placeholder_index)
        self._markdown_placeholder_index = None
        self._set_current_markdown_path(self._resolve_current_markdown_path())

    def _on_prompt_text_changed(self) -> None:
        self._update_prompt_height()
        QtCore.QTimer.singleShot(0, self._update_prompt_height)

    def _update_prompt_height(self) -> None:
        doc = self._prompt_input.document()
        last_block = doc.lastBlock()
        if last_block.isValid():
            last_geometry = self._prompt_input.blockBoundingGeometry(last_block)
            doc_height = float(last_geometry.y() + last_geometry.height())
        else:
            doc_height = 0.0

        doc_margin_height = float(doc.documentMargin()) * 2.0
        margins = self._prompt_input.contentsMargins()
        frame = int(self._prompt_input.frameWidth()) * 2
        needed_height = doc_height + doc_margin_height + margins.top() + margins.bottom() + frame

        if needed_height < self._PROMPT_MIN_HEIGHT:
            new_height = self._PROMPT_MIN_HEIGHT
            self._prompt_input.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        elif needed_height > self._PROMPT_MAX_HEIGHT:
            new_height = self._PROMPT_MAX_HEIGHT
            self._prompt_input.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        else:
            new_height = int(math.ceil(needed_height))
            self._prompt_input.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self._prompt_input.setFixedHeight(int(new_height))

    def _set_current_markdown_path(self, path: Path | None) -> None:
        self._current_markdown_path = path
        self._update_prompt_visibility()
        self._update_history_button_visibility()
        self._update_delete_question_visibility()
        self._update_initial_button_visibility()
        self._update_focus_crop_visibility()
        self._update_tutor_focus_visibility()
        self._update_reveal_button_state()
        self._update_fix_latex_button_state()
        self._persist_asset_ui_state()

    def _serialize_asset_markdown_path(self, asset_name: str, path: Path) -> str:
        try:
            asset_dir = get_asset_dir(asset_name).resolve()
            resolved = path.resolve()
            return resolved.relative_to(asset_dir).as_posix()
        except Exception:
            return str(path)

    def _deserialize_asset_markdown_path(self, asset_name: str, raw: object) -> Path | None:
        if not isinstance(raw, str) or not raw.strip():
            return None
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = get_asset_dir(asset_name) / candidate
        try:
            candidate = candidate.resolve()
        except Exception:
            pass
        if candidate.is_file():
            return candidate
        return None

    def _open_markdown_paths(self) -> list[Path]:
        paths: list[Path] = []
        for index in range(self._markdown_tabs.count()):
            widget = self._markdown_tabs.widget(index)
            if not isinstance(widget, QtWebEngineWidgets.QWebEngineView):
                continue
            markdown_path = self._markdown_path_for_view(widget)
            if not markdown_path:
                continue
            try:
                resolved = markdown_path.resolve()
            except Exception:
                resolved = markdown_path
            if resolved.is_file():
                paths.append(resolved)
        return paths

    def _persist_asset_ui_state(self) -> None:
        if self._asset_config_persist_suspended:
            return
        asset_name = self._current_asset_name
        if not asset_name:
            return
        config: dict[str, object] = {"zoom": float(self._zoom)}
        config["open_markdown_paths"] = [
            self._serialize_asset_markdown_path(asset_name, path)
            for path in self._open_markdown_paths()
        ]
        if self._current_markdown_path:
            config["markdown_path"] = self._serialize_asset_markdown_path(asset_name, self._current_markdown_path)
        else:
            config["markdown_path"] = None
        try:
            save_asset_config(asset_name, config)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            logger.warning("Failed to save asset config for '%s': %s", asset_name, exc)

    def _restore_asset_ui_state(self, asset_name: str) -> None:
        config = load_asset_config(asset_name)
        if not config:
            return

        zoom_raw = config.get("zoom")
        try:
            zoom_value = float(zoom_raw) if zoom_raw is not None else None
        except Exception:
            zoom_value = None
        if zoom_value is not None:
            self._set_zoom(zoom_value)

        active_markdown = self._deserialize_asset_markdown_path(asset_name, config.get("markdown_path"))

        open_markdown_paths: list[Path] = []
        open_raw = config.get("open_markdown_paths")
        if isinstance(open_raw, list):
            for item in open_raw:
                candidate = self._deserialize_asset_markdown_path(asset_name, item)
                if candidate and candidate not in open_markdown_paths:
                    open_markdown_paths.append(candidate)

        if active_markdown and active_markdown not in open_markdown_paths:
            open_markdown_paths.append(active_markdown)

        for path in open_markdown_paths:
            if active_markdown and path == active_markdown:
                continue
            self._open_markdown_file(path)
        if active_markdown:
            self._open_markdown_file(active_markdown)

    def _update_prompt_visibility(self) -> None:
        visible = False
        if self._current_markdown_path:
            visible = self._tutor_context_from_markdown(self._current_markdown_path) is not None
            if visible:
                self._update_prompt_height()
        self._prompt_container.setVisible(visible)
        enabled = visible and not self._ask_in_progress
        self._ask_button.setEnabled(enabled)
        self._prompt_input.setEnabled(enabled)

    def _group_context_from_markdown(self, path: Path) -> tuple[str, int, Path] | None:
        resolved = path.resolve()
        if resolved.suffix.lower() != ".md":
            return None
        parts = resolved.parts
        try:
            group_data_idx = parts.index("group_data")
        except ValueError:
            return None
        if group_data_idx + 1 >= len(parts):
            return None
        try:
            group_index = int(parts[group_data_idx + 1])
        except Exception:
            return None
        assets_idx = None
        for idx, part in enumerate(parts[:group_data_idx]):
            if part == "assets":
                assets_idx = idx
        if assets_idx is None:
            return None
        drop_levels = len(parts) - (group_data_idx + 2)
        group_dir = resolved
        for _ in range(drop_levels):
            group_dir = group_dir.parent
        asset_parts = parts[assets_idx + 1 : group_data_idx]
        if not asset_parts:
            return None
        asset_name = "/".join(asset_parts)
        return asset_name, group_index, group_dir

    def _is_enhanced_img_explainer_markdown(self, path: Path) -> bool:
        context = self._group_context_from_markdown(path)
        if not context:
            return False
        _asset_name, group_index, group_dir = context
        expected = group_dir / "img_explainer_data" / "enhanced.md"
        try:
            return path.resolve() == expected.resolve()
        except Exception:
            return False

    def _tutor_context_from_markdown(self, path: Path) -> tuple[str, int, int, Path] | None:
        context = self._group_context_from_markdown(path)
        if not context:
            return None
        asset_name, group_index, group_dir = context
        tutor_data_dir = group_dir / "tutor_data"
        try:
            resolved = path.resolve()
            resolved.relative_to(tutor_data_dir.resolve())
        except Exception:
            return None

        parts = resolved.parts
        try:
            tutor_data_idx = parts.index("tutor_data")
        except ValueError:
            return None
        if tutor_data_idx + 1 >= len(parts):
            return None
        tutor_idx_raw = parts[tutor_data_idx + 1]
        if not tutor_idx_raw.isdigit():
            return None
        try:
            tutor_idx = int(tutor_idx_raw)
        except Exception:
            return None

        tutor_session_dir = tutor_data_dir / tutor_idx_raw
        if not tutor_session_dir.is_dir():
            return None
        return asset_name, group_index, tutor_idx, tutor_session_dir

    def _is_tutor_focus_markdown(self, path: Path) -> bool:
        context = self._tutor_context_from_markdown(path)
        if not context:
            return False
        _asset_name, _group_index, _tutor_idx, tutor_session_dir = context
        expected = tutor_session_dir / "focus.md"
        try:
            return path.resolve() == expected.resolve()
        except Exception:
            return False

    def _is_tutor_history_markdown(self, path: Path) -> bool:
        context = self._tutor_context_from_markdown(path)
        if not context:
            return False
        _asset_name, _group_index, _tutor_idx, tutor_session_dir = context
        ask_history_dir = tutor_session_dir / "ask_history"
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        if resolved.suffix.lower() != ".md" or not resolved.is_file():
            return False
        try:
            resolved.relative_to(ask_history_dir.resolve())
        except Exception:
            return resolved.name.lower() == "ask_history.md"
        return True

    def _update_history_button_visibility(self) -> None:
        history_visible = False
        integrate_visible = False
        if self._current_markdown_path:
            history_visible = self._tutor_context_from_markdown(self._current_markdown_path) is not None
            integrate_visible = history_visible
        self._history_button.setVisible(history_visible)
        self._integrate_button.setVisible(integrate_visible)
        self._integrate_button.setEnabled(
            integrate_visible and not self._integrate_in_progress
        )

    def _update_delete_question_visibility(self) -> None:
        visible = False
        if self._current_markdown_path:
            visible = self._is_tutor_history_markdown(self._current_markdown_path)
        self._delete_question_button.setVisible(visible)

    def _update_initial_button_visibility(self) -> None:
        visible = False
        if self._current_markdown_path:
            visible = self._group_context_from_markdown(self._current_markdown_path) is not None
        self._show_initial_button.setVisible(visible)

    def _update_tutor_focus_visibility(self) -> None:
        visible = False
        if self._current_markdown_path:
            visible = self._group_context_from_markdown(self._current_markdown_path) is not None
        self._tutor_focus_button.setVisible(visible)

    def _update_focus_crop_visibility(self) -> None:
        visible = False
        if self._current_markdown_path:
            visible = self._is_tutor_focus_markdown(self._current_markdown_path)
        self._crop_head_button.setVisible(visible)
        self._crop_tail_button.setVisible(visible)

    def _update_reveal_button_state(self) -> None:
        enabled = bool(self._current_markdown_path and self._current_markdown_path.is_file())
        self._reveal_button.setEnabled(enabled)

    def _update_fix_latex_button_state(self) -> None:
        enabled = bool(
            self._current_markdown_path
            and self._current_markdown_path.is_file()
            and not self._fix_latex_in_progress
        )
        self._fix_latex_button.setEnabled(enabled)

    def _reveal_in_explorer(self) -> None:
        if not self._current_markdown_path or not self._current_markdown_path.is_file():
            self.statusBar().showMessage("No markdown selected.")
            return
        folder = self._current_markdown_path.parent
        opened = QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))
        if not opened:
            self.statusBar().showMessage(f"Failed to open folder: {folder.name}")

    def _show_about_dialog(self) -> None:
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("About")
        layout = QtWidgets.QVBoxLayout(dialog)

        made_by = QtWidgets.QLabel(
            'made by <a href="https://github.com/ximiwu">ximiwu</a>'
        )
        made_by.setTextFormat(QtCore.Qt.RichText)
        made_by.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        made_by.setOpenExternalLinks(True)

        powered_by = QtWidgets.QLabel(
            'powered by <a href="https://github.com/openai/codex">codex</a>, '
            '<a href="https://github.com/google-gemini/gemini-cli">gemini-cli</a>'
        )
        powered_by.setTextFormat(QtCore.Qt.RichText)
        powered_by.setTextInteractionFlags(QtCore.Qt.TextBrowserInteraction)
        powered_by.setOpenExternalLinks(True)

        layout.addWidget(made_by)
        layout.addWidget(powered_by)

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)

        dialog.setLayout(layout)
        dialog.exec()

    def _handle_fix_latex(self) -> None:
        if self._fix_latex_in_progress:
            self.statusBar().showMessage("Latex fix already in progress.")
            return
        if not self._current_markdown_path or not self._current_markdown_path.is_file():
            self.statusBar().showMessage("No markdown selected.")
            return
        self._fix_latex_in_progress = True
        self._update_fix_latex_button_state()
        self.statusBar().showMessage(f"Fixing latex in {self._current_markdown_path.name}...")
        task = _FixLatexTask(self._current_markdown_path)
        task.signals.finished.connect(self._on_fix_latex_finished)
        task.signals.failed.connect(self._on_fix_latex_failed)
        self._fix_latex_pool.start(task)

    @QtCore.Slot(str)
    def _on_fix_latex_finished(self, output_path: str) -> None:
        self._fix_latex_in_progress = False
        self._update_fix_latex_button_state()
        path = Path(output_path)
        if path.is_file():
            if self._find_markdown_tab(path) is not None:
                self._open_markdown_file(path)
            self.statusBar().showMessage(f"Latex fixed: {path.name}")
            return
        self.statusBar().showMessage(f"Latex fix output not found: {output_path}")

    @QtCore.Slot(str)
    def _on_fix_latex_failed(self, error: str) -> None:
        self._fix_latex_in_progress = False
        self._update_fix_latex_button_state()
        self.statusBar().showMessage(f"Latex fix failed: {error}")

    def _crop_focus_head(self) -> None:
        if not self._current_markdown_path or not self._is_tutor_focus_markdown(self._current_markdown_path):
            self.statusBar().showMessage("crop head only available on tutor focus.md.")
            return
        path = self._current_markdown_path
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to read {path.name}: {exc}")
            return
        lines = content.splitlines()
        if not lines:
            self.statusBar().showMessage("focus.md is empty.")
            return
        new_content = "\n".join(lines[1:])
        try:
            path.write_text(new_content, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to update {path.name}: {exc}")
            return
        self._open_markdown_file(path)

    def _crop_focus_tail(self) -> None:
        if not self._current_markdown_path or not self._is_tutor_focus_markdown(self._current_markdown_path):
            self.statusBar().showMessage("crop tail only available on tutor focus.md.")
            return
        path = self._current_markdown_path
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to read {path.name}: {exc}")
            return
        lines = content.splitlines()
        if not lines:
            self.statusBar().showMessage("focus.md is empty.")
            return
        new_content = "\n".join(lines[:-1])
        try:
            path.write_text(new_content, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to update {path.name}: {exc}")
            return
        self._open_markdown_file(path)

    def _build_history_items(self, tutor_session_dir: Path) -> list[tuple[str, Path]]:
        ask_history_dir = tutor_session_dir / "ask_history"
        if not ask_history_dir.is_dir():
            return []

        def _order_key(path: Path) -> tuple[int, str]:
            stem = path.stem
            try:
                return int(stem), stem
            except Exception:
                return 1_000_000, stem

        entries: list[tuple[str, Path]] = []
        for path in sorted(ask_history_dir.glob("*.md"), key=_order_key):
            entries.append((path.name, path))
        return entries

    def _focus_preview(self, focus_path: Path) -> str:
        try:
            content = focus_path.read_text(encoding="utf-8")
        except Exception:  # pragma: no cover - GUI runtime path
            return ""
        collapsed = " ".join(content.split())
        return collapsed[:150]

    def _collect_tutor_focus_items(self, asset_name: str, group_idx: int | None = None) -> list[tuple[str, Path]]:
        group_data_dir = get_group_data_dir(asset_name)
        if not group_data_dir.is_dir():
            return []

        def _order_key(path: Path) -> tuple[int, str]:
            name = path.name
            try:
                return int(name), name
            except Exception:
                return 1_000_000, name

        items: list[tuple[str, Path]] = []
        if group_idx is not None:
            target_dirs = [group_data_dir / str(group_idx)]
        else:
            target_dirs = sorted(group_data_dir.iterdir(), key=_order_key)

        for group_dir in target_dirs:
            if not group_dir.is_dir() or not group_dir.name.isdigit():
                continue
            tutor_data_dir = group_dir / "tutor_data"
            if not tutor_data_dir.is_dir():
                continue
            for session_dir in sorted(tutor_data_dir.iterdir(), key=_order_key):
                if not session_dir.is_dir() or not session_dir.name.isdigit():
                    continue
                focus_path = session_dir / "focus.md"
                if not focus_path.is_file():
                    continue
                preview = self._focus_preview(focus_path)
                items.append((f"{session_dir.name} {preview}.....", focus_path))
        return items

    def _show_tutor_focus_list(self) -> None:
        if not self._current_markdown_path:
            self.statusBar().showMessage("Open a group markdown first.")
            return
        context = self._group_context_from_markdown(self._current_markdown_path)
        if not context:
            self.statusBar().showMessage("History ask tutor is only available in group_data.")
            return
        asset_name, group_idx, _group_dir = context
        items = self._collect_tutor_focus_items(asset_name, group_idx)
        if not items:
            self.statusBar().showMessage("No tutor focus found for this group.")
            return
        dialog = _TutorFocusDialog(items, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        selected = dialog.selected_paths()
        if not selected:
            self.statusBar().showMessage("No focus.md selected.")
            return
        for path in selected:
            self._open_markdown_file(path)

    def _delete_current_question(self) -> None:
        if not self._current_markdown_path:
            self.statusBar().showMessage("No markdown selected.")
            return
        path = self._current_markdown_path
        if not self._is_tutor_history_markdown(path):
            self.statusBar().showMessage("delete question is only available for tutor ask_history markdown.")
            return
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Delete Question",
            f"Delete this question markdown?\n{path.name}",
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        tab_index = self._find_markdown_tab(path)
        try:
            path.unlink(missing_ok=True)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to delete {path.name}: {exc}")
            return
        if tab_index is not None:
            self._close_markdown_tab(tab_index)
        self.statusBar().showMessage(f"Deleted {path.name}")

    def _show_history_questions(self) -> None:
        if not self._current_markdown_path:
            self.statusBar().showMessage("No markdown selected.")
            return
        context = self._tutor_context_from_markdown(self._current_markdown_path)
        if not context:
            self.statusBar().showMessage("History not available for this file.")
            return
        _asset_name, _group_idx, _tutor_idx, tutor_session_dir = context
        entries = self._build_history_items(tutor_session_dir)
        if not entries:
            self.statusBar().showMessage("No tutor history found.")
            return
        dialog = _TutorHistoryDialog(entries, parent=self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        for path in dialog.selected_paths():
            self._open_markdown_file(path)

    def _show_initial_markdown(self) -> None:
        if not self._current_markdown_path:
            self.statusBar().showMessage("No markdown selected.")
            return
        context = self._group_context_from_markdown(self._current_markdown_path)
        if not context:
            self.statusBar().showMessage("Initial files not available for this file.")
            return
        _asset_name, group_idx, group_dir = context
        initial_dir = group_dir / "img_explainer_data" / "initial"
        if not initial_dir.is_dir():
            self.statusBar().showMessage(f"No initial folder for group {group_idx}.")
            return

        def _order_key(path: Path) -> tuple[int, str]:
            stem = path.stem
            try:
                return int(stem), stem
            except Exception:
                return 1_000_000, stem

        md_paths = sorted(initial_dir.glob("*.md"), key=_order_key)
        if not md_paths:
            self.statusBar().showMessage(f"No initial markdown found for group {group_idx}.")
            return
        for path in md_paths:
            self._open_markdown_file(path, tab_label=f"Initial: {path.name}")

    def _resolve_current_markdown_path(self) -> Path | None:
        widget = self._markdown_tabs.currentWidget()
        for path, view in self._markdown_views.items():
            if view is widget:
                return path
        return None

    def _close_markdown_tab(self, index: int) -> None:
        widget = self._markdown_tabs.widget(index)
        if widget:
            self._markdown_tabs.removeTab(index)
            for path, view in list(self._markdown_views.items()):
                if view is widget:
                    del self._markdown_views[path]
                    break
        if not self._markdown_views:
            self._markdown_tabs.setTabsClosable(False)
            self._show_markdown_placeholder()
        self._set_current_markdown_path(self._resolve_current_markdown_path())

    def _on_markdown_tab_changed(self, _index: int) -> None:
        self._set_current_markdown_path(self._resolve_current_markdown_path())

    def _handle_integrate(self) -> None:
        if self._integrate_in_progress:
            self.statusBar().showMessage("finish_ask already in progress.")
            return
        if not self._current_markdown_path:
            self.statusBar().showMessage("Open a tutor markdown first.")
            return
        context = self._tutor_context_from_markdown(self._current_markdown_path)
        if not context:
            self.statusBar().showMessage("finish_ask is only available in tutor_data.")
            return
        asset_name, group_idx, tutor_idx, _tutor_session_dir = context
        self._integrate_in_progress = True
        self._update_prompt_visibility()
        self._update_history_button_visibility()
        self.statusBar().showMessage(f"finish_ask (group {group_idx}, tutor {tutor_idx})")
        task = _IntegrateTask(asset_name, group_idx, tutor_idx)
        task.signals.finished.connect(self._on_integrate_finished)
        task.signals.failed.connect(self._on_integrate_failed)
        self._integrate_pool.start(task)

    @QtCore.Slot(str)
    def _on_integrate_finished(self, output_path: str) -> None:
        self._integrate_in_progress = False
        self._update_prompt_visibility()
        self._update_history_button_visibility()

        path = Path(output_path)
        if path.is_file():
            self.statusBar().showMessage(f"finish_ask updated {path.name}")
            return
        self.statusBar().showMessage(f"finish_ask updated {output_path}")

    @QtCore.Slot(str)
    def _on_integrate_failed(self, error: str) -> None:
        self._integrate_in_progress = False
        self._update_prompt_visibility()
        self._update_history_button_visibility()
        self.statusBar().showMessage(f"finish_ask failed: {error}")

    def _handle_ask(self) -> None:
        text = self._prompt_input.toPlainText().strip()
        if not text:
            self.statusBar().showMessage("Enter a question first.")
            return
        if self._ask_in_progress:
            self.statusBar().showMessage("Ask already in progress.")
            return
        if not self._current_markdown_path:
            self.statusBar().showMessage("Open a group explainer markdown first.")
            return
        context = self._tutor_context_from_markdown(self._current_markdown_path)
        if not context:
            self.statusBar().showMessage("Ask is only available in tutor_data.")
            return
        asset_name, group_idx, tutor_idx, _tutor_session_dir = context
        self._ask_in_progress = True
        self._update_prompt_visibility()
        self._update_history_button_visibility()
        preview = text if len(text) <= 60 else f"{text[:60]}..."
        self.statusBar().showMessage(f"Ask (group {group_idx}, tutor {tutor_idx}): {preview}")
        task = _AskTutorTask(asset_name, group_idx, tutor_idx, text)
        task.signals.finished.connect(self._on_ask_finished)
        task.signals.failed.connect(self._on_ask_failed)
        self._ask_pool.start(task)

    @QtCore.Slot(str)
    def _on_ask_finished(self, output_path: str) -> None:
        self._ask_in_progress = False
        self._update_prompt_visibility()
        self._update_history_button_visibility()
        self._prompt_input.clear()

        path = Path(output_path)
        if path.is_file():
            self._open_markdown_file(path, tab_label=f"Tutor: {path.name}")
            self.statusBar().showMessage(f"Tutor response saved to {path.name}")
            return
        self.statusBar().showMessage(f"Tutor response saved to {output_path}")

    @QtCore.Slot(str)
    def _on_ask_failed(self, error: str) -> None:
        self._ask_in_progress = False
        self._update_prompt_visibility()
        self._update_history_button_visibility()
        self.statusBar().showMessage(f"Ask failed: {error}")

    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if obj is self._prompt_input:
            if event.type() == QtCore.QEvent.KeyPress:
                if isinstance(event, QtGui.QKeyEvent) and event.key() in (
                    QtCore.Qt.Key_Return,
                    QtCore.Qt.Key_Enter,
                ):
                    if event.modifiers() & QtCore.Qt.ShiftModifier:
                        return False
                    self._ask_button.click()
                    return True
            if event.type() == QtCore.QEvent.Resize:
                self._update_prompt_height()
        return super().eventFilter(obj, event)

    def _find_markdown_tab(self, path: Path) -> int | None:
        resolved = path.resolve()
        view = self._markdown_views.get(resolved)
        if not view:
            return None
        index = self._markdown_tabs.indexOf(view)
        if index < 0:
            del self._markdown_views[resolved]
            return None
        return index

    def _open_markdown_file(self, path: Path, *, tab_label: str | None = None) -> None:
        resolved = path.resolve()
        if not resolved.is_file():
            self.statusBar().showMessage(f"Markdown not found: {resolved.name}")
            return
        try:
            content = resolved.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to read {resolved.name}: {exc}")
            return
        try:
            html = markdown_helper.render_markdown_content(content)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to render markdown: {exc}")
            return

        self._remove_markdown_placeholder()
        title = tab_label or resolved.name
        existing_index = self._find_markdown_tab(resolved)
        if existing_index is not None:
            widget = self._markdown_tabs.widget(existing_index)
            if isinstance(widget, QtWebEngineWidgets.QWebEngineView):
                self._configure_markdown_view(widget, resolved)
                widget.setHtml(html, baseUrl=QtCore.QUrl.fromLocalFile(str(resolved.parent)))
            if tab_label:
                self._markdown_tabs.setTabText(existing_index, title)
            self._markdown_tabs.setCurrentIndex(existing_index)
            self._set_current_markdown_path(resolved)
            self.statusBar().showMessage(f"Updated {title}")
            return

        view = QtWebEngineWidgets.QWebEngineView()
        self._configure_markdown_view(view, resolved)
        view.setHtml(html, baseUrl=QtCore.QUrl.fromLocalFile(str(resolved.parent)))
        index = self._markdown_tabs.addTab(view, title)
        self._markdown_tabs.setCurrentIndex(index)
        self._markdown_tabs.setTabsClosable(True)
        self._markdown_views[resolved] = view
        self._set_current_markdown_path(resolved)
        self.statusBar().showMessage(f"Opened {title}")

    def _configure_markdown_view(self, view: QtWebEngineWidgets.QWebEngineView, path: Path) -> None:
        view.setProperty("markdown_path", str(path))
        if view.property("_markdown_context_menu_ready"):
            return
        view.setProperty("_markdown_context_menu_ready", True)
        view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        view.customContextMenuRequested.connect(
            lambda point, _view=view: self._show_markdown_context_menu(_view, point)
        )

    def _show_markdown_context_menu(self, view: QtWebEngineWidgets.QWebEngineView, point: QtCore.QPoint) -> None:
        try:
            menu = view.createStandardContextMenu()
        except Exception:
            menu = QtWidgets.QMenu(view)
        menu.addSeparator()
        markdown_path = self._markdown_path_for_view(view) or self._current_markdown_path
        if markdown_path and self._is_enhanced_img_explainer_markdown(markdown_path):
            ask_action = menu.addAction("ask tutor")
            ask_action.setEnabled(self._view_has_selection(view))
            ask_action.triggered.connect(lambda _checked=False, _view=view: self._ask_tutor_at_markdown_selection(_view))
        menu.exec(view.mapToGlobal(point))
        menu.deleteLater()

    def _markdown_path_for_view(self, view: QtWebEngineWidgets.QWebEngineView) -> Path | None:
        prop = view.property("markdown_path")
        if prop:
            try:
                return Path(str(prop))
            except Exception:
                return None
        for path, candidate in self._markdown_views.items():
            if candidate is view:
                return path
        return None

    def _current_markdown_view(self) -> QtWebEngineWidgets.QWebEngineView | None:
        widget = self._markdown_tabs.currentWidget()
        if isinstance(widget, QtWebEngineWidgets.QWebEngineView):
            return widget
        return None

    @staticmethod
    def _view_has_selection(view: QtWebEngineWidgets.QWebEngineView) -> bool:
        try:
            return view.page().hasSelection()
        except Exception:
            return bool(view.selectedText().strip())

    def _ask_tutor_at_markdown_selection(self, view: QtWebEngineWidgets.QWebEngineView | None = None) -> None:
        markdown_view = view or self._current_markdown_view()
        if not markdown_view:
            self.statusBar().showMessage("No markdown view selected.")
            return
        markdown_path = self._markdown_path_for_view(markdown_view) or self._current_markdown_path
        if not markdown_path:
            self.statusBar().showMessage("No markdown selected.")
            return
        if not markdown_path.is_file():
            self.statusBar().showMessage(f"Markdown not found: {markdown_path.name}")
            return
        if not self._is_enhanced_img_explainer_markdown(markdown_path):
            self.statusBar().showMessage("ask tutor is only available on img_explainer_data/enhanced.md.")
            return
        if not self._view_has_selection(markdown_view):
            self.statusBar().showMessage("No text selected in markdown.")
            return

        self._capture_markdown_selection_as_copied_text(
            markdown_view,
            lambda copied: self._init_tutor_from_markdown_selection(markdown_path, copied),
        )

    def _init_tutor_from_markdown_selection(self, markdown_path: Path, selected_text: str) -> None:
        if not selected_text.strip():
            self.statusBar().showMessage("Clipboard selection is empty.")
            return
        try:
            markdown = markdown_path.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to read {markdown_path.name}: {exc}")
            return

        match = self._find_markdown_match_range(markdown, selected_text)
        if not match:
            self.statusBar().showMessage("Selected text not found in markdown.")
            return

        start, end = match
        focus_markdown = markdown[start : end + 1]
        if not focus_markdown.strip():
            self.statusBar().showMessage("Selected focus content is empty.")
            return

        context = self._group_context_from_markdown(markdown_path)
        if not context:
            self.statusBar().showMessage("Failed to resolve asset/group for this markdown.")
            return
        asset_name, group_idx, _group_dir = context
        try:
            focus_path = init_tutor(asset_name, group_idx, focus_markdown)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to init tutor: {exc}")
            return
        self._open_markdown_file(focus_path, tab_label=f"Tutor focus {focus_path.parent.name}")
        self.statusBar().showMessage(f"Created tutor focus in group {group_idx} (session {focus_path.parent.name}).")

    @staticmethod
    def _clone_mime_data(source: QtCore.QMimeData) -> QtCore.QMimeData:
        cloned = QtCore.QMimeData()
        for fmt in source.formats():
            cloned.setData(fmt, source.data(fmt))
        if source.hasText():
            cloned.setText(source.text())
        if source.hasHtml():
            cloned.setHtml(source.html())
        if source.hasUrls():
            cloned.setUrls(source.urls())
        if source.hasImage():
            cloned.setImageData(source.imageData())
        return cloned

    def _capture_markdown_selection_as_copied_text(
        self,
        view: QtWebEngineWidgets.QWebEngineView,
        on_captured: Callable[[str], None],
    ) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        if self._markdown_clipboard_capture_handler is not None:
            try:
                clipboard.dataChanged.disconnect(self._markdown_clipboard_capture_handler)
            except Exception:
                pass
            self._markdown_clipboard_capture_handler = None

        self._markdown_clipboard_capture_token += 1
        token = self._markdown_clipboard_capture_token
        saved = self._clone_mime_data(clipboard.mimeData())
        before_text = clipboard.text()
        finished = False
        capture_scheduled = False
        change_seen = False
        attempt = 0

        def read_clipboard_text() -> str:
            try:
                mime = clipboard.mimeData()
                if mime and mime.hasText():
                    return mime.text()
            except Exception:
                pass
            return clipboard.text()

        def finish_capture(captured: str | None = None) -> None:
            nonlocal finished
            if finished or self._markdown_clipboard_capture_token != token:
                return
            finished = True
            handler = self._markdown_clipboard_capture_handler
            if handler is not None:
                try:
                    clipboard.dataChanged.disconnect(handler)
                except Exception:
                    pass
            self._markdown_clipboard_capture_handler = None
            captured_text = captured if captured is not None else read_clipboard_text()
            try:
                clipboard.setMimeData(saved)
            except Exception:
                pass
            on_captured(captured_text)

        def try_capture() -> None:
            nonlocal attempt, capture_scheduled
            if finished or self._markdown_clipboard_capture_token != token:
                return
            current = read_clipboard_text()
            if (change_seen and current and (current != before_text or attempt >= 3)) or attempt >= 12:
                finish_capture(current)
                return
            attempt += 1
            QtCore.QTimer.singleShot(50, try_capture)

        def schedule_capture(delay_ms: int) -> None:
            nonlocal capture_scheduled
            if capture_scheduled:
                return
            capture_scheduled = True
            QtCore.QTimer.singleShot(delay_ms, try_capture)

        def on_data_changed() -> None:
            nonlocal change_seen
            change_seen = True
            schedule_capture(50)

        self._markdown_clipboard_capture_handler = on_data_changed
        clipboard.dataChanged.connect(on_data_changed)
        QtCore.QTimer.singleShot(250, lambda: schedule_capture(0))
        QtCore.QTimer.singleShot(1500, finish_capture)
        try:
            view.page().triggerAction(QtWebEngineCore.QWebEnginePage.WebAction.Copy)
        except AttributeError:
            try:
                view.page().triggerAction(QtWebEngineCore.QWebEnginePage.Copy)
            except AttributeError:
                view.page().triggerAction(QtWebEngineWidgets.QWebEnginePage.Copy)

    @staticmethod
    def _normalize_text_for_markdown_match(text: str, *, strip_all_whitespace: bool = False) -> str:
        text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
        text = text.replace("\u202f", " ").replace("\u2007", " ")
        text = re.sub(r"[\u200b\u200c\u200d\u2060\ufeff]", "", text)
        lines: list[str] = []
        for line in text.splitlines():
            stripped = line.lstrip()
            stripped = re.sub(r"^[-*+]\s+", "", stripped)
            stripped = re.sub(r"^>+\s*", "", stripped)
            stripped = re.sub(r"^[•◦▪·‣⁃∙●○]+\s+", "", stripped)
            lines.append(stripped)
        text = "\n".join(lines)
        text = text.strip()
        if strip_all_whitespace:
            return re.sub(r"\s+", "", text)
        return re.sub(r"\s+", " ", text)

    @classmethod
    def _normalize_markdown_for_match(
        cls, content: str, *, strip_all_whitespace: bool = False
    ) -> tuple[str, list[int]]:
        content = content.replace("\r\n", "\n").replace("\r", "\n")
        out_chars: list[str] = []
        out_map: list[int] = []
        i = 0
        at_line_start = True
        while i < len(content):
            char = content[i]

            if char == "<":
                gt = content.find(">", i + 1)
                if gt != -1 and gt - i <= 200 and "\n" not in content[i : gt + 1]:
                    candidate = content[i + 1 : gt].lstrip()
                    if candidate.startswith("!--"):
                        end_comment = content.find("-->", gt + 1)
                        if end_comment != -1:
                            i = end_comment + 3
                            continue
                    if candidate and (candidate[0].isalpha() or candidate[0] in "/!?"):
                        i = gt + 1
                        continue

            if at_line_start:
                j = i
                while j < len(content) and content[j] in " \t":
                    j += 1

                k = j
                while k < len(content) and content[k] == "#":
                    k += 1
                if k > j and k - j <= 6 and k < len(content) and content[k] in " \t":
                    while k < len(content) and content[k] in " \t":
                        k += 1
                    i = k
                    at_line_start = False
                    continue

                if j < len(content) and content[j] in "-*+":
                    k = j + 1
                    if k < len(content) and content[k] in " \t":
                        while k < len(content) and content[k] in " \t":
                            k += 1
                        i = k
                        at_line_start = False
                        continue

                if j < len(content) and content[j] == ">":
                    k = j
                    while k < len(content) and content[k] == ">":
                        k += 1
                    while k < len(content) and content[k] in " \t":
                        k += 1
                    i = k
                    at_line_start = False
                    continue

                at_line_start = False

            if content.startswith("**", i) or content.startswith("__", i):
                i += 2
                continue

            if char == "`":
                i += 1
                continue

            if char.isspace():
                if char == "\n":
                    at_line_start = True
                if strip_all_whitespace:
                    i += 1
                    continue
                if out_chars and out_chars[-1] == " ":
                    i += 1
                    continue
                out_chars.append(" ")
                out_map.append(i)
                i += 1
                continue

            out_chars.append(char)
            out_map.append(i)
            i += 1

        out_text = "".join(out_chars)
        if strip_all_whitespace:
            return out_text, out_map
        normalized = out_text.strip()
        if normalized != out_text:
            leading = len(out_text) - len(out_text.lstrip(" "))
            trailing = len(out_text) - len(out_text.rstrip(" "))
            if trailing:
                out_map = out_map[leading:-trailing]
            else:
                out_map = out_map[leading:]
        return normalized, out_map

    def _find_markdown_match_range(self, markdown: str, selected_text: str) -> tuple[int, int] | None:
        def try_exact(strip_all_whitespace: bool) -> tuple[int, int] | None:
            normalized_selected = self._normalize_text_for_markdown_match(
                selected_text, strip_all_whitespace=strip_all_whitespace
            )
            if not normalized_selected:
                return None
            normalized_markdown, index_map = self._normalize_markdown_for_match(
                markdown, strip_all_whitespace=strip_all_whitespace
            )
            if not normalized_markdown or len(normalized_selected) > len(normalized_markdown):
                return None
            pos = normalized_markdown.find(normalized_selected)
            if pos < 0:
                return None
            start = index_map[pos]
            end = index_map[pos + len(normalized_selected) - 1]
            return start, end

        exact = try_exact(False)
        if exact:
            return exact
        exact_no_ws = try_exact(True)
        if exact_no_ws:
            return exact_no_ws

        import difflib

        normalized_selected = self._normalize_text_for_markdown_match(selected_text, strip_all_whitespace=True)
        normalized_markdown, index_map = self._normalize_markdown_for_match(markdown, strip_all_whitespace=True)
        if not normalized_selected or not normalized_markdown or len(normalized_selected) > len(normalized_markdown):
            return None

        selected_len = len(normalized_selected)
        max_start = len(normalized_markdown) - selected_len

        matcher = difflib.SequenceMatcher(None, normalized_markdown, normalized_selected, autojunk=False)
        anchor = matcher.find_longest_match(0, len(normalized_markdown), 0, selected_len)
        if anchor.size < min(30, max(10, selected_len // 5)):
            return None

        estimated_start = max(0, min(max_start, anchor.a - anchor.b))
        search_radius = min(1000, max_start)
        start_min = max(0, estimated_start - search_radius)
        start_max = min(max_start, estimated_start + search_radius)
        first_char = normalized_selected[0]

        def score_candidate(candidate: int) -> tuple[float, float]:
            window = normalized_markdown[candidate : candidate + selected_len]
            ratio = difflib.SequenceMatcher(None, window, normalized_selected, autojunk=False).ratio()
            boundary_len = min(selected_len, min(120, max(20, selected_len // 8)))
            if boundary_len < selected_len:
                prefix_ratio = difflib.SequenceMatcher(
                    None, window[:boundary_len], normalized_selected[:boundary_len], autojunk=False
                ).ratio()
                suffix_ratio = difflib.SequenceMatcher(
                    None, window[-boundary_len:], normalized_selected[-boundary_len:], autojunk=False
                ).ratio()
            else:
                prefix_ratio = ratio
                suffix_ratio = ratio
            score = ratio * 0.70 + prefix_ratio * 0.15 + suffix_ratio * 0.15
            return score, ratio

        candidate_starts: set[int] = set()

        def add_anchor_candidates(anchor_text: str, *, anchor_is_prefix: bool) -> None:
            if not anchor_text:
                return
            search_lo = start_min
            search_hi = min(len(normalized_markdown), start_max + selected_len)
            pos = normalized_markdown.find(anchor_text, search_lo, search_hi)
            while pos != -1:
                candidate = pos if anchor_is_prefix else pos - (selected_len - len(anchor_text))
                if start_min <= candidate <= start_max:
                    candidate_starts.add(candidate)
                    if len(candidate_starts) >= 200:
                        return
                pos = normalized_markdown.find(anchor_text, pos + 1, search_hi)

        anchor_lengths = [80, 60, 40, 30, 20, 15, 10]
        for length in anchor_lengths:
            length = min(selected_len, length)
            if length < 10:
                continue
            add_anchor_candidates(normalized_selected[:length], anchor_is_prefix=True)
            if candidate_starts:
                break
        for length in anchor_lengths:
            length = min(selected_len, length)
            if length < 10:
                continue
            add_anchor_candidates(normalized_selected[-length:], anchor_is_prefix=False)
            if len(candidate_starts) >= 50:
                break

        best_start = None
        best_score = -1.0
        best_ratio = 0.0

        def consider_start(candidate: int) -> None:
            nonlocal best_start, best_score, best_ratio
            score, ratio = score_candidate(candidate)
            if score > best_score:
                best_start = candidate
                best_score = score
                best_ratio = ratio
                return
            if best_start is None:
                return
            if abs(score - best_score) <= 1e-6:
                if ratio > best_ratio or (abs(ratio - best_ratio) <= 1e-6 and abs(candidate - estimated_start) < abs(best_start - estimated_start)):
                    best_start = candidate
                    best_score = score
                    best_ratio = ratio

        if candidate_starts:
            for candidate in candidate_starts:
                consider_start(candidate)
        else:
            step = max(1, selected_len // 200)
            require_first_char = selected_len >= 50
            for candidate in range(start_min, start_max + 1, step):
                if require_first_char and normalized_markdown[candidate] != first_char:
                    continue
                consider_start(candidate)
            if best_start is None and require_first_char:
                for candidate in range(start_min, start_max + 1, step):
                    consider_start(candidate)

            if best_start is not None and step > 1:
                refine_min = max(start_min, best_start - step)
                refine_max = min(start_max, best_start + step)
                for candidate in range(refine_min, refine_max + 1):
                    consider_start(candidate)

        if best_start is None or best_ratio < 0.80:
            return None

        start = index_map[best_start]
        end = index_map[best_start + selected_len - 1]
        return start, end

    @staticmethod
    def _line_col_from_index(text: str, index: int) -> tuple[int, int]:
        line = text.count("\n", 0, index) + 1
        last_newline = text.rfind("\n", 0, index)
        col = index - last_newline
        return line, col

    def _insert_text_at_markdown_match(self, path: Path, selected_text: str, insert_text: str) -> None:
        if not selected_text.strip():
            self.statusBar().showMessage("Clipboard selection is empty.")
            return
        try:
            markdown = path.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to read {path.name}: {exc}")
            return

        match = self._find_markdown_match_range(markdown, selected_text)
        if not match:
            self.statusBar().showMessage("Selected text not found in markdown.")
            return

        _start, end = match
        insert_at = end + 1
        updated = markdown[:insert_at] + insert_text + markdown[insert_at:]
        try:
            path.write_text(updated, encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to write {path.name}: {exc}")
            return

        self._open_markdown_file(path)
        line, col = self._line_col_from_index(updated, insert_at)
        self.statusBar().showMessage(f'Inserted \"{insert_text}\" at {path.name}:{line}:{col}')

    def _normalize_math_content(self, content: str) -> str:
        return markdown_helper.normalize_math_content(content)

    def _normalize_details_markdown(self, content: str) -> str:
        return markdown_helper.normalize_details_markdown(content)

    def _normalize_details_attrs(self, attrs: str) -> tuple[str, bool]:
        return markdown_helper.normalize_details_attrs(attrs)

    def _normalize_note_content_divs(self, block: str) -> str:
        return markdown_helper.normalize_note_content_divs(block)

    def _normalize_list_spacing_markdown(self, content: str) -> str:
        return markdown_helper.normalize_list_spacing_markdown(content)

    def _render_markdown_content(self, content: str) -> str:
        return markdown_helper.render_markdown_content(content)

    def _katex_assets(self) -> str:
        return markdown_helper.katex_assets()

    def _open_reference_markdown(self, name: str) -> None:
        if not self._current_asset_name or not self._current_references_dir:
            self.statusBar().showMessage("Load an asset to view reference markdown.")
            return
        path = self._current_references_dir / f"{name}.md"
        if not path.is_file():
            self.statusBar().showMessage(f"Reference file not found: {path.name}")
            return
        self._open_markdown_file(path)

    def _show_reference_info(self) -> None:
        if not self._current_asset_name or not self._current_references_dir:
            self.statusBar().showMessage("Load an asset to view reference markdown.")
            return
        for name in ("background", "concept", "formula"):
            self._open_reference_markdown(name)

    def _apply_splitter_ratio(self) -> None:
        left = max(DEFAULT_SPLITTER_RATIO_LEFT, 1)
        right = max(DEFAULT_SPLITTER_RATIO_RIGHT, 1)
        total = left + right
        basis = _SPLITTER_SIZE_BASIS
        left_size = max(1, int(basis * left / total))
        right_size = max(1, int(basis * right / total))
        self._splitter.setSizes([left_size, right_size])

    def _update_window_title(self) -> None:
        title = self._base_title
        if self._current_asset_name:
            title = f"{title} - {self._current_asset_name}"
        if self._dirty:
            title = f"{title} *"
        self.setWindowTitle(title)

    def _update_dpi_label(self) -> None:
        self._dpi_label.setText(f"DPI: {self._renderer.dpi}")

    def _set_dirty(self, dirty: bool) -> None:
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self._update_window_title()

    def _go_to_page(self, page_index: int) -> None:
        if page_index < 0 or page_index >= self._page_count:
            return
        self._current_page = page_index
        self._page_input.blockSignals(True)
        self._page_input.setValue(self._current_page + 1)
        self._page_input.blockSignals(False)
        self._rebuild_scene(center_on_current=True)

    def _on_page_input(self, value: int) -> None:
        self._go_to_page(value - 1)

    def _adjust_zoom(self, delta: float) -> None:
        self._set_zoom(self._zoom + delta)

    @staticmethod
    def _clamp_zoom(value: float) -> float:
        return max(0.1, min(5.0, value))

    def _calculate_default_zoom(self) -> float:
        if self._renderer.dpi <= 0:
            return 1.0
        return self._reference_dpi / self._renderer.dpi

    def _set_zoom(self, value: float) -> None:
        self._zoom = self._clamp_zoom(value)
        effective_dpi = self._apply_render_dpi()
        self._apply_zoom_transform(effective_dpi)
        self._persist_asset_ui_state()

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        self._persist_asset_ui_state()
        super().closeEvent(event)

    def _target_render_dpi(self) -> int:
        scaled = int(round(self._reference_dpi * self._zoom))
        scaled = max(MIN_RENDER_DPI, scaled)
        if self._max_render_dpi:
            scaled = min(self._max_render_dpi, scaled)
        return max(1, scaled)

    def _apply_zoom_transform(self, effective_dpi: int) -> None:
        dpi_scale = effective_dpi / self._reference_dpi if self._reference_dpi > 0 else 1.0
        residual_zoom = self._zoom / dpi_scale if dpi_scale else self._zoom
        self._view.resetTransform()
        self._view.scale(residual_zoom, residual_zoom)

    def _render_scale_factor(self) -> float:
        if self._reference_dpi <= 0:
            return 1.0
        return max(self._renderer.dpi, 1) / self._reference_dpi

    def _apply_render_dpi(self) -> int:
        if not self._page_count:
            self._update_dpi_label()
            return self._renderer.dpi
        target_dpi = self._target_render_dpi()
        if target_dpi != self._renderer.dpi:
            self._renderer.set_dpi(target_dpi)
            self._render_generation += 1
            self._update_page_metrics()
            self._clear_scene_items()
            self._rebuild_scene(center_on_current=True)
        self._update_dpi_label()
        return self._renderer.dpi

    def _update_page_metrics(self) -> None:
        self._page_heights = []
        self._page_widths = []
        self._page_offsets = [0]
        if not self._page_count:
            return
        for i in range(self._page_count):
            w, h = self._renderer.page_pixel_size(i)
            self._page_widths.append(w)
            self._page_heights.append(h)
            self._page_offsets.append(self._page_offsets[-1] + h)
        self._update_compress_result_label()

    def _clear_scene_items(self) -> None:
        self._hide_block_action_overlay()
        self._scene.clear()
        self._page_pixmaps.clear()
        self._pages_loaded.clear()
        self._pending_renders.clear()
        self._desired_pages.clear()
        self._block_items.clear()
        self._hovered_block_id = None
        self._hovered_group_idx = None
        self._clear_compress_overlays(reset_rect=False)

    def _to_reference_rect(self, rect: QtCore.QRectF) -> QtCore.QRectF:
        scale = self._render_scale_factor()
        if scale == 0:
            return rect
        return QtCore.QRectF(
            rect.x() / scale,
            rect.y() / scale,
            rect.width() / scale,
            rect.height() / scale,
        )

    def _from_reference_rect(self, rect: QtCore.QRectF) -> QtCore.QRectF:
        scale = self._render_scale_factor()
        return QtCore.QRectF(
            rect.x() * scale,
            rect.y() * scale,
            rect.width() * scale,
            rect.height() * scale,
        )

    def _on_scroll(self, _value: int) -> None:
        if self._drag_active:
            return
        center_y = self._view.mapToScene(
            QtCore.QPoint(
                self._view.viewport().width() // 2, self._view.viewport().height() // 2
            )
        ).y()
        page_index = self._page_at_y(center_y)
        if page_index is not None and page_index != self._current_page:
            self._current_page = page_index
            self._page_input.blockSignals(True)
            self._page_input.setValue(self._current_page + 1)
            self._page_input.blockSignals(False)
            self._rebuild_scene(center_on_current=False)

    def _rebuild_scene(self, *, center_on_current: bool = False) -> None:
        if not self._page_count:
            return

        prev_center: QtCore.QPointF | None = None
        if not center_on_current:
            prev_center = self._view.mapToScene(
                QtCore.QPoint(
                    self._view.viewport().width() // 2, self._view.viewport().height() // 2
                )
            )

        desired = {
            p
            for p in (self._current_page - 1, self._current_page, self._current_page + 1)
            if 0 <= p < self._page_count
        }
        self._desired_pages = desired

        for page in list(self._pages_loaded):
            if page not in desired:
                self._remove_page_items(page)

        for page in sorted(desired, key=lambda p: (p != self._current_page, p)):
            if page not in self._pages_loaded:
                self._request_page_render(page)

        total_height = self._page_offsets[-1] if self._page_offsets else 0
        max_width = 0
        for p in desired:
            max_width = max(max_width, self._page_widths[p])
        if max_width == 0:
            max_width = 1
        self._scene.setSceneRect(0, 0, max_width, total_height)

        if center_on_current and self._page_heights:
            x_center = max_width / 2
            y_center = (
                self._page_offsets[self._current_page]
                + self._page_heights[self._current_page] / 2
            )
            self._view.centerOn(x_center, y_center)
        elif prev_center is not None:
            self._view.centerOn(prev_center)
        self._page_label.setText(f"Page: {self._current_page + 1}/{self._page_count}")

    def _page_at_y(self, y: float) -> int | None:
        if not self._page_offsets:
            return None
        for idx in range(self._page_count):
            top = self._page_offsets[idx]
            bottom = self._page_offsets[idx + 1]
            if top <= y < bottom:
                return idx
        return None

    def _request_page_render(self, page_index: int) -> None:
        if page_index in self._pending_renders:
            return
        task = _RenderTask(self._renderer, page_index, self._render_generation)
        task.signals.finished.connect(self._on_render_finished)
        task.signals.failed.connect(self._on_render_failed)
        self._pending_renders.add(page_index)
        self._render_pool.start(task)

    def _on_render_finished(self, page_index: int, generation: int, image: QtGui.QImage) -> None:
        self._pending_renders.discard(page_index)
        if generation != self._render_generation:
            return
        if page_index in self._pages_loaded:
            return
        if page_index not in self._desired_pages:
            return
        self._add_page_to_scene(page_index, image)

    def _on_render_failed(self, page_index: int, generation: int, error: str) -> None:
        self._pending_renders.discard(page_index)
        if generation != self._render_generation:
            return
        self.statusBar().showMessage(f"Failed to render page {page_index + 1}: {error}")

    def _add_page_to_scene(self, page_index: int, image: QtGui.QImage) -> None:
        if image.isNull():
            self.statusBar().showMessage(f"Failed to render page {page_index + 1}.")
            return
        y_offset = self._page_offsets[page_index]
        pixmap_item = self._scene.addPixmap(QtGui.QPixmap.fromImage(image))
        pixmap_item.setOffset(0, y_offset)
        pixmap_item.setZValue(1)
        self._page_pixmaps[page_index] = pixmap_item
        self._pages_loaded.add(page_index)
        self._render_page_blocks(page_index)

    def _remove_page_items(self, page_index: int) -> None:
        if page_index in self._page_pixmaps:
            self._scene.removeItem(self._page_pixmaps[page_index])
            del self._page_pixmaps[page_index]
        for block_id in list(self._blocks_by_page.get(page_index, [])):
            item = self._block_items.pop(block_id, None)
            if item:
                self._scene.removeItem(item)
        if page_index in self._pages_loaded:
            self._pages_loaded.remove(page_index)

    def _render_page_blocks(self, page_index: int) -> None:
        for block_id in self._blocks_by_page.get(page_index, []):
            if block_id in self._block_items:
                self._scene.removeItem(self._block_items[block_id])
                del self._block_items[block_id]
        if self._block_action_block_id in self._blocks_by_page.get(page_index, []):
            self._hide_block_action_overlay()
        y_offset = self._page_offsets[page_index]
        for block_id in self._blocks_by_page.get(page_index, []):
            block = self._blocks[block_id]
            current_rect = self._from_reference_rect(block.rect.normalized())
            translated = QtCore.QRectF(
                current_rect.x(),
                current_rect.y() + y_offset,
                current_rect.width(),
                current_rect.height(),
            )
            item = _BlockGraphicsItem(
                translated, block_id, self._on_block_hover_enter, self._on_block_hover_leave
            )
            item.setData(0, block_id)
            item.setZValue(5)
            self._scene.addItem(item)
            self._block_items[block_id] = item
            self._apply_block_style(block_id)
        self._render_compress_overlay_for_page(page_index)

    def _block_center_position(self, block_id: int) -> QtCore.QPointF | None:
        item = self._block_items.get(block_id)
        if item:
            return item.sceneBoundingRect().center()
        block = self._blocks.get(block_id)
        if not block:
            return None
        if block.page_index >= len(self._page_offsets):
            return None
        rect = self._from_reference_rect(block.rect.normalized())
        y_offset = self._page_offsets[block.page_index]
        translated = QtCore.QRectF(
            rect.x(),
            rect.y() + y_offset,
            rect.width(),
            rect.height(),
        )
        return translated.center()

    def _hide_block_action_overlay(self) -> None:
        if self._block_action_proxy:
            self._scene.removeItem(self._block_action_proxy)
        self._block_action_proxy = None
        self._block_action_block_id = None

    def _position_block_action_overlay(self, center: QtCore.QPointF) -> None:
        if not self._block_action_proxy:
            return
        widget = self._block_action_proxy.widget()
        if not widget:
            self._hide_block_action_overlay()
            return
        size = widget.sizeHint()
        self._block_action_proxy.setPos(center.x() - size.width() / 2, center.y() - size.height() / 2)

    def _show_block_action_overlay(self, block_id: int) -> None:
        center = self._block_center_position(block_id)
        if center is None:
            self._hide_block_action_overlay()
            return
        if block_id != self._block_action_block_id:
            self._hide_block_action_overlay()
        if self._block_action_proxy and self._block_action_block_id == block_id:
            self._position_block_action_overlay(center)
            return

        container = QtWidgets.QFrame()
        container.setFrameShape(QtWidgets.QFrame.StyledPanel)
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(6, 4, 6, 4)
        merge_button = QtWidgets.QPushButton("Merge Block")
        clear_button = QtWidgets.QPushButton("Clear Selection")
        merge_button.clicked.connect(self._merge_selected_blocks)
        clear_button.clicked.connect(self._clear_merge_order)
        layout.addWidget(merge_button)
        layout.addWidget(clear_button)

        proxy = self._scene.addWidget(container)
        proxy.setZValue(10)
        proxy.setFlag(QtWidgets.QGraphicsItem.ItemIgnoresTransformations, True)
        self._block_action_proxy = proxy
        self._block_action_block_id = block_id
        self._position_block_action_overlay(center)

    def _on_block_hover_enter(self, block_id: int) -> None:
        block = self._blocks.get(block_id)
        if not block:
            return
        if block.group_idx is not None:
            if self._hovered_group_idx != block.group_idx:
                previous_group = self._hovered_group_idx
                self._hovered_group_idx = block.group_idx
                self._hovered_block_id = None
                if previous_group is not None:
                    for member in self._blocks_by_group.get(previous_group, set()):
                        self._apply_block_style(member)
                for member in self._blocks_by_group.get(block.group_idx, set()):
                    self._apply_block_style(member)
            return
        if self._hovered_group_idx is not None:
            for member in self._blocks_by_group.get(self._hovered_group_idx, set()):
                self._apply_block_style(member)
            self._hovered_group_idx = None
        if self._hovered_block_id == block_id:
            return
        previous_hover = self._hovered_block_id
        self._hovered_block_id = block_id
        if previous_hover is not None:
            self._apply_block_style(previous_hover)
        self._apply_block_style(block_id)

    def _on_block_hover_leave(self, block_id: int) -> None:
        block = self._blocks.get(block_id)
        if not block:
            return
        updated: set[int] = set()
        if self._hovered_block_id == block_id:
            self._hovered_block_id = None
            updated.add(block_id)
        if block.group_idx is not None and self._hovered_group_idx == block.group_idx:
            updated.update(self._blocks_by_group.get(block.group_idx, set()))
            self._hovered_group_idx = None
        for bid in updated:
            self._apply_block_style(bid)

    def _handle_selection(self, scene_rect: QtCore.QRectF) -> None:
        if self._compress_mode_active:
            self._handle_compress_selection(scene_rect)
            return
        if not self._page_offsets or not self._page_heights:
            return
        center_y = scene_rect.center().y()
        page_index = self._page_at_y(center_y)
        if page_index is None:
            self.statusBar().showMessage("Selection not within a page.")
            return
        y_offset = self._page_offsets[page_index]
        local_rect = QtCore.QRectF(
            scene_rect.x(),
            scene_rect.y() - y_offset,
            scene_rect.width(),
            scene_rect.height(),
        )
        self._create_block(page_index, local_rect)

    def _create_block(self, page_index: int, rect: QtCore.QRectF) -> None:
        block_id = self._next_block_id
        self._next_block_id += 1
        reference_rect = self._to_reference_rect(rect.normalized())
        block = Block(block_id=block_id, page_index=page_index, rect=reference_rect, group_idx=None)
        self._blocks[block_id] = block
        self._blocks_by_page.setdefault(page_index, []).append(block_id)

        self._render_page_blocks(block.page_index)
        self._set_dirty(True)

    def _remove_block_from_state(self, block: Block, *, update_group_map: bool = True) -> None:
        block_id = block.block_id
        self._blocks.pop(block_id, None)
        page_blocks = self._blocks_by_page.get(block.page_index)
        if page_blocks and block_id in page_blocks:
            page_blocks.remove(block_id)
            if not page_blocks:
                del self._blocks_by_page[block.page_index]
        self._selected_blocks.discard(block_id)
        if block_id in self._merge_order:
            self._merge_order.remove(block_id)
        if self._hovered_block_id == block_id:
            self._hovered_block_id = None
        if self._block_action_block_id == block_id:
            self._hide_block_action_overlay()
        item = self._block_items.pop(block_id, None)
        if item:
            scene = item.scene()
            if scene:
                scene.removeItem(item)
        if update_group_map and block.group_idx is not None:
            members = self._blocks_by_group.get(block.group_idx, set())
            members.discard(block_id)
            if members:
                self._blocks_by_group[block.group_idx] = members
            else:
                self._blocks_by_group.pop(block.group_idx, None)
                if self._hovered_group_idx == block.group_idx:
                    self._hovered_group_idx = None

    def _confirm_group_deletion(self, group_idx: int) -> bool:
        members = set(self._blocks_by_group.get(group_idx, set()))
        if not members:
            members = {bid for bid, blk in self._blocks.items() if blk.group_idx == group_idx}
        count = len(members)
        message = f"Delete group {group_idx}? This will remove {count} block(s)." if count else f"Delete group {group_idx}?"
        confirm = QtWidgets.QMessageBox.question(self, "Delete Group", message)
        return confirm == QtWidgets.QMessageBox.Yes

    def _delete_group(self, group_idx: int) -> None:
        member_ids = set(self._blocks_by_group.get(group_idx, set()))
        if not member_ids:
            member_ids = {bid for bid, blk in self._blocks.items() if blk.group_idx == group_idx}
        if not member_ids:
            self.statusBar().showMessage(f"No blocks found for group {group_idx}.")
            return
        removed_count = 0
        for member_id in list(member_ids):
            block = self._blocks.get(member_id)
            if block:
                self._remove_block_from_state(block, update_group_map=False)
                removed_count += 1
        self._blocks_by_group.pop(group_idx, None)
        if self._hovered_group_idx == group_idx:
            self._hovered_group_idx = None
        if self._current_asset_name:
            try:
                delete_group_record(self._current_asset_name, group_idx)
            except Exception as exc:  # pragma: no cover - GUI runtime path
                self.statusBar().showMessage(f"Failed to delete group {group_idx}: {exc}")
                self._update_merge_order_label()
                self._set_dirty(True)
                return
        self._update_merge_order_label()
        self.statusBar().showMessage(f"Deleted group {group_idx} with {removed_count} block(s).")
        self._set_dirty(True)

    def _delete_block(self, block_id: int) -> None:
        block = self._blocks.get(block_id)
        if not block:
            return
        if block.group_idx is not None:
            if not self._confirm_group_deletion(block.group_idx):
                return
            self._delete_group(block.group_idx)
            return
        self._remove_block_from_state(block)
        self._update_merge_order_label()
        self.statusBar().showMessage(f"Deleted block {block_id}")
        self._set_dirty(True)

    def _toggle_block_selection(self, block_id: int) -> None:
        block = self._blocks.get(block_id)
        if not block:
            self._hide_block_action_overlay()
            return
        if block.group_idx is not None:
            self._hide_block_action_overlay()
            self._start_group_dive(block.group_idx)
            return
        self._show_block_action_overlay(block_id)
        if block_id in self._selected_blocks:
            self._selected_blocks.remove(block_id)
            if block_id in self._merge_order:
                self._merge_order.remove(block_id)
        else:
            self._selected_blocks.add(block_id)
            self._merge_order.append(block_id)
        self._apply_block_style(block_id)
        self._update_merge_order_label()
        self._set_dirty(True)

    def _update_merge_order_label(self) -> None:
        if not self._merge_order:
            self._order_label.setText("Selection: (none)")
            return
        order_text = ", ".join(str(bid) for bid in self._merge_order)
        self._order_label.setText(f"Selection: {order_text}")

    def _clear_merge_order(self) -> None:
        self._merge_order.clear()
        self._selected_blocks.clear()
        for bid in list(self._block_items.keys()):
            self._apply_block_style(bid)
        self._update_merge_order_label()
        self._set_dirty(True)
        self._hide_block_action_overlay()

        self.statusBar().showMessage("Selection cleared.")

    def _merge_selected_blocks(self) -> None:
        if not self._current_asset_name:
            self.statusBar().showMessage("No asset loaded to merge.")
            return
        if not self._merge_order:
            self.statusBar().showMessage("Select blocks to merge.")
            return
        grouped = [
            bid for bid in self._merge_order if self._blocks.get(bid) and self._blocks[bid].group_idx is not None
        ]
        if grouped:
            grouped_text = ", ".join(str(bid) for bid in grouped)
            self.statusBar().showMessage(f"Already grouped: {grouped_text}")
            return
        try:
            record = create_group_record(self._current_asset_name, self._merge_order, group_idx=self._next_group_idx)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to merge blocks: {exc}")
            return
        self._blocks_by_group[record.group_idx] = set(record.block_ids)
        self._next_group_idx = max(self._next_group_idx, record.group_idx + 1)
        affected_ids: list[int] = []
        for block_id in record.block_ids:
            block = self._blocks.get(block_id)
            if block:
                block.group_idx = record.group_idx
                affected_ids.append(block_id)
        self._merge_order.clear()
        self._selected_blocks.clear()
        self._update_merge_order_label()
        for block_id in affected_ids:
            self._apply_block_style(block_id)
        self._hide_block_action_overlay()
        self._persist_block_data(force=True)
        self.statusBar().showMessage(f"Created group {record.group_idx} with {len(record.block_ids)} block(s).")

    def _block_style_for(self, block_id: int) -> dict:
        block = self._blocks.get(block_id)
        if not block:
            return BLOCK_STYLE_DEFAULT
        if block_id in self._selected_blocks:
            return BLOCK_STYLE_SELECTED
        if block.group_idx is not None and self._hovered_group_idx == block.group_idx:
            return BLOCK_STYLE_GROUP_HOVER
        if self._hovered_block_id == block_id:
            return BLOCK_STYLE_HOVER
        if block.group_idx is not None:
            return BLOCK_STYLE_GROUP_DEFAULT
        return BLOCK_STYLE_DEFAULT

    def _apply_block_style(self, block_id: int) -> None:
        item = self._block_items.get(block_id)
        if not item:
            return
        style = self._block_style_for(block_id)
        pen_enabled = style.get("pen_enabled", True)
        pen_color = QtGui.QColor(style["pen_color"])
        pen_alpha = style.get("pen_alpha")
        if pen_alpha is not None:
            pen_color = QtGui.QColor(pen_color)
            pen_color.setAlpha(int(pen_alpha))
        pen = QtGui.QPen(pen_color) if pen_enabled else QtGui.QPen(QtCore.Qt.NoPen)
        if style.get("pen_enabled", True):
            pen.setWidth(int(style["pen_width"]))
            pen.setStyle(style["pen_style"])
        brush_enabled = style.get("brush_enabled", True)
        brush_color = QtGui.QColor(style["brush_color"])
        brush_alpha = style.get("brush_alpha")
        if brush_alpha is not None:
            brush_color = QtGui.QColor(brush_color)
            brush_color.setAlpha(int(brush_alpha))
        brush = QtGui.QBrush(brush_color) if brush_enabled else QtGui.QBrush(QtCore.Qt.NoBrush)
        item.setPen(pen)
        item.setBrush(brush)

    def _crop_block(self, block: Block) -> QtGui.QImage:
        image = self._renderer.render_page(block.page_index)
        rect = self._from_reference_rect(block.rect.normalized())
        x = max(0, int(rect.left()))
        y = max(0, int(rect.top()))
        w = max(1, int(rect.width()))
        h = max(1, int(rect.height()))
        if x + w > image.width():
            w = image.width() - x
        if y + h > image.height():
            h = image.height() - y
        return image.copy(x, y, w, h)

    def _load_blocks_from_storage(self) -> None:
        if not self._current_asset_name:
            return
        data = load_block_data(self._current_asset_name)
        group_records = load_group_records(self._current_asset_name)

        self._clear_blocks_only()
        self._blocks_by_group = {record.group_idx: set(record.block_ids) for record in group_records}
        self._next_group_idx = next_group_idx(self._current_asset_name, group_records)
        for record in data.blocks:
            rect = QtCore.QRectF(
                record.rect.x,
                record.rect.y,
                record.rect.width,
                record.rect.height,
            ).normalized()
            block = Block(
                block_id=record.block_id,
                page_index=record.page_index,
                rect=rect,
                group_idx=record.group_idx,
            )
            self._blocks[block.block_id] = block
            self._blocks_by_page.setdefault(block.page_index, []).append(block.block_id)
            if block.group_idx is not None:
                self._blocks_by_group.setdefault(block.group_idx, set()).add(block.block_id)
                self._next_group_idx = max(self._next_group_idx, block.group_idx + 1)
        self._merge_order = [
            bid for bid in data.merge_order if bid in self._blocks and self._blocks[bid].group_idx is None
        ]
        self._selected_blocks = set(self._merge_order)
        self._next_block_id = max(data.next_block_id, max(self._blocks.keys(), default=0) + 1)

        for page_index in list(self._pages_loaded):
            self._render_page_blocks(page_index)
        self._update_merge_order_label()
        self._set_dirty(False)

    def _persist_block_data(self, *, force: bool = False) -> None:
        if not self._current_asset_name:
            self.statusBar().showMessage("No asset loaded to save.")
            return
        if not force and not self._dirty:
            self.statusBar().showMessage("No changes to save.")
            return
        records: list[BlockRecord] = []
        for block_id in sorted(self._blocks.keys()):
            block = self._blocks[block_id]
            rect = block.rect.normalized()
            records.append(
                BlockRecord(
                    block_id=block.block_id,
                    page_index=block.page_index,
                    rect=BlockRect(
                        x=rect.x(),
                        y=rect.y(),
                        width=rect.width(),
                        height=rect.height(),
                    ),
                    group_idx=block.group_idx,
                )
            )
        data = BlockData(blocks=records, merge_order=list(self._merge_order), next_block_id=self._next_block_id)
        try:
            save_block_data(self._current_asset_name, data)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to save blocks: {exc}")
            return
        self._set_dirty(False)
        self.statusBar().showMessage("Blocks saved.")

    def _undo_blocks(self) -> None:
        if not self._current_asset_name:
            self.statusBar().showMessage("No asset loaded to undo.")
            return
        self._load_blocks_from_storage()
        self.statusBar().showMessage("Blocks reloaded from disk.")

    def _start_group_dive(self, group_idx: int) -> None:
        if not self._current_asset_name:
            self.statusBar().showMessage("No asset loaded.")
            return
        enhanced_md = get_group_data_dir(self._current_asset_name) / str(group_idx) / "img_explainer_data" / "enhanced.md"
        if enhanced_md.is_file():
            self._open_markdown_file(enhanced_md, tab_label=f"Group {group_idx}: enhanced.md")
            return
        if self._group_dive_in_progress:
            self.statusBar().showMessage("Group dive already in progress.")
            return
        self._group_dive_in_progress = True
        self.statusBar().showMessage(f"Running explainer for group {group_idx}...")
        task = _GroupDiveTask(self._current_asset_name, group_idx)
        task.signals.finished.connect(self._on_group_dive_finished)
        task.signals.failed.connect(self._on_group_dive_failed)
        task.signals.gemini_ready.connect(self._on_group_dive_gemini_ready)
        self._group_dive_pool.start(task)

    def _resolve_group_markdown_output(self, path: Path) -> Path | None:
        resolved = path.resolve()
        if resolved.is_file() and resolved.suffix.lower() == ".md":
            if resolved.name != "enhanced.md":
                return None
            return resolved
        if resolved.is_dir():
            enhanced_md = resolved / "enhanced.md"
            if enhanced_md.is_file():
                return enhanced_md
        return None

    @QtCore.Slot(str, int)
    def _on_group_dive_gemini_ready(self, output_path: str, group_idx: int) -> None:
        path = Path(output_path)
        if not path.is_file():
            self.statusBar().showMessage(f"Gemini output not found for group {group_idx}: {path.name}")
            return
        self.statusBar().showMessage(f"Gemini output ready for group {group_idx}: {path.name}")

    def _on_group_dive_finished(self, output_path: str) -> None:
        self._group_dive_in_progress = False
        markdown_path = self._resolve_group_markdown_output(Path(output_path))
        if markdown_path:
            tab_title = markdown_path.name
            try:
                group_label = markdown_path.parent.parent.name
                if group_label:
                    tab_title = f"Group {group_label}: {markdown_path.name}"
            except Exception:
                pass
            self._open_markdown_file(markdown_path, tab_label=tab_title)
            return
        self.statusBar().showMessage(f"Explainer output saved to {output_path}")

    def _on_group_dive_failed(self, error: str) -> None:
        self._group_dive_in_progress = False
        self.statusBar().showMessage(f"Explainer failed: {error}")

