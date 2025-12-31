from __future__ import annotations

import html
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

_SIDEBAR_ACTION_SCHEME = "exocortex-sidebar"
_SIDEBAR_ACTION_HOST = "action"
_SIDEBAR_GROUP_ALIAS_FILENAME = "group.alias"
_SIDEBAR_MARKDOWN_ALIAS_SUFFIX = ".alias"
_SIDEBAR_SHOW_MARKDOWN_PREVIEW = False


class _MarkdownSidebarPage(QtWebEngineCore.QWebEnginePage):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self._window = window

    def acceptNavigationRequest(  # noqa: N802
        self,
        url: QtCore.QUrl,
        nav_type: QtWebEngineCore.QWebEnginePage.NavigationType,
        is_main_frame: bool,
    ) -> bool:
        if url.scheme() == _SIDEBAR_ACTION_SCHEME and url.host() == _SIDEBAR_ACTION_HOST:
            self._window._handle_markdown_sidebar_action_url(url)
            return False
        return super().acceptNavigationRequest(url, nav_type, is_main_frame)

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
    insert_feynman_original_image,
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
    _BugFinderTask,
    _CompressPreviewTask,
    _CompressTask,
    _FixLatexTask,
    _GroupDiveTask,
    _IntegrateTask,
    _ReTutorTask,
    _StudentNoteTask,
    _RenderTask,
)
from .dialogs import (
    _AssetProgressDialog,
    _AssetSelectionDialog,
    _FeynmanManuscriptDialog,
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
        self._bug_finder_pool = QtCore.QThreadPool(self)
        self._bug_finder_pool.setMaxThreadCount(1)
        self._student_note_pool = QtCore.QThreadPool(self)
        self._student_note_pool.setMaxThreadCount(1)
        self._group_dive_pool = QtCore.QThreadPool(self)
        self._group_dive_pool.setMaxThreadCount(1)
        self._fix_latex_pool = QtCore.QThreadPool(self)
        self._fix_latex_pool.setMaxThreadCount(1)
        self._drag_active = False
        self._asset_init_in_progress = False
        self._asset_progress_dialog: _AssetProgressDialog | None = None
        self._tutor_history_dialog: _TutorHistoryDialog | None = None
        self._tutor_focus_dialog: _TutorFocusDialog | None = None
        self._current_references_dir: Path | None = None
        self._markdown_views: Dict[Path, QtWebEngineWidgets.QWebEngineView] = {}
        self._markdown_placeholder_index: int | None = None
        self._markdown_sidebar_view: QtWebEngineWidgets.QWebEngineView | None = None
        self._markdown_sidebar_splitter: QtWidgets.QSplitter | None = None
        self._markdown_sidebar_collapsed = False
        self._markdown_sidebar_restore_width: int | None = None
        self._markdown_sidebar_collapsed_nodes: set[str] = set()
        self._markdown_warmup_view: QtWebEngineWidgets.QWebEngineView | None = None
        self._markdown_pdf_page: QtWebEngineCore.QWebEnginePage | None = None
        self._markdown_pdf_context: dict[str, object] | None = None
        self._markdown_pdf_temp_path: Path | None = None
        self._group_dive_in_progress = False
        self._ask_in_progress = False
        self._integrate_in_progress = False
        self._bug_finder_in_progress = False
        self._student_note_in_progress = False
        self._fix_latex_in_progress = False
        self._feynman_mode_active = False
        self._feynman_locked_tab_index: int | None = None
        self._feynman_view: QtWebEngineWidgets.QWebEngineView | None = None
        self._feynman_context: tuple[str, int, int, Path] | None = None
        self._feynman_pending_review = False
        self._feynman_questions_enabled = False
        self._block_action_proxy: QtWidgets.QGraphicsProxyWidget | None = None
        self._block_action_block_id: int | None = None
        self._current_markdown_path: Path | None = None
        self._markdown_clipboard_capture_token = 0
        self._markdown_clipboard_capture_handler: Callable[[], None] | None = None
        self._asset_config_persist_suspended = False
        self._asset_ui_state_persist_timer = QtCore.QTimer(self)
        self._asset_ui_state_persist_timer.setSingleShot(True)
        self._asset_ui_state_persist_timer.setInterval(250)
        self._asset_ui_state_persist_timer.timeout.connect(self._persist_asset_ui_state)
        self._markdown_scroll_y_by_path: dict[str, float] = {}
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
        self._history_button = None
        self._delete_question_button = QtWidgets.QPushButton("delete question")
        self._tutor_focus_button = None
        self._integrate_button = QtWidgets.QPushButton("start feynman")
        self._skip_feynman_button = QtWidgets.QPushButton("skip feynman")
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
        self._delete_question_button.clicked.connect(self._delete_current_question)
        self._integrate_button.clicked.connect(self._handle_integrate)
        self._skip_feynman_button.clicked.connect(self._handle_skip_feynman)
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
        self._delete_question_button.setVisible(False)
        self._integrate_button.setVisible(False)
        self._skip_feynman_button.setVisible(False)
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
        top_bar.addWidget(self._delete_question_button)
        top_bar.addWidget(self._integrate_button)
        top_bar.addWidget(self._skip_feynman_button)
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

        self._feynman_submit_button = QtWidgets.QPushButton("submit my deduction")
        self._feynman_finish_button = QtWidgets.QPushButton("finish improvement")
        self._feynman_finish_button.setVisible(False)
        self._feynman_submit_button.clicked.connect(self._handle_feynman_submit)
        self._feynman_finish_button.clicked.connect(self._handle_feynman_finish)

        feynman_bar = QtWidgets.QHBoxLayout()
        feynman_bar.setContentsMargins(0, 0, 0, 0)
        feynman_bar.addStretch(1)
        feynman_bar.addWidget(self._feynman_submit_button)
        feynman_bar.addWidget(self._feynman_finish_button)
        self._feynman_controls = QtWidgets.QWidget()
        self._feynman_controls.setLayout(feynman_bar)
        self._feynman_controls.setVisible(False)

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
        self._markdown_tabs_reordering = False
        self._markdown_tabs.tabCloseRequested.connect(self._close_markdown_tab)
        self._markdown_tabs.currentChanged.connect(self._on_markdown_tab_changed)
        self._markdown_tabs.tabBar().tabMoved.connect(self._on_markdown_tab_moved)
        self._reset_markdown_tabs()
        QtCore.QTimer.singleShot(0, self._warm_up_markdown_engine)
        QtCore.QTimer.singleShot(0, self._warm_up_history_dialogs)

        self._markdown_tabs.tabBar().setVisible(False)

        self._ask_tutor_action = QtGui.QAction("ask tutor", self)
        self._ask_tutor_action.setShortcut(QtGui.QKeySequence("Ctrl+Alt+T"))
        self._ask_tutor_action.setShortcutContext(QtCore.Qt.ApplicationShortcut)
        self._ask_tutor_action.triggered.connect(self._ask_tutor_at_markdown_selection)
        self.addAction(self._ask_tutor_action)

        markdown_container = QtWidgets.QWidget()
        markdown_layout = QtWidgets.QVBoxLayout(markdown_container)
        markdown_layout.setContentsMargins(0, 0, 0, 0)

        self._markdown_sidebar_view = QtWebEngineWidgets.QWebEngineView(self)
        self._markdown_sidebar_view.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        self._markdown_sidebar_view.setPage(_MarkdownSidebarPage(self))

        self._markdown_sidebar_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self._markdown_sidebar_splitter.addWidget(self._markdown_sidebar_view)
        self._markdown_sidebar_splitter.addWidget(self._markdown_tabs)
        self._markdown_sidebar_splitter.setCollapsible(0, False)
        self._markdown_sidebar_splitter.setCollapsible(1, False)
        self._markdown_sidebar_splitter.setStretchFactor(0, 0)
        self._markdown_sidebar_splitter.setStretchFactor(1, 1)
        self._markdown_sidebar_splitter.setSizes([240, 800])
        self._markdown_sidebar_splitter.splitterMoved.connect(
            lambda _pos, _idx: self._schedule_persist_asset_ui_state()
        )

        markdown_layout.addWidget(self._markdown_sidebar_splitter)

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
        self._splitter.splitterMoved.connect(
            lambda _pos, _idx: self._schedule_persist_asset_ui_state()
        )

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.addLayout(top_bar)
        layout.addWidget(self._splitter, 1)
        layout.addWidget(self._compress_controls)
        layout.addWidget(self._prompt_container)
        layout.addWidget(self._feynman_controls)
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
        QtCore.QTimer.singleShot(0, self._refresh_markdown_sidebar)

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
        dialog = _NewAssetDialog(
            default_name,
            allow_img2md_markdown=selected_path.suffix.lower() == ".pdf",
            img2md_start_dir=selected_path.parent,
            parent=self,
        )
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

        img2md_markdown_path = dialog.img2md_markdown_path()
        if img2md_markdown_path is not None:
            if selected_path.suffix.lower() != ".pdf":
                self.statusBar().showMessage("Skipping img2md requires selecting a PDF first.")
                return
            if dialog.compress_enabled():
                self.statusBar().showMessage("Page compress can't be used when skipping img2md.")
                return
            self._start_asset_initialization_with_img2md_markdown(
                selected_path, img2md_markdown_path, asset_name
            )
            return

        if dialog.compress_enabled():
            if selected_path.suffix.lower() == ".md":
                self.statusBar().showMessage("Page compress only supports PDF inputs.")
            else:
                self._start_page_compress(selected_path, asset_name)
                return
        self._start_asset_initialization(selected_path, asset_name)

    def _start_asset_initialization_with_img2md_markdown(
        self,
        source_pdf: Path,
        img2md_markdown_path: Path,
        asset_name: str,
    ) -> None:
        if not source_pdf.is_file():
            self.statusBar().showMessage(f"PDF not found: {source_pdf}")
            return
        if not img2md_markdown_path.is_file():
            self.statusBar().showMessage(f"Markdown not found: {img2md_markdown_path}")
            return
        if img2md_markdown_path.suffix.lower() != ".md":
            self.statusBar().showMessage("Selected file is not a Markdown (.md) file.")
            return

        self._asset_init_in_progress = True
        self._show_asset_progress_dialog()
        if self._asset_progress_dialog:
            self._asset_progress_dialog.append_message(
                f"Using pre-generated Markdown (skip img2md): {img2md_markdown_path}"
            )
            self._asset_progress_dialog.append_message(f"Starting asset '{asset_name}'...")
        self.statusBar().showMessage(f"Initializing asset '{asset_name}' (skip img2md)...")
        self._start_asset_init_task(img2md_markdown_path, asset_name, rendered_pdf_path=source_pdf)

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

    def _warm_up_history_dialogs(self) -> None:
        """Preload WebEngine history dialogs (with KaTeX) to avoid first-open lag."""
        if not self._tutor_history_dialog:
            self._tutor_history_dialog = _TutorHistoryDialog(parent=self)
            self._tutor_history_dialog.set_items([])
        if not self._tutor_focus_dialog:
            self._tutor_focus_dialog = _TutorFocusDialog(parent=self)
            self._tutor_focus_dialog.set_items([])

    def _set_markdown_sidebar_collapsed(self, collapsed: bool, *, update_restore_width: bool = True) -> None:
        splitter = self._markdown_sidebar_splitter
        self._markdown_sidebar_collapsed = collapsed
        if not splitter:
            return

        sizes = splitter.sizes()
        if len(sizes) != 2:
            return

        collapsed_width = 44
        total = max(1, sizes[0] + sizes[1])
        if collapsed:
            if update_restore_width and sizes[0] > collapsed_width:
                self._markdown_sidebar_restore_width = sizes[0]
            splitter.setSizes([collapsed_width, max(1, total - collapsed_width)])
        else:
            restore_width = self._markdown_sidebar_restore_width or 240
            restore_width = max(collapsed_width, min(restore_width, total - 1))
            splitter.setSizes([restore_width, max(1, total - restore_width)])

        self._persist_asset_ui_state()
        self._refresh_markdown_sidebar()

    @staticmethod
    def _sidebar_node_id(kind: str, *parts: int) -> str:
        if parts:
            return f"{kind}:" + ":".join(str(part) for part in parts)
        return kind

    @staticmethod
    def _parse_sidebar_node_id(node_id: str) -> tuple[str, tuple[int, ...]] | None:
        if not node_id:
            return None
        parts = node_id.split(":")
        if not parts:
            return None
        kind = parts[0].strip()
        if not kind:
            return None
        if len(parts) == 1:
            return kind, ()
        numbers: list[int] = []
        for raw in parts[1:]:
            if not raw or not raw.isdigit():
                return None
            try:
                numbers.append(int(raw))
            except Exception:
                return None
        return kind, tuple(numbers)

    @staticmethod
    def _read_sidebar_alias(path: Path) -> str | None:
        try:
            text = path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            return None
        return text or None

    @staticmethod
    def _atomic_write_sidebar_alias(path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(value, encoding="utf-8")
        tmp_path.replace(path)

    @staticmethod
    def _markdown_alias_path(markdown_path: Path) -> Path:
        return markdown_path.with_name(markdown_path.name + _SIDEBAR_MARKDOWN_ALIAS_SUFFIX)

    @staticmethod
    def _default_group_alias(group_index: int) -> str:
        return f"Group {group_index}"

    def _markdown_sidebar_group_title(self, group_dir: Path, group_index: int) -> str:
        alias_path = group_dir / _SIDEBAR_GROUP_ALIAS_FILENAME
        return self._read_sidebar_alias(alias_path) or self._default_group_alias(group_index)

    def _markdown_sidebar_markdown_title(self, markdown_path: Path, fallback: str) -> str:
        alias = self._read_sidebar_alias(self._markdown_alias_path(markdown_path))
        return alias or fallback

    def _set_markdown_sidebar_group_alias(self, group_dir: Path, group_index: int, alias: str) -> None:
        alias_path = group_dir / _SIDEBAR_GROUP_ALIAS_FILENAME
        cleaned = alias.strip()
        default = self._default_group_alias(group_index)
        if not cleaned or cleaned == default:
            try:
                alias_path.unlink()
            except FileNotFoundError:
                pass
            return
        self._atomic_write_sidebar_alias(alias_path, cleaned)

    def _set_markdown_sidebar_markdown_alias(self, markdown_path: Path, alias: str) -> str:
        alias_path = self._markdown_alias_path(markdown_path)
        cleaned = alias.strip()
        default = markdown_path.name
        if not cleaned or cleaned == default:
            try:
                alias_path.unlink()
            except FileNotFoundError:
                pass
            return default
        self._atomic_write_sidebar_alias(alias_path, cleaned)
        return cleaned

    @staticmethod
    def _markdown_sidebar_preview_for_path(path: Path) -> str:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for _ in range(30):
                    line = handle.readline()
                    if not line:
                        break
                    stripped = line.strip()
                    if not stripped:
                        continue
                    normalized = re.sub(r"\s+", " ", stripped)
                    normalized = markdown_helper.normalize_math_content(normalized)
                    return normalized[:180]
        except Exception:
            return ""
        return ""

    def _build_markdown_sidebar_tree_html(self) -> str:
        head_assets = markdown_helper.katex_assets()
        collapsed_class = "collapsed" if self._markdown_sidebar_collapsed else ""
        show_preview = _SIDEBAR_SHOW_MARKDOWN_PREVIEW

        active_path: Path | None = None
        if self._current_markdown_path:
            try:
                active_path = self._current_markdown_path.resolve()
            except Exception:
                active_path = self._current_markdown_path

        collapsed_nodes = self._markdown_sidebar_collapsed_nodes

        def esc(value: object) -> str:
            return html.escape(str(value), quote=True)

        groups: dict[str, dict[str, object]] = {}
        group_order: list[str] = []

        def ensure_group(group_id: str, title: str) -> dict[str, object]:
            group = groups.get(group_id)
            if group is None:
                group = {
                    "id": group_id,
                    "title": title,
                    "active": False,
                    "leaves": [],
                    "tutors": {},
                    "tutor_order": [],
                }
                groups[group_id] = group
                group_order.append(group_id)
            return group

        def ensure_tutor(group: dict[str, object], tutor_id: str, tutor_title: str) -> dict[str, object]:
            tutors: dict[str, dict[str, object]] = group["tutors"]  # type: ignore[assignment]
            tutor = tutors.get(tutor_id)
            if tutor is None:
                tutor = {
                    "id": tutor_id,
                    "title": tutor_title,
                    "active": False,
                    "leaves": [],
                    "focus_path": None,
                    "focus_open": False,
                    "history": [],
                }
                tutors[tutor_id] = tutor
                tutor_order: list[str] = group["tutor_order"]  # type: ignore[assignment]
                tutor_order.append(tutor_id)
            return tutor

        for tab_index in range(self._markdown_tabs.count()):
            widget = self._markdown_tabs.widget(tab_index)
            if not isinstance(widget, QtWebEngineWidgets.QWebEngineView):
                continue
            markdown_path = self._markdown_path_for_view(widget)
            if not markdown_path:
                continue
            try:
                resolved = markdown_path.resolve()
            except Exception:
                resolved = markdown_path
            if not resolved.is_file():
                continue

            title = (self._markdown_tabs.tabText(tab_index) or resolved.name).strip() or resolved.name
            title = self._markdown_sidebar_markdown_title(resolved, title)
            preview = self._markdown_sidebar_preview_for_path(resolved) if show_preview else ""
            is_active = bool(active_path and resolved == active_path)

            group_ctx = self._group_context_from_markdown(resolved)
            if group_ctx:
                _ctx_asset, group_idx, group_dir = group_ctx
                group_id = self._sidebar_node_id("group", group_idx)
                group_title = self._markdown_sidebar_group_title(group_dir, group_idx)
            else:
                group_id = "other"
                group_title = "Other"
            group = ensure_group(group_id, group_title)
            if is_active:
                group["active"] = True

            tutor_ctx = self._tutor_context_from_markdown(resolved)
            if tutor_ctx:
                _asset_name, group_idx_int, tutor_idx, tutor_session_dir = tutor_ctx
                tutor_id = self._sidebar_node_id("tutor", group_idx_int, tutor_idx)
                tutor = ensure_tutor(group, tutor_id, f"tutor_data/{tutor_idx}")
                if is_active:
                    tutor["active"] = True

                focus_path = tutor_session_dir / "focus.md"
                try:
                    focus_resolved = focus_path.resolve()
                except Exception:
                    focus_resolved = focus_path
                tutor["focus_path"] = focus_resolved

                ask_history_dir = tutor_session_dir / "ask_history"
                try:
                    ask_history_dir_resolved = ask_history_dir.resolve()
                except Exception:
                    ask_history_dir_resolved = ask_history_dir

                is_focus = resolved == focus_resolved
                is_history = False
                if not is_focus:
                    try:
                        resolved.relative_to(ask_history_dir_resolved)
                        is_history = True
                    except Exception:
                        is_history = False

                if is_focus:
                    tutor["focus_open"] = True
                    continue

                if is_history:
                    history: list[dict[str, object]] = tutor["history"]  # type: ignore[assignment]
                    history.append(
                        {
                            "path": resolved,
                            "title": title,
                            "preview": preview,
                            "active": is_active,
                            "parent": tutor_id,
                        }
                    )
                    continue

                tutor_leaves: list[dict[str, object]] = tutor["leaves"]  # type: ignore[assignment]
                tutor_leaves.append(
                    {
                        "path": resolved,
                        "title": title,
                        "preview": preview,
                        "active": is_active,
                        "parent": tutor_id,
                    }
                )
                continue

            group_leaves: list[dict[str, object]] = group["leaves"]  # type: ignore[assignment]
            group_leaves.append(
                {
                    "path": resolved,
                    "title": title,
                    "preview": preview,
                    "active": is_active,
                    "parent": group_id,
                }
            )

        def leaf_html(item: dict[str, object]) -> str:
            classes = "leaf active" if item.get("active") else "leaf"
            path_attr = esc(item.get("path"))
            parent_attr = esc(item.get("parent"))
            title_html = html.escape(str(item.get("title", "")))
            preview_html = html.escape(str(item.get("preview", "")))
            preview_block = ""
            if show_preview and preview_html:
                preview_block = f"<div class='leaf-preview'>{preview_html}</div>"
            return (
                "<div class='"
                + classes
                + f"' data-path='{path_attr}' data-parent='{parent_attr}' draggable='true'>"
                + "<div class='leaf-main'>"
                + f"<div class='leaf-title'>{title_html}</div>"
                + preview_block
                + "</div>"
                + f"<button class='close' data-action='close' data-path='{path_attr}'>x</button>"
                + "</div>"
            )

        blocks: list[str] = []
        for group_id in group_order:
            group = groups[group_id]
            node_id = str(group["id"])
            classes = "node group"
            if node_id in collapsed_nodes:
                classes += " collapsed"
            if group.get("active"):
                classes += " active"

            children: list[str] = []
            for leaf in group.get("leaves", []):  # type: ignore[assignment]
                children.append(leaf_html(leaf))

            tutors: dict[str, dict[str, object]] = group.get("tutors", {})  # type: ignore[assignment]
            tutor_order: list[str] = group.get("tutor_order", [])  # type: ignore[assignment]
            for tutor_id in tutor_order:
                tutor = tutors.get(tutor_id)
                if not tutor:
                    continue
                tutor_node_id = str(tutor["id"])
                tutor_classes = "node tutor"
                if tutor_node_id in collapsed_nodes:
                    tutor_classes += " collapsed"
                if tutor.get("active"):
                    tutor_classes += " active"

                tutor_children: list[str] = []
                for leaf in tutor.get("leaves", []):  # type: ignore[assignment]
                    tutor_children.append(leaf_html(leaf))

                for leaf in tutor.get("history", []):  # type: ignore[assignment]
                    tutor_children.append(leaf_html(leaf))

                focus_path_value = tutor.get("focus_path")
                focus_path_attr = esc(focus_path_value or "")
                focus_title = "focus.md"
                if isinstance(focus_path_value, Path):
                    focus_title = self._markdown_sidebar_markdown_title(focus_path_value, focus_path_value.name)
                focus_title_html = html.escape(focus_title)
                focus_close = ""
                if focus_path_attr:
                    focus_close = f"<button class='close' data-action='close-node' data-node='{esc(tutor_node_id)}'>x</button>"
                focus_history = f"<button class='action-btn' data-action='show-history' data-node='{esc(tutor_node_id)}' title='history question'>Q</button>"

                children.append(
                    f"<div class='{tutor_classes}' data-node='{esc(tutor_node_id)}'>"
                    f"<div class='node-header' data-kind='tutor' data-node='{esc(tutor_node_id)}' draggable='true'>"
                    f"<span class='twisty' data-action='toggle-node' data-node='{esc(tutor_node_id)}'>&#9656;</span>"
                    f"<span class='node-title focus-title' data-action='activate' data-path='{focus_path_attr}'>{focus_title_html}</span>"
                    f"{focus_history}"
                    f"{focus_close}"
                    "</div>"
                    f"<div class='children'>{''.join(tutor_children)}</div>"
                    "</div>"
                )

            group_focus_button = ""
            if node_id != "other":
                group_focus_button = (
                    f"<button class='action-btn' data-action='show-tutor-focus' data-node='{esc(node_id)}' title='history ask tutor'>A</button>"
                )

            blocks.append(
                f"<div class='{classes}' data-node='{esc(node_id)}'>"
                f"<div class='node-header' data-kind='group' data-node='{esc(node_id)}' draggable='true'>"
                f"<span class='twisty' data-action='toggle-node' data-node='{esc(node_id)}'>&#9656;</span>"
                f"<span class='node-title' data-action='toggle-node' data-node='{esc(node_id)}'>{html.escape(str(group.get('title', '')))}</span>"
                f"{group_focus_button}"
                f"<button class='close' data-action='close-node' data-node='{esc(node_id)}'>x</button>"
                "</div>"
                f"<div class='children'>{''.join(children)}</div>"
                "</div>"
            )

        empty_html = "<div class='empty'>No markdown tabs open.</div>"
        if blocks:
            empty_html = "".join(blocks)

        styles = """
        *, *::before, *::after { box-sizing: border-box; }
        html, body { height: 100%; width: 100%; }
        body {
            margin: 0;
            font-family: Segoe UI, Arial, sans-serif;
            font-size: 12px;
            background: #f6f7fb;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }
        body.collapsed { font-size: 0; }
        body.collapsed .content { display: none; }
        .toolbar { flex: 0 0 auto; position: sticky; top: 0; padding: 8px; display: flex; gap: 8px; align-items: center; background: #ffffff; border-bottom: 1px solid #e5e7eb; }
        .btn { width: 28px; height: 28px; border: 1px solid #d1d5db; border-radius: 8px; background: #fff; cursor: pointer; display: inline-flex; align-items: center; justify-content: center; padding: 0; }
        .btn:hover { background: #f9fafb; }
        .toolbar-title { font-weight: 600; color: #374151; }
        .toolbar-actions { display: flex; gap: 8px; align-items: center; }
        body.collapsed .toolbar-title, body.collapsed .toolbar-actions { display: none; }
        .spacer { flex: 1 1 auto; }
        .content { flex: 1 1 auto; min-height: 0; padding: 8px; overflow-y: auto; overflow-x: hidden; }
        .empty { padding: 10px; color: #6b7280; }
        .node { margin: 6px 0; }
        .node-header { display: flex; align-items: center; gap: 6px; padding: 4px 6px; border-radius: 8px; }
        .node-header:hover { background: rgba(17, 24, 39, 0.05); }
        .node.active > .node-header { background: rgba(37, 99, 235, 0.10); }
        .node-header[draggable='true'] { cursor: grab; }
        .twisty { width: 16px; text-align: center; cursor: pointer; user-select: none; }
        .node-title { flex: 1 1 auto; font-weight: 600; cursor: pointer; user-select: none; }
        .children { padding-left: 14px; }
        .node.collapsed > .children { display: none; }
        .node.collapsed > .node-header .twisty { transform: rotate(-90deg); display: inline-block; }
        .leaf { display: flex; gap: 6px; padding: 6px; border-radius: 10px; background: #fff; border: 1px solid #e5e7eb; margin: 4px 0; }
        .leaf.active { border-color: #60a5fa; box-shadow: 0 0 0 2px rgba(37,99,235,0.10); }
        .leaf-main { flex: 1 1 auto; min-width: 0; cursor: pointer; user-select: none; }
        .leaf-title { font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .leaf-preview { color: #6b7280; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .close { border: 0; background: transparent; cursor: pointer; color: #6b7280; width: 22px; height: 22px; border-radius: 6px; }
        .close:hover { background: rgba(239,68,68,0.10); color: #ef4444; }
        .action-btn { border: 0; background: transparent; cursor: pointer; color: #6b7280; width: 22px; height: 22px; border-radius: 6px; }
        .action-btn:hover { background: rgba(37,99,235,0.10); color: #1d4ed8; }
        .drag-over { outline: 2px dashed rgba(37, 99, 235, 0.55); }
        .dragging { opacity: 0.5; }
        .focus-title { font-weight: 700; }
        .inline-edit {
            width: 100%;
            font: inherit;
            font-size: 12px;
            padding: 2px 6px;
            border: 1px solid rgba(17, 24, 39, 0.20);
            border-radius: 6px;
            outline: none;
            background: #fff;
        }
        .inline-edit:focus {
            border-color: rgba(37, 99, 235, 0.70);
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.10);
        }
        """

        script = f"""
        <script>
        (function() {{
            const ACTION_BASE = '{_SIDEBAR_ACTION_SCHEME}://{_SIDEBAR_ACTION_HOST}/';
            function act(path) {{
                const sep = path.includes('?') ? '&' : '?';
                let url = ACTION_BASE + path + sep + '_=' + Date.now();
                const el = document.querySelector('.content');
                if (el) {{
                    const max = Math.max(0, el.scrollHeight - el.clientHeight);
                    url += '&st=' + encodeURIComponent(el.scrollTop || 0) + '&sm=' + encodeURIComponent(max);
                }}
                window.location.href = url;
            }}

            document.addEventListener('click', (e) => {{
                const actionEl = e.target.closest('[data-action]');
                if (actionEl) {{
                    const action = actionEl.dataset.action;
                    if (action === 'toggle-sidebar') {{ act('toggle'); return; }}
                    if (action === 'open-all') {{ act('open-all'); return; }}
                    if (action === 'toggle-node') {{
                        const node = actionEl.dataset.node || '';
                        if (node) act('toggle-node?node=' + encodeURIComponent(node));
                        return;
                    }}
                    if (action === 'activate') {{
                        const path = actionEl.dataset.path || '';
                        if (path) act('activate?path=' + encodeURIComponent(path));
                        return;
                    }}
                    if (action === 'close-node') {{
                        const node = actionEl.dataset.node || '';
                        if (node) act('close-node?node=' + encodeURIComponent(node));
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }}
                    if (action === 'show-tutor-focus') {{
                        const node = actionEl.dataset.node || '';
                        if (node) act('show-tutor-focus?node=' + encodeURIComponent(node));
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }}
                    if (action === 'show-history') {{
                        const node = actionEl.dataset.node || '';
                        if (node) act('show-history?node=' + encodeURIComponent(node));
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }}
                    if (action === 'close') {{
                        const path = actionEl.dataset.path || '';
                        if (path) act('close?path=' + encodeURIComponent(path));
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }}
                }}
                const leaf = e.target.closest('.leaf');
                if (leaf && leaf.dataset.path) {{
                    act('activate?path=' + encodeURIComponent(leaf.dataset.path));
                }}
            }});

            function startInlineEdit(container, onCommit) {{
                if (!container) return;
                if (container.querySelector('input.inline-edit')) return;
                const previousText = container.textContent || '';
                const input = document.createElement('input');
                input.type = 'text';
                input.value = previousText.trim();
                input.className = 'inline-edit';
                container.textContent = '';
                container.appendChild(input);
                input.focus();
                input.select();

                let done = false;
                function finish(shouldCommit) {{
                    if (done) return;
                    done = true;
                    const value = (input.value || '').trim();
                    if (shouldCommit) {{
                        if (value === previousText.trim()) {{
                            container.textContent = previousText;
                            return;
                        }}
                        onCommit(value);
                        return;
                    }}
                    container.textContent = previousText;
                }}

                input.addEventListener('keydown', (ev) => {{
                    if (ev.key === 'Enter') {{ ev.preventDefault(); finish(true); }}
                    else if (ev.key === 'Escape') {{ ev.preventDefault(); finish(false); }}
                }});
                input.addEventListener('blur', () => finish(true));
                input.addEventListener('click', (ev) => ev.stopPropagation());
                input.addEventListener('contextmenu', (ev) => {{ ev.preventDefault(); ev.stopPropagation(); }});
            }}

            document.addEventListener('contextmenu', (e) => {{
                const leafTitle = e.target.closest('.leaf-title');
                if (leafTitle) {{
                    const leaf = leafTitle.closest('.leaf');
                    const path = leaf ? (leaf.dataset.path || '') : '';
                    if (path) {{
                        e.preventDefault();
                        e.stopPropagation();
                        startInlineEdit(leafTitle, (value) => {{
                            act('rename-md?path=' + encodeURIComponent(path) + '&name=' + encodeURIComponent(value));
                        }});
                        return;
                    }}
                }}

                const mdTitle = e.target.closest('.node-title[data-path]');
                if (mdTitle && mdTitle.dataset.path) {{
                    e.preventDefault();
                    e.stopPropagation();
                    startInlineEdit(mdTitle, (value) => {{
                        act('rename-md?path=' + encodeURIComponent(mdTitle.dataset.path) + '&name=' + encodeURIComponent(value));
                    }});
                    return;
                }}

                const groupTitle = e.target.closest('.node.group > .node-header .node-title');
                if (groupTitle) {{
                    const header = groupTitle.closest('.node-header');
                    const kind = header ? (header.dataset.kind || '') : '';
                    const node = header ? (header.dataset.node || '') : '';
                    if (kind !== 'group' || !node) return;
                    e.preventDefault();
                    e.stopPropagation();
                    startInlineEdit(groupTitle, (value) => {{
                        act('rename-group?node=' + encodeURIComponent(node) + '&name=' + encodeURIComponent(value));
                    }});
                }}
            }});

            function parseDragData(raw) {{
                if (!raw) return null;
                const parts = raw.split('|');
                if (parts.length < 3) return null;
                if (parts[0] === 'node') {{
                    return {{ type: 'node', kind: parts[1], id: parts[2] }};
                }}
                if (parts[0] === 'leaf') {{
                    return {{ type: 'leaf', path: parts[1], parent: parts[2] }};
                }}
                return null;
            }}

            document.addEventListener('dragstart', (e) => {{
                const header = e.target.closest('.node-header[draggable=\"true\"]');
                if (header && header.dataset.kind && header.dataset.node) {{
                    e.dataTransfer.setData('text/plain', 'node|' + header.dataset.kind + '|' + header.dataset.node);
                    e.dataTransfer.effectAllowed = 'move';
                    header.classList.add('dragging');
                    return;
                }}
                const leaf = e.target.closest('.leaf');
                if (leaf && leaf.dataset.path) {{
                    const parent = leaf.dataset.parent || '';
                    e.dataTransfer.setData('text/plain', 'leaf|' + leaf.dataset.path + '|' + parent);
                    e.dataTransfer.effectAllowed = 'move';
                    leaf.classList.add('dragging');
                }}
            }});

            document.addEventListener('dragend', () => {{
                document.querySelectorAll('.dragging').forEach(el => el.classList.remove('dragging'));
                document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
            }});

            document.addEventListener('dragover', (e) => {{
                const header = e.target.closest('.node-header[draggable=\"true\"]');
                const leaf = e.target.closest('.leaf');
                if (!header && !leaf) return;
                e.preventDefault();
                if (header) header.classList.add('drag-over');
                if (leaf) leaf.classList.add('drag-over');
                e.dataTransfer.dropEffect = 'move';
            }});

            document.addEventListener('dragleave', (e) => {{
                const header = e.target.closest('.node-header[draggable=\"true\"]');
                const leaf = e.target.closest('.leaf');
                if (header) header.classList.remove('drag-over');
                if (leaf) leaf.classList.remove('drag-over');
            }});

            document.addEventListener('drop', (e) => {{
                const header = e.target.closest('.node-header[draggable=\"true\"]');
                const leaf = e.target.closest('.leaf');
                if (!header && !leaf) return;
                e.preventDefault();
                if (header) header.classList.remove('drag-over');
                if (leaf) leaf.classList.remove('drag-over');

                const data = parseDragData(e.dataTransfer.getData('text/plain'));
                if (!data) return;

                if (header && data.type === 'node') {{
                    const dstKind = header.dataset.kind || '';
                    const dstId = header.dataset.node || '';
                    if (!dstKind || !dstId) return;
                    if (data.kind !== dstKind) return;
                    if (data.id === dstId) return;
                    act('move-node?src=' + encodeURIComponent(data.id) + '&dst=' + encodeURIComponent(dstId));
                    return;
                }}

                if (leaf && data.type === 'leaf') {{
                    const dstPath = leaf.dataset.path || '';
                    const dstParent = leaf.dataset.parent || '';
                    if (!dstPath || !dstParent) return;
                    if (dstParent !== data.parent) return;
                    if (dstPath === data.path) return;
                    act('move?src=' + encodeURIComponent(data.path) + '&dst=' + encodeURIComponent(dstPath));
                }}
            }});
        }})();
        </script>
        """

        return (
            "<!DOCTYPE html>"
            "<html><head><meta charset='UTF-8'>"
            f"<style>{styles}</style>{head_assets}"
            "</head><body class='"
            + collapsed_class
            + "'>"
            "<div class='toolbar'>"
            "<button class='btn' data-action='toggle-sidebar' title='Toggle sidebar' aria-label='Toggle sidebar'>"
            "<svg viewBox='0 0 16 16' width='14' height='14' aria-hidden='true'>"
            "<path d='M2 3.5h12a1 1 0 0 1 0 2H2a1 1 0 0 1 0-2zm0 4h12a1 1 0 0 1 0 2H2a1 1 0 0 1 0-2zm0 4h12a1 1 0 0 1 0 2H2a1 1 0 0 1 0-2z'/>"
            "</svg>"
            "</button>"
            "<div class='toolbar-title'>Exocortex</div>"
            "<div class='spacer'></div>"
            "<div class='toolbar-actions'>"
            "<button class='btn' data-action='open-all' title='Open all markdown under asset' aria-label='Open all markdown under asset'>"
            "<svg viewBox='0 0 16 16' width='14' height='14' aria-hidden='true'>"
            "<path d='M8 1.5a.75.75 0 0 1 .75.75v5.19l1.72-1.72a.75.75 0 1 1 1.06 1.06L8 10.31 4.47 6.78a.75.75 0 1 1 1.06-1.06l1.72 1.72V2.25A.75.75 0 0 1 8 1.5z'/>"
            "<path d='M2.5 10.5a.75.75 0 0 1 .75.75v1.25c0 .55.45 1 1 1h7.5c.55 0 1-.45 1-1v-1.25a.75.75 0 0 1 1.5 0v1.25c0 1.38-1.12 2.5-2.5 2.5h-7.5c-1.38 0-2.5-1.12-2.5-2.5v-1.25a.75.75 0 0 1 .75-.75z'/>"
            "</svg>"
            "</button>"
            "</div>"
            "</div>"
            "<div class='content'>"
            + empty_html
            + "</div>"
            + script
            + "</body></html>"
        )

    def _build_markdown_sidebar_html(self) -> str:
        return self._build_markdown_sidebar_tree_html()
        head_assets = markdown_helper.katex_assets()
        collapsed_class = "collapsed" if self._markdown_sidebar_collapsed else ""

        active_path: Path | None = None
        if self._current_markdown_path:
            try:
                active_path = self._current_markdown_path.resolve()
            except Exception:
                active_path = self._current_markdown_path

        items_in_order: list[tuple[str, str, str, Path, bool]] = []
        for tab_index in range(self._markdown_tabs.count()):
            widget = self._markdown_tabs.widget(tab_index)
            if not isinstance(widget, QtWebEngineWidgets.QWebEngineView):
                continue
            markdown_path = self._markdown_path_for_view(widget)
            if not markdown_path:
                continue
            try:
                resolved = markdown_path.resolve()
            except Exception:
                resolved = markdown_path
            if not resolved.is_file():
                continue

            group = self._markdown_sidebar_group_for_path(resolved)
            title = (self._markdown_tabs.tabText(tab_index) or resolved.name).strip() or resolved.name
            preview = self._markdown_sidebar_preview_for_path(resolved)
            is_active = bool(active_path and resolved == active_path)
            items_in_order.append((group, title, preview, resolved, is_active))

        grouped: dict[str, list[tuple[str, str, Path, bool]]] = {}
        for group, title, preview, path, is_active in items_in_order:
            grouped.setdefault(group, []).append((title, preview, path, is_active))

        groups_html: list[str] = []
        for group, group_items in grouped.items():
            rows: list[str] = []
            for title, preview, path, is_active in group_items:
                classes = "item active" if is_active else "item"
                path_attr = html.escape(str(path), quote=True)
                title_html = html.escape(title)
                preview_html = html.escape(preview)
                rows.append(
                    f"""<div class="{classes}" draggable="true" data-path="{path_attr}">
                        <div class="item-main">
                            <div class="item-title">{title_html}</div>
                            <div class="item-preview">{preview_html}</div>
                        </div>
                        <button class="icon-btn close" data-action="close" title="Close tab" aria-label="Close tab">
                            <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
                                <path d="M3.3 3.3a1 1 0 0 1 1.4 0L8 6.6l3.3-3.3a1 1 0 1 1 1.4 1.4L9.4 8l3.3 3.3a1 1 0 0 1-1.4 1.4L8 9.4l-3.3 3.3a1 1 0 0 1-1.4-1.4L6.6 8 3.3 4.7a1 1 0 0 1 0-1.4z"/>
                            </svg>
                        </button>
                    </div>"""
                )

            group_title = html.escape(group)
            groups_html.append(
                f"""<div class="group">
                        <div class="group-header" role="button" tabindex="0" aria-label="Toggle group">
                            <span class="chevron" aria-hidden="true"></span>
                            <span class="group-title">{group_title}</span>
                            <span class="count">{len(group_items)}</span>
                        </div>
                        <div class="group-items">
                            {''.join(rows)}
                        </div>
                    </div>"""
            )

        empty_html = (
            "<div class='empty'>No markdown tabs open.</div>"
            if not items_in_order
            else "".join(groups_html)
        )

        styles = """
        html, body { height: 100%; }
        body {
            margin: 0;
            padding: 0;
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
            color: #111827;
            background: #f6f7fb;
            user-select: none;
        }
        body.collapsed { font-size: 0; }
        .toolbar {
            position: sticky;
            top: 0;
            z-index: 10;
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 10px 10px 8px 10px;
            background: linear-gradient(to bottom, rgba(246,247,251,0.98), rgba(246,247,251,0.90));
            backdrop-filter: blur(8px);
            border-bottom: 1px solid rgba(17,24,39,0.08);
        }
        .toolbar-title {
            font-size: 12px;
            font-weight: 600;
            color: #374151;
            letter-spacing: 0.2px;
        }
        body.collapsed .toolbar-title { display: none; }
        .spacer { flex: 1 1 auto; }
        .icon-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 30px;
            height: 30px;
            border-radius: 8px;
            border: 1px solid rgba(17,24,39,0.12);
            background: #ffffff;
            cursor: pointer;
            padding: 0;
        }
        .icon-btn:hover { background: #f9fafb; }
        .icon-btn svg { fill: #374151; }
        .content {
            padding: 8px 8px 12px 8px;
            height: calc(100% - 49px);
            overflow-y: auto;
            overflow-x: hidden;
        }
        body.collapsed .content { display: none; }
        .empty {
            font-size: 13px;
            color: #6b7280;
            padding: 12px;
        }
        .group { margin-bottom: 10px; }
        .group-header {
            display: flex;
            align-items: center;
            gap: 8px;
            padding: 6px 8px;
            border-radius: 8px;
            color: #374151;
            cursor: pointer;
        }
        .group-header:hover { background: rgba(17,24,39,0.04); }
        .chevron {
            width: 10px;
            height: 10px;
            border-right: 2px solid #6b7280;
            border-bottom: 2px solid #6b7280;
            transform: rotate(45deg);
            margin-left: 2px;
            transition: transform 0.12s ease;
        }
        .group.collapsed .chevron { transform: rotate(-45deg); }
        .group-title {
            font-size: 12px;
            font-weight: 600;
            flex: 1 1 auto;
        }
        .count {
            font-size: 11px;
            padding: 2px 6px;
            border-radius: 999px;
            background: rgba(37, 99, 235, 0.10);
            color: #1d4ed8;
        }
        .group.collapsed .group-items { display: none; }
        .item {
            display: flex;
            align-items: stretch;
            gap: 8px;
            padding: 8px 8px;
            margin: 4px 0;
            border-radius: 10px;
            background: #ffffff;
            border: 1px solid rgba(17,24,39,0.10);
        }
        .item:hover { border-color: rgba(37, 99, 235, 0.35); }
        .item.active {
            border-color: rgba(37, 99, 235, 0.75);
            box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.10);
        }
        .item.drag-over { outline: 2px dashed rgba(37, 99, 235, 0.55); }
        .item.dragging { opacity: 0.5; }
        .item-main { flex: 1 1 auto; min-width: 0; }
        .item-title {
            font-size: 12px;
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            margin-bottom: 4px;
        }
        .item-preview {
            font-size: 12px;
            color: #6b7280;
            line-height: 1.25;
            overflow: hidden;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
        }
        .icon-btn.close {
            width: 28px;
            height: 28px;
            border-radius: 8px;
            border: 1px solid transparent;
            background: transparent;
        }
        .icon-btn.close:hover { background: rgba(239,68,68,0.10); }
        .icon-btn.close svg { fill: rgba(17,24,39,0.65); }
        .icon-btn.close:hover svg { fill: #ef4444; }
        """

        script = f"""
        <script>
        (function() {{
            const ACTION_BASE = '{_SIDEBAR_ACTION_SCHEME}://{_SIDEBAR_ACTION_HOST}/';
            function act(path) {{
                const sep = path.includes('?') ? '&' : '?';
                window.location.href = ACTION_BASE + path + sep + '_=' + Date.now();
            }}

            document.addEventListener('click', (e) => {{
                const toggle = e.target.closest('[data-action=\"toggle-sidebar\"]');
                if (toggle) {{
                    act('toggle');
                    return;
                }}

                const closeBtn = e.target.closest('[data-action=\"close\"]');
                if (closeBtn) {{
                    const item = closeBtn.closest('.item');
                    if (item && item.dataset.path) {{
                        e.preventDefault();
                        e.stopPropagation();
                        act('close?path=' + encodeURIComponent(item.dataset.path));
                    }}
                    return;
                }}

                const groupHeader = e.target.closest('.group-header');
                if (groupHeader) {{
                    const group = groupHeader.closest('.group');
                    if (group) group.classList.toggle('collapsed');
                    return;
                }}

                const item = e.target.closest('.item');
                if (item && item.dataset.path) {{
                    act('activate?path=' + encodeURIComponent(item.dataset.path));
                }}
            }});

            document.addEventListener('keydown', (e) => {{
                if (e.key !== 'Enter' && e.key !== ' ') return;
                const header = e.target.closest('.group-header');
                if (!header) return;
                e.preventDefault();
                const group = header.closest('.group');
                if (group) group.classList.toggle('collapsed');
            }});

            document.addEventListener('dragstart', (e) => {{
                const item = e.target.closest('.item');
                if (!item || !item.dataset.path) return;
                e.dataTransfer.setData('text/plain', item.dataset.path);
                e.dataTransfer.effectAllowed = 'move';
                item.classList.add('dragging');
            }});

            document.addEventListener('dragend', (e) => {{
                document.querySelectorAll('.item.dragging').forEach(el => el.classList.remove('dragging'));
                document.querySelectorAll('.item.drag-over').forEach(el => el.classList.remove('drag-over'));
            }});

            document.addEventListener('dragover', (e) => {{
                const item = e.target.closest('.item');
                if (!item) return;
                e.preventDefault();
                item.classList.add('drag-over');
                e.dataTransfer.dropEffect = 'move';
            }});

            document.addEventListener('dragleave', (e) => {{
                const item = e.target.closest('.item');
                if (!item) return;
                item.classList.remove('drag-over');
            }});

            document.addEventListener('drop', (e) => {{
                const item = e.target.closest('.item');
                if (!item || !item.dataset.path) return;
                e.preventDefault();
                item.classList.remove('drag-over');
                const src = e.dataTransfer.getData('text/plain');
                const dst = item.dataset.path;
                if (!src || !dst || src === dst) return;
                act('move?src=' + encodeURIComponent(src) + '&dst=' + encodeURIComponent(dst));
            }});
        }})();
        </script>
        """

        html_text = (
            "<!DOCTYPE html>"
            f"<html><head><meta charset='UTF-8'><style>{styles}</style>{head_assets}"
            "</head>"
            f"<body class='{collapsed_class}'>"
            "<div class='toolbar'>"
            "<button class='icon-btn' data-action='toggle-sidebar' title='Toggle sidebar' aria-label='Toggle sidebar'>"
            "<svg viewBox='0 0 16 16' width='14' height='14' aria-hidden='true'>"
            "<path d='M2 3.5h12a1 1 0 0 1 0 2H2a1 1 0 0 1 0-2zm0 4h12a1 1 0 0 1 0 2H2a1 1 0 0 1 0-2zm0 4h12a1 1 0 0 1 0 2H2a1 1 0 0 1 0-2z'/>"
            "</svg>"
            "</button>"
            "<div class='toolbar-title'>Markdown</div>"
            "<div class='spacer'></div>"
            "</div>"
            f"<div class='content'>{empty_html}</div>"
            f"{script}"
            "</body></html>"
        )
        return html_text

    def _refresh_markdown_sidebar(self) -> None:
        view = self._markdown_sidebar_view
        if view is None:
            return
        self._markdown_sidebar_refresh_seq = getattr(self, "_markdown_sidebar_refresh_seq", 0) + 1
        refresh_seq = self._markdown_sidebar_refresh_seq
        try:
            html_text = self._build_markdown_sidebar_html()
        except Exception as exc:  # pragma: no cover - GUI runtime path
            logger.warning("Failed to build markdown sidebar: %s", exc)
            html_text = "<html><body></body></html>"

        base_url = QtCore.QUrl.fromLocalFile(str(Path(__file__).resolve().parent))
        page = view.page()
        if page is None:
            view.setHtml(html_text, baseUrl=base_url)
            return

        if getattr(self, "_markdown_sidebar_scroll_asset", None) != self._current_asset_name:
            self._markdown_sidebar_scroll_asset = self._current_asset_name
            self._markdown_sidebar_saved_scroll_top = 0

        if not self._open_markdown_paths():
            self._markdown_sidebar_saved_scroll_top = 0

        def _set_html_with_scroll(scroll_top: int | None) -> None:
            if getattr(self, "_markdown_sidebar_refresh_seq", 0) != refresh_seq:
                return
            if scroll_top is not None:

                def _restore_scroll(_ok: bool) -> None:
                    try:
                        view.loadFinished.disconnect(_restore_scroll)
                    except Exception:
                        pass
                    if getattr(self, "_markdown_sidebar_refresh_seq", 0) != refresh_seq:
                        return
                    page = view.page()
                    if page is None:
                        return
                    page.runJavaScript(
                        "(function(){const el=document.querySelector('.content');"
                        f"if(el) el.scrollTop={int(scroll_top)};"
                        "})();"
                    )

                view.loadFinished.connect(_restore_scroll)
            view.setHtml(html_text, baseUrl=base_url)

        def _on_scroll_captured(value: object) -> None:
            scroll_top: int | None = None
            scroll_max: int | None = None
            if isinstance(value, dict):
                top_raw = value.get("top")
                max_raw = value.get("max")
                if isinstance(top_raw, (int, float)) and top_raw >= 0:
                    scroll_top = int(top_raw)
                if isinstance(max_raw, (int, float)) and max_raw >= 0:
                    scroll_max = int(max_raw)
            elif isinstance(value, (int, float)) and value >= 0:
                scroll_top = int(value)

            saved = int(getattr(self, "_markdown_sidebar_saved_scroll_top", 0) or 0)
            if scroll_max is not None and scroll_max > 0:
                if scroll_top is not None:
                    saved = int(scroll_top)
            elif scroll_top is not None and scroll_top > 0:
                saved = int(scroll_top)

            self._markdown_sidebar_saved_scroll_top = saved
            _set_html_with_scroll(saved)

        if getattr(self, "_markdown_sidebar_scroll_skip_capture", False):
            self._markdown_sidebar_scroll_skip_capture = False
            saved = int(getattr(self, "_markdown_sidebar_saved_scroll_top", 0) or 0)
            _set_html_with_scroll(saved)
            return

        try:
            page.runJavaScript(
                "(function(){const el=document.querySelector('.content');"
                "if(!el) return null;"
                "const max=Math.max(0, el.scrollHeight - el.clientHeight);"
                "return {top: el.scrollTop, max: max};})();",
                0,
                _on_scroll_captured,
            )
        except TypeError:
            view.setHtml(html_text, baseUrl=base_url)

    @staticmethod
    def _decode_sidebar_query_path(raw: str) -> Path | None:
        if not raw:
            return None
        try:
            decoded = QtCore.QUrl.fromPercentEncoding(raw.encode("utf-8"))
        except Exception:
            decoded = raw
        if not decoded:
            decoded = raw
        try:
            return Path(decoded)
        except Exception:
            return None

    def _open_all_markdown_under_current_asset(self) -> None:
        if self._feynman_mode_active:
            self.statusBar().showMessage("Feynman mode is active; opening markdown is disabled.")
            return
        asset_name = self._current_asset_name
        if not asset_name:
            self.statusBar().showMessage("Load an asset to open markdown.")
            return

        asset_dir = get_asset_dir(asset_name)
        if not asset_dir.is_dir():
            self.statusBar().showMessage(f"Asset directory not found: {asset_dir}")
            return

        try:
            md_paths = sorted(asset_dir.rglob("*.md"), key=lambda p: str(p).lower())
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to scan markdown: {exc}")
            return

        if not md_paths:
            self.statusBar().showMessage("No markdown found under asset.")
            return

        for path in md_paths:
            self._open_markdown_file(path)

    def _reorder_markdown_tabs_by_paths(self, desired_paths: list[Path]) -> None:
        tab_bar = self._markdown_tabs.tabBar()
        self._markdown_tabs_reordering = True
        try:
            for target_index, path in enumerate(desired_paths):
                current_index = self._find_markdown_tab(path)
                if current_index is None or current_index == target_index:
                    continue
                tab_bar.moveTab(current_index, target_index)
        finally:
            self._markdown_tabs_reordering = False

    def _move_markdown_group_block(self, src_group: int, dst_group: int) -> None:
        if src_group == dst_group:
            return

        order = self._open_markdown_paths()
        if not order:
            return

        blocks: dict[str, list[Path]] = {}
        node_order: list[str] = []
        seen_nodes: set[str] = set()

        for path in order:
            context = self._group_context_from_markdown(path)
            if context:
                _asset_name, group_idx, _group_dir = context
                node_id = self._sidebar_node_id("group", group_idx)
            else:
                node_id = "other"

            blocks.setdefault(node_id, []).append(path)
            if node_id not in seen_nodes:
                seen_nodes.add(node_id)
                node_order.append(node_id)

        src_node = self._sidebar_node_id("group", src_group)
        dst_node = self._sidebar_node_id("group", dst_group)
        if src_node not in node_order or dst_node not in node_order:
            return

        src_pos = node_order.index(src_node)
        dst_pos = node_order.index(dst_node)
        if src_pos == dst_pos:
            return

        node_order.pop(src_pos)
        if src_pos < dst_pos:
            dst_pos -= 1
            insert_pos = dst_pos + 1
        else:
            insert_pos = dst_pos
        node_order.insert(insert_pos, src_node)

        new_order: list[Path] = []
        for node_id in node_order:
            new_order.extend(blocks.get(node_id, []))
        if new_order == order:
            return

        self._reorder_markdown_tabs_by_paths(new_order)
        self._persist_asset_ui_state()

    def _move_markdown_tab_block(self, src_paths: set[Path], dst_paths: set[Path]) -> None:
        if not src_paths or not dst_paths:
            return
        if src_paths & dst_paths:
            return

        order = self._open_markdown_paths()
        src_block = [path for path in order if path in src_paths]
        if not src_block:
            return
        dst_block = [path for path in order if path in dst_paths]
        if not dst_block:
            return

        src_first = next((idx for idx, path in enumerate(order) if path in src_paths), None)
        dst_first = next((idx for idx, path in enumerate(order) if path in dst_paths), None)
        if src_first is None or dst_first is None:
            return

        remaining = [path for path in order if path not in src_paths]
        insert_index: int | None = None
        if src_first < dst_first:
            last_dst_index: int | None = None
            for idx, path in enumerate(remaining):
                if path in dst_paths:
                    last_dst_index = idx
            if last_dst_index is None:
                return
            insert_index = last_dst_index + 1
        else:
            for idx, path in enumerate(remaining):
                if path in dst_paths:
                    insert_index = idx
                    break
            if insert_index is None:
                return

        new_order = remaining[:insert_index] + src_block + remaining[insert_index:]
        if new_order == order:
            return
        self._reorder_markdown_tabs_by_paths(new_order)
        self._persist_asset_ui_state()

    def _handle_markdown_sidebar_action_url(self, url: QtCore.QUrl) -> None:
        action = url.path().lstrip("/")
        query = QtCore.QUrlQuery(url)

        self._markdown_sidebar_scroll_skip_capture = False
        scroll_top: int | None = None
        scroll_max: int | None = None
        raw_scroll_top = query.queryItemValue("st")
        raw_scroll_max = query.queryItemValue("sm")
        if raw_scroll_top:
            try:
                scroll_top = max(0, int(raw_scroll_top))
            except Exception:
                scroll_top = None
        if raw_scroll_max:
            try:
                scroll_max = max(0, int(raw_scroll_max))
            except Exception:
                scroll_max = None

        if scroll_top is not None or scroll_max is not None:
            saved = int(getattr(self, "_markdown_sidebar_saved_scroll_top", 0) or 0)
            if scroll_max is not None and scroll_max > 0:
                if scroll_top is not None:
                    saved = int(scroll_top)
            elif scroll_top is not None and scroll_top > 0:
                saved = int(scroll_top)
            self._markdown_sidebar_saved_scroll_top = saved
            self._markdown_sidebar_scroll_skip_capture = True

        if action == "rename-group":
            raw_node = query.queryItemValue("node")
            raw_name = query.queryItemValue("name")
            node_id = ""
            alias_value = ""
            if raw_node:
                try:
                    node_id = QtCore.QUrl.fromPercentEncoding(raw_node.encode("utf-8"))
                except Exception:
                    node_id = raw_node
            if raw_name:
                try:
                    alias_value = QtCore.QUrl.fromPercentEncoding(raw_name.encode("utf-8"))
                except Exception:
                    alias_value = raw_name
            parsed = self._parse_sidebar_node_id(node_id)
            if parsed and parsed[0] == "group" and len(parsed[1]) == 1:
                group_index = parsed[1][0]
                asset_name = self._current_asset_name
                if asset_name:
                    group_dir = get_group_data_dir(asset_name) / str(group_index)
                    if group_dir.is_dir():
                        self._set_markdown_sidebar_group_alias(group_dir, group_index, alias_value)
            self._refresh_markdown_sidebar()
            return

        if action == "rename-md":
            path = self._decode_sidebar_query_path(query.queryItemValue("path"))
            raw_name = query.queryItemValue("name")
            alias_value = ""
            if raw_name:
                try:
                    alias_value = QtCore.QUrl.fromPercentEncoding(raw_name.encode("utf-8"))
                except Exception:
                    alias_value = raw_name
            if path:
                try:
                    resolved = path.resolve()
                except Exception:
                    resolved = path
                if not self._group_context_from_markdown(resolved):
                    self.statusBar().showMessage("Alias is supported for asset markdown only.")
                else:
                    display_title = self._set_markdown_sidebar_markdown_alias(resolved, alias_value)
                    tab_index = self._find_markdown_tab(resolved)
                    if tab_index is not None:
                        self._markdown_tabs.setTabText(tab_index, display_title)
            self._refresh_markdown_sidebar()
            return

        if action == "toggle":
            self._set_markdown_sidebar_collapsed(not self._markdown_sidebar_collapsed)
            return

        if action == "open-all":
            self._open_all_markdown_under_current_asset()
            self._refresh_markdown_sidebar()
            return

        if action == "toggle-node":
            raw_node = query.queryItemValue("node")
            if raw_node:
                try:
                    node_id = QtCore.QUrl.fromPercentEncoding(raw_node.encode("utf-8"))
                except Exception:
                    node_id = raw_node
                if node_id:
                    if node_id in self._markdown_sidebar_collapsed_nodes:
                        self._markdown_sidebar_collapsed_nodes.discard(node_id)
                    else:
                        self._markdown_sidebar_collapsed_nodes.add(node_id)
            self._persist_asset_ui_state()
            self._refresh_markdown_sidebar()
            return

        if action == "activate":
            path = self._decode_sidebar_query_path(query.queryItemValue("path"))
            if path:
                tab_index = self._find_markdown_tab(path)
                if tab_index is not None:
                    self._markdown_tabs.setCurrentIndex(tab_index)
                elif path.is_file():
                    self._open_markdown_file(path)
            self._refresh_markdown_sidebar()
            return

        if action == "close":
            path = self._decode_sidebar_query_path(query.queryItemValue("path"))
            if path:
                tab_index = self._find_markdown_tab(path)
                if tab_index is not None:
                    self._close_markdown_tab(tab_index)
            self._refresh_markdown_sidebar()
            return

        if action == "close-node":
            raw_node = query.queryItemValue("node")
            node_id = ""
            if raw_node:
                try:
                    node_id = QtCore.QUrl.fromPercentEncoding(raw_node.encode("utf-8"))
                except Exception:
                    node_id = raw_node

            parsed = self._parse_sidebar_node_id(node_id)
            open_paths = self._open_markdown_paths()
            if parsed:
                kind, nums = parsed
                if kind == "group" and len(nums) == 1:
                    group_index = nums[0]
                    to_close: set[Path] = set()
                    for path in open_paths:
                        ctx = self._group_context_from_markdown(path)
                        if ctx and ctx[1] == group_index:
                            to_close.add(path)
                    self._close_markdown_tabs_for_paths(to_close)
                    return
                if kind == "tutor" and len(nums) == 2:
                    group_index, tutor_index = nums
                    to_close: set[Path] = set()
                    for path in open_paths:
                        ctx = self._tutor_context_from_markdown(path)
                        if not ctx:
                            continue
                        _asset_name, ctx_group, ctx_tutor, _tutor_dir = ctx
                        if ctx_group == group_index and ctx_tutor == tutor_index:
                            to_close.add(path)
                    self._close_markdown_tabs_for_paths(to_close)
                    return
                if kind == "other" and not nums:
                    to_close = {path for path in open_paths if not self._group_context_from_markdown(path)}
                    self._close_markdown_tabs_for_paths(to_close)
                    return
            self._refresh_markdown_sidebar()
            return

        if action == "show-tutor-focus":
            raw_node = query.queryItemValue("node")
            node_id = ""
            if raw_node:
                try:
                    node_id = QtCore.QUrl.fromPercentEncoding(raw_node.encode("utf-8"))
                except Exception:
                    node_id = raw_node
            parsed = self._parse_sidebar_node_id(node_id)
            if parsed and parsed[0] == "group" and len(parsed[1]) == 1:
                asset_name = self._current_asset_name
                if asset_name:
                    group_index = parsed[1][0]
                    QtCore.QTimer.singleShot(
                        0,
                        lambda a=asset_name, g=group_index: self._show_tutor_focus_list_for_group(a, g),
                    )
            self._markdown_sidebar_scroll_skip_capture = False
            return

        if action == "show-history":
            raw_node = query.queryItemValue("node")
            node_id = ""
            if raw_node:
                try:
                    node_id = QtCore.QUrl.fromPercentEncoding(raw_node.encode("utf-8"))
                except Exception:
                    node_id = raw_node
            parsed = self._parse_sidebar_node_id(node_id)
            if parsed and parsed[0] == "tutor" and len(parsed[1]) == 2:
                asset_name = self._current_asset_name
                if asset_name:
                    group_index, tutor_index = parsed[1]
                    session_dir = get_group_data_dir(asset_name) / str(group_index) / "tutor_data" / str(tutor_index)
                    if session_dir.is_dir():
                        QtCore.QTimer.singleShot(
                            0,
                            lambda d=session_dir: self._show_history_questions_for_session_dir(d),
                        )
            self._markdown_sidebar_scroll_skip_capture = False
            return

        if action == "move":
            src_path = self._decode_sidebar_query_path(query.queryItemValue("src"))
            dst_path = self._decode_sidebar_query_path(query.queryItemValue("dst"))
            if src_path and dst_path and src_path != dst_path:
                src_index = self._find_markdown_tab(src_path)
                dst_index = self._find_markdown_tab(dst_path)
                if src_index is not None and dst_index is not None:
                    self._markdown_tabs.tabBar().moveTab(src_index, dst_index)
                    self._persist_asset_ui_state()
            self._refresh_markdown_sidebar()
            return

        if action == "move-node":
            raw_src = query.queryItemValue("src")
            raw_dst = query.queryItemValue("dst")
            if raw_src and raw_dst:
                try:
                    src_id = QtCore.QUrl.fromPercentEncoding(raw_src.encode("utf-8"))
                except Exception:
                    src_id = raw_src
                try:
                    dst_id = QtCore.QUrl.fromPercentEncoding(raw_dst.encode("utf-8"))
                except Exception:
                    dst_id = raw_dst

                parsed_src = self._parse_sidebar_node_id(src_id)
                parsed_dst = self._parse_sidebar_node_id(dst_id)
                if parsed_src and parsed_dst and parsed_src[0] == parsed_dst[0]:
                    kind = parsed_src[0]
                    src_nums = parsed_src[1]
                    dst_nums = parsed_dst[1]
                    if kind == "group" and len(src_nums) == 1 and len(dst_nums) == 1:
                        src_group = src_nums[0]
                        dst_group = dst_nums[0]
                        self._move_markdown_group_block(src_group, dst_group)
                    elif kind == "tutor" and len(src_nums) == 2 and len(dst_nums) == 2:
                        src_group, src_tutor = src_nums
                        dst_group, dst_tutor = dst_nums
                        if src_group == dst_group:
                            src_paths = set()
                            dst_paths = set()
                            for path in self._open_markdown_paths():
                                context = self._tutor_context_from_markdown(path)
                                if not context:
                                    continue
                                _asset_name, group_idx, tutor_idx, _tutor_dir = context
                                if group_idx != src_group:
                                    continue
                                if tutor_idx == src_tutor:
                                    src_paths.add(path)
                                elif tutor_idx == dst_tutor:
                                    dst_paths.add(path)
                            self._move_markdown_tab_block(src_paths, dst_paths)
            self._refresh_markdown_sidebar()
            return

        logger.debug("Unhandled markdown sidebar action: %s", action)
        self._markdown_sidebar_scroll_skip_capture = False

    @QtCore.Slot(int, int)
    def _on_markdown_tab_moved(self, _from_index: int, _to_index: int) -> None:
        if self._markdown_tabs_reordering:
            return
        self._persist_asset_ui_state()
        self._refresh_markdown_sidebar()

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
        self._refresh_markdown_sidebar()

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

    def _close_markdown_tabs_for_paths(self, paths: set[Path]) -> None:
        if not paths:
            return

        tab_entries: list[tuple[int, Path]] = []
        for path in paths:
            try:
                resolved = path.resolve()
            except Exception:
                resolved = path
            view = self._markdown_views.get(resolved)
            if not view:
                continue
            index = self._markdown_tabs.indexOf(view)
            if index < 0:
                continue
            tab_entries.append((index, resolved))

        if not tab_entries:
            return

        self._markdown_tabs.blockSignals(True)
        try:
            for index, resolved in sorted(tab_entries, key=lambda item: item[0], reverse=True):
                widget = self._markdown_tabs.widget(index)
                if widget:
                    self._markdown_tabs.removeTab(index)
                    if resolved in self._markdown_views and self._markdown_views[resolved] is widget:
                        del self._markdown_views[resolved]
                    else:
                        for candidate_path, view in list(self._markdown_views.items()):
                            if view is widget:
                                del self._markdown_views[candidate_path]
                                break
        finally:
            self._markdown_tabs.blockSignals(False)

        if not self._markdown_views:
            self._markdown_tabs.setTabsClosable(False)
            self._show_markdown_placeholder()
        self._set_current_markdown_path(self._resolve_current_markdown_path())

    def _schedule_persist_asset_ui_state(self) -> None:
        if self._asset_config_persist_suspended:
            return
        if not self._current_asset_name:
            return
        self._asset_ui_state_persist_timer.start()

    @staticmethod
    def _encode_splitter_state(splitter: QtWidgets.QSplitter | None) -> str | None:
        if splitter is None:
            return None
        try:
            state = splitter.saveState()
        except Exception:
            return None
        if not state:
            return None
        try:
            return bytes(state.toBase64()).decode("ascii")
        except Exception:
            return None

    @staticmethod
    def _restore_splitter_state(splitter: QtWidgets.QSplitter | None, raw: object) -> bool:
        if splitter is None or not isinstance(raw, str) or not raw.strip():
            return False
        try:
            state = QtCore.QByteArray.fromBase64(raw.encode("ascii"))
        except Exception:
            return False
        try:
            return bool(splitter.restoreState(state))
        except Exception:
            return False

    @staticmethod
    def _parse_splitter_sizes(raw: object) -> list[int] | None:
        if not isinstance(raw, list) or len(raw) != 2:
            return None
        sizes: list[int] = []
        for item in raw:
            if not isinstance(item, (int, float)):
                return None
            sizes.append(max(1, int(item)))
        return sizes

    def _capture_current_markdown_scroll_position(self) -> None:
        asset_name = self._current_asset_name
        if not asset_name:
            return
        view = self._current_markdown_view()
        if not view:
            return
        markdown_path = self._markdown_path_for_view(view)
        if not markdown_path:
            return
        try:
            pos = view.page().scrollPosition()
            scroll_y = float(pos.y())
        except Exception:
            return
        key = self._serialize_asset_markdown_path(asset_name, markdown_path)
        self._markdown_scroll_y_by_path[key] = scroll_y

    def _queue_markdown_scroll_restore(self, view: QtWebEngineWidgets.QWebEngineView, path: Path) -> None:
        asset_name = self._current_asset_name
        if not asset_name:
            return
        key = self._serialize_asset_markdown_path(asset_name, path)
        scroll_y = self._markdown_scroll_y_by_path.get(key)
        if scroll_y is None:
            return
        view.setProperty("_pending_scroll_restore_y", float(scroll_y))

    def _apply_pending_markdown_scroll_restore(self, view: QtWebEngineWidgets.QWebEngineView) -> None:
        raw = view.property("_pending_scroll_restore_y")
        if raw is None:
            return
        view.setProperty("_pending_scroll_restore_y", None)
        try:
            scroll_y = float(raw)
        except Exception:
            return
        if scroll_y <= 0:
            return
        try:
            view.page().runJavaScript(f"window.scrollTo(0, {int(scroll_y)});")
        except Exception:
            return

    def _persist_asset_ui_state(self) -> None:
        if self._asset_config_persist_suspended:
            return
        asset_name = self._current_asset_name
        if not asset_name:
            return
        self._capture_current_markdown_scroll_position()
        config: dict[str, object] = {"zoom": float(self._zoom)}
        config["markdown_sidebar_collapsed"] = bool(self._markdown_sidebar_collapsed)
        splitter_state = self._encode_splitter_state(self._splitter)
        if splitter_state:
            config["main_splitter_state_b64"] = splitter_state
        sidebar_state = self._encode_splitter_state(self._markdown_sidebar_splitter)
        if sidebar_state:
            config["markdown_sidebar_splitter_state_b64"] = sidebar_state
        if self._splitter:
            config["main_splitter_sizes"] = [int(v) for v in self._splitter.sizes()]
        if self._markdown_sidebar_splitter:
            config["markdown_sidebar_splitter_sizes"] = [
                int(v) for v in self._markdown_sidebar_splitter.sizes()
            ]
        if self._markdown_sidebar_splitter and not self._markdown_sidebar_collapsed:
            sizes = self._markdown_sidebar_splitter.sizes()
            if len(sizes) == 2 and sizes[0] > 0:
                self._markdown_sidebar_restore_width = int(sizes[0])
        config["markdown_sidebar_restore_width"] = (
            int(self._markdown_sidebar_restore_width) if self._markdown_sidebar_restore_width is not None else None
        )
        config["markdown_sidebar_collapsed_nodes"] = sorted(self._markdown_sidebar_collapsed_nodes)
        scroll_bar = self._view.verticalScrollBar()
        scroll_value = int(scroll_bar.value())
        scroll_max = int(scroll_bar.maximum())
        config["pdf_scroll_value"] = scroll_value
        config["pdf_scroll_fraction"] = float(scroll_value) / scroll_max if scroll_max > 0 else 0.0
        open_markdown_paths = self._open_markdown_paths()
        open_markdown_keys = {
            self._serialize_asset_markdown_path(asset_name, path) for path in open_markdown_paths
        }
        if self._current_markdown_path:
            open_markdown_keys.add(
                self._serialize_asset_markdown_path(asset_name, self._current_markdown_path)
            )
        config["markdown_scroll_y"] = {
            key: float(value)
            for key, value in self._markdown_scroll_y_by_path.items()
            if key in open_markdown_keys
        }
        config["open_markdown_paths"] = [
            self._serialize_asset_markdown_path(asset_name, path)
            for path in open_markdown_paths
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
        config = load_asset_config(asset_name) or {}

        self._markdown_scroll_y_by_path = {}
        scroll_raw = config.get("markdown_scroll_y")
        if isinstance(scroll_raw, dict):
            for key, value in scroll_raw.items():
                if not isinstance(key, str) or not key:
                    continue
                if isinstance(value, (int, float)):
                    self._markdown_scroll_y_by_path[key] = float(value)

        restored_main_splitter = self._restore_splitter_state(
            self._splitter, config.get("main_splitter_state_b64")
        )
        restored_sidebar_splitter = self._restore_splitter_state(
            self._markdown_sidebar_splitter, config.get("markdown_sidebar_splitter_state_b64")
        )
        splitter_sizes = self._parse_splitter_sizes(config.get("main_splitter_sizes"))
        if splitter_sizes and self._splitter and not restored_main_splitter:
            self._splitter.setSizes(splitter_sizes)
        sidebar_sizes = self._parse_splitter_sizes(config.get("markdown_sidebar_splitter_sizes"))
        if sidebar_sizes and self._markdown_sidebar_splitter and not restored_sidebar_splitter:
            self._markdown_sidebar_splitter.setSizes(sidebar_sizes)

        sidebar_collapsed = config.get("markdown_sidebar_collapsed")
        collapsed = bool(sidebar_collapsed) if isinstance(sidebar_collapsed, bool) else False

        sidebar_restore_width_raw = config.get("markdown_sidebar_restore_width")
        restore_width: int | None = None
        if isinstance(sidebar_restore_width_raw, (int, float)):
            candidate = int(sidebar_restore_width_raw)
            if candidate > 0:
                restore_width = candidate
        self._markdown_sidebar_restore_width = restore_width

        collapsed_nodes_raw = config.get("markdown_sidebar_collapsed_nodes")
        collapsed_nodes: set[str] = set()
        if isinstance(collapsed_nodes_raw, list):
            for item in collapsed_nodes_raw:
                if isinstance(item, str) and item:
                    collapsed_nodes.add(item)
        self._markdown_sidebar_collapsed_nodes = collapsed_nodes
        self._set_markdown_sidebar_collapsed(collapsed, update_restore_width=False)

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

        pdf_scroll_fraction_raw = config.get("pdf_scroll_fraction")
        pdf_scroll_fraction: float | None = None
        if isinstance(pdf_scroll_fraction_raw, (int, float)):
            candidate = float(pdf_scroll_fraction_raw)
            if 0.0 <= candidate <= 1.0:
                pdf_scroll_fraction = candidate
        pdf_scroll_value_raw = config.get("pdf_scroll_value")
        pdf_scroll_value: int | None = None
        if isinstance(pdf_scroll_value_raw, (int, float)):
            pdf_scroll_value = int(pdf_scroll_value_raw)

        QtCore.QTimer.singleShot(
            0,
            lambda _asset=asset_name, _fraction=pdf_scroll_fraction, _value=pdf_scroll_value: self._restore_pdf_scroll(
                _asset, _fraction, _value
            ),
        )

    def _restore_pdf_scroll(
        self, asset_name: str, scroll_fraction: float | None, scroll_value: int | None
    ) -> None:
        if self._current_asset_name != asset_name:
            return
        scroll_bar = self._view.verticalScrollBar()
        maximum = int(scroll_bar.maximum())
        target: int | None = None
        if scroll_fraction is not None and maximum > 0:
            target = int(round(scroll_fraction * maximum))
        elif scroll_value is not None:
            target = int(scroll_value)
        if target is None:
            return
        scroll_bar.setValue(max(0, min(target, maximum)))

    def _update_prompt_visibility(self) -> None:
        if self._feynman_mode_active:
            visible = self._feynman_questions_enabled
            self._prompt_container.setVisible(visible)
            enabled = visible and not self._ask_in_progress and not self._bug_finder_in_progress
            self._ask_button.setEnabled(enabled)
            self._prompt_input.setEnabled(enabled)
            return

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
        integrate_visible = False
        if self._current_markdown_path:
            integrate_visible = self._tutor_context_from_markdown(self._current_markdown_path) is not None
        if self._feynman_mode_active:
            integrate_visible = False
        self._integrate_button.setVisible(integrate_visible)
        self._skip_feynman_button.setVisible(integrate_visible)
        self._integrate_button.setEnabled(
            integrate_visible and not self._integrate_in_progress
        )
        self._skip_feynman_button.setEnabled(
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
        return

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

    def _build_history_items(self, tutor_session_dir: Path) -> list[tuple[str, str, Path]]:
        ask_history_dir = tutor_session_dir / "ask_history"
        if not ask_history_dir.is_dir():
            return []

        def _order_key(path: Path) -> tuple[int, str]:
            stem = path.stem
            try:
                return int(stem), stem
            except Exception:
                return 1_000_000, stem

        entries: list[tuple[str, str, Path]] = []
        for path in sorted(ask_history_dir.glob("*.md"), key=_order_key):
            entries.append((path.name, self._markdown_preview(path), path))
        return entries

    def _markdown_preview(self, markdown_path: Path) -> str:
        try:
            content = markdown_path.read_text(encoding="utf-8")
        except Exception:  # pragma: no cover - GUI runtime path
            return ""
        return " ".join(content.split())

    def _collect_tutor_focus_items(
        self, asset_name: str, group_idx: int | None = None
    ) -> list[tuple[str, str, Path]]:
        group_data_dir = get_group_data_dir(asset_name)
        if not group_data_dir.is_dir():
            return []

        def _order_key(path: Path) -> tuple[int, str]:
            name = path.name
            try:
                return int(name), name
            except Exception:
                return 1_000_000, name

        items: list[tuple[str, str, Path]] = []
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
                preview = self._markdown_preview(focus_path)
                items.append((session_dir.name, preview, focus_path))
        return items

    def _show_tutor_focus_list_for_group(self, asset_name: str, group_idx: int) -> None:
        items = self._collect_tutor_focus_items(asset_name, group_idx)
        if not items:
            self.statusBar().showMessage("No tutor focus found for this group.")
            return
        dialog = self._tutor_focus_dialog
        if not dialog:
            dialog = _TutorFocusDialog(parent=self)
            self._tutor_focus_dialog = dialog
        dialog.set_items(items)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        selected = dialog.selected_paths()
        if not selected:
            self.statusBar().showMessage("No focus.md selected.")
            return
        for path in selected:
            self._open_markdown_file(path)

    def _show_history_questions_for_session_dir(self, tutor_session_dir: Path) -> None:
        entries = self._build_history_items(tutor_session_dir)
        if not entries:
            self.statusBar().showMessage("No tutor history found.")
            return
        dialog = self._tutor_history_dialog
        if not dialog:
            dialog = _TutorHistoryDialog(parent=self)
            self._tutor_history_dialog = dialog
        dialog.set_items(entries)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return
        for path in dialog.selected_paths():
            self._open_markdown_file(path)

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
        dialog = self._tutor_focus_dialog
        if not dialog:
            dialog = _TutorFocusDialog(parent=self)
            self._tutor_focus_dialog = dialog
        dialog.set_items(items)
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
        dialog = self._tutor_history_dialog
        if not dialog:
            dialog = _TutorHistoryDialog(parent=self)
            self._tutor_history_dialog = dialog
        dialog.set_items(entries)
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

    def _on_markdown_tab_changed(self, index: int) -> None:
        if self._markdown_tabs_reordering:
            return
        if self._feynman_mode_active and self._feynman_locked_tab_index is not None:
            locked = self._feynman_locked_tab_index
            if locked != index and 0 <= locked < self._markdown_tabs.count():
                self._markdown_tabs.blockSignals(True)
                try:
                    self._markdown_tabs.setCurrentIndex(locked)
                finally:
                    self._markdown_tabs.blockSignals(False)
                return
        self._set_current_markdown_path(self._resolve_current_markdown_path())

    def _handle_integrate(self) -> None:
        if self._feynman_mode_active:
            self.statusBar().showMessage("Feynman mode is already active.")
            return
        if self._integrate_in_progress:
            self.statusBar().showMessage("start feynman already in progress.")
            return
        if not self._current_markdown_path:
            self.statusBar().showMessage("Open a tutor markdown first.")
            return
        context = self._tutor_context_from_markdown(self._current_markdown_path)
        if not context:
            self.statusBar().showMessage("start feynman is only available in tutor_data.")
            return

        asset_name, group_idx, tutor_idx, tutor_session_dir = context
        prompt = (
            "Are you sure you want to enter Feynman mode?\n"
            "You will not be able to view AI-generated content.\n"
            "You must independently write on paper a full explanation and derivation of everything you just learned from Ask Tutor."
        )
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Enter Feynman Mode",
            prompt,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        note_path = tutor_session_dir / "note.md"
        if note_path.is_file():
            try:
                existing_note = note_path.read_text(encoding="utf-8").lstrip("\ufeff")
            except Exception:  # pragma: no cover - defensive
                existing_note = ""
            try:
                group_dir = get_group_data_dir(asset_name) / str(group_idx)
                enhanced_md = group_dir / "img_explainer_data" / "enhanced.md"
                if existing_note and enhanced_md.is_file():
                    enhanced_content = enhanced_md.read_text(encoding="utf-8")
                    if existing_note in enhanced_content:
                        enhanced_md.write_text(
                            enhanced_content.replace(existing_note, "", 1),
                            encoding="utf-8",
                            newline="\n",
                        )
            except Exception:  # pragma: no cover - GUI runtime path
                pass
            note_path.unlink(missing_ok=True)

        self._enter_feynman_mode(asset_name, group_idx, tutor_idx, tutor_session_dir)

        self._integrate_in_progress = True
        self._update_prompt_visibility()
        self._update_history_button_visibility()
        self.statusBar().showMessage(f"start feynman (group {group_idx}, tutor {tutor_idx})")
        task = _IntegrateTask(asset_name, group_idx, tutor_idx)
        task.signals.finished.connect(self._on_integrate_finished)
        task.signals.failed.connect(self._on_integrate_failed)
        self._integrate_pool.start(task)

    def _handle_skip_feynman(self) -> None:
        if self._feynman_mode_active:
            self.statusBar().showMessage("Feynman mode is already active.")
            return
        if self._integrate_in_progress:
            self.statusBar().showMessage("Integrator already in progress.")
            return
        if not self._current_markdown_path:
            self.statusBar().showMessage("Open a tutor markdown first.")
            return
        context = self._tutor_context_from_markdown(self._current_markdown_path)
        if not context:
            self.statusBar().showMessage("skip feynman is only available in tutor_data.")
            return

        asset_name, group_idx, tutor_idx, _tutor_session_dir = context
        prompt = "Are you sure you want to skip Feynman mode and let the AI generate the notes directly?"
        confirm = QtWidgets.QMessageBox.question(
            self,
            "Skip Feynman Mode",
            prompt,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        self._integrate_in_progress = True
        self._update_prompt_visibility()
        self._update_history_button_visibility()
        self.statusBar().showMessage(f"Integrating (group {group_idx}, tutor {tutor_idx})")
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
            self.statusBar().showMessage(f"Integrator updated {path.name}")
        else:
            self.statusBar().showMessage(f"Integrator updated {output_path}")

        self._maybe_start_feynman_bug_review()

    @QtCore.Slot(str)
    def _on_integrate_failed(self, error: str) -> None:
        self._integrate_in_progress = False
        self._update_prompt_visibility()
        self._update_history_button_visibility()
        self.statusBar().showMessage(f"Integrator failed: {error}")

        if self._feynman_pending_review:
            self._feynman_pending_review = False
            self._feynman_submit_button.setEnabled(True)

    def _enter_feynman_mode(
        self,
        asset_name: str,
        group_idx: int,
        tutor_idx: int,
        tutor_session_dir: Path,
    ) -> None:
        view = self._ensure_feynman_view()
        tab_index = self._markdown_tabs.indexOf(view)

        self._feynman_mode_active = True
        self._feynman_context = (asset_name, group_idx, tutor_idx, tutor_session_dir)
        self._feynman_pending_review = False
        self._feynman_locked_tab_index = tab_index
        self._feynman_questions_enabled = False

        tab_bar = self._markdown_tabs.tabBar()
        tab_bar.setEnabled(False)
        tab_bar.setVisible(False)
        if self._markdown_sidebar_view:
            self._markdown_sidebar_view.setEnabled(False)

        self._feynman_finish_button.setVisible(False)
        self._feynman_controls.setVisible(True)
        self._feynman_submit_button.setEnabled(True)
        self._update_prompt_visibility()

        feiman_html = Path(__file__).resolve().parents[1] / "feiman.html"
        if feiman_html.is_file():
            view.load(QtCore.QUrl.fromLocalFile(str(feiman_html)))
        else:
            view.setHtml("<html><body><h2>Feynman mode</h2><p>Missing feiman.html</p></body></html>")

    def _exit_feynman_mode(self) -> None:
        self._feynman_mode_active = False
        self._feynman_locked_tab_index = None
        self._feynman_context = None
        self._feynman_pending_review = False
        self._feynman_questions_enabled = False

        tab_bar = self._markdown_tabs.tabBar()
        tab_bar.setEnabled(True)
        tab_bar.setVisible(False)
        if self._markdown_sidebar_view:
            self._markdown_sidebar_view.setEnabled(True)

        self._feynman_controls.setVisible(False)
        self._feynman_finish_button.setVisible(False)
        self._bug_finder_in_progress = False
        self._update_prompt_visibility()
        self._update_history_button_visibility()

    def _ensure_feynman_view(self) -> QtWebEngineWidgets.QWebEngineView:
        view = self._feynman_view
        if view is not None and self._markdown_tabs.indexOf(view) >= 0:
            self._markdown_tabs.blockSignals(True)
            try:
                self._markdown_tabs.setCurrentWidget(view)
            finally:
                self._markdown_tabs.blockSignals(False)
            return view

        self._remove_markdown_placeholder()

        view = QtWebEngineWidgets.QWebEngineView()
        view.setContextMenuPolicy(QtCore.Qt.NoContextMenu)
        index = self._markdown_tabs.addTab(view, "Feynman")
        self._markdown_tabs.setCurrentIndex(index)
        self._markdown_tabs.setTabsClosable(True)
        self._feynman_view = view
        return view

    def _handle_feynman_finish(self) -> None:
        if not self._feynman_mode_active or not self._feynman_context:
            return

        if self._bug_finder_in_progress:
            self.statusBar().showMessage("Bug review is still running.")
            return

        asset_name, group_idx, tutor_idx, _tutor_session_dir = self._feynman_context
        try:
            enhanced_md = insert_feynman_original_image(asset_name, group_idx, tutor_idx)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"finish improvement failed: {exc}")
            return

        self.statusBar().showMessage("Inserted manuscript image into enhanced.md.")
        self._exit_feynman_mode()
        self._open_markdown_file(enhanced_md, tab_label=f"Group {group_idx}: enhanced.md")

        if self._student_note_in_progress:
            self.statusBar().showMessage("Student note generation already in progress.")
            return
        self._student_note_in_progress = True
        task = _StudentNoteTask(asset_name, group_idx, tutor_idx)
        task.signals.finished.connect(self._on_student_note_finished)
        task.signals.failed.connect(self._on_student_note_failed)
        self._student_note_pool.start(task)

    def _handle_feynman_submit(self) -> None:
        if not self._feynman_mode_active or not self._feynman_context:
            self.statusBar().showMessage("Start Feynman mode first.")
            return
        if self._feynman_pending_review:
            self.statusBar().showMessage("A deduction review is already queued.")
            return
        if self._bug_finder_in_progress:
            self.statusBar().showMessage("Bug review already in progress.")
            return

        dialog = _FeynmanManuscriptDialog(self)
        if dialog.exec() != QtWidgets.QDialog.Accepted:
            return

        source_paths = dialog.selected_paths()
        if not source_paths:
            return

        _asset_name, _group_idx, _tutor_idx, tutor_session_dir = self._feynman_context
        tutor_session_dir.mkdir(parents=True, exist_ok=True)

        manuscript_name_re = re.compile(r"^manuscript(?:_\\d+)?\\.png$", re.IGNORECASE)
        for entry in tutor_session_dir.iterdir():
            if entry.is_file() and manuscript_name_re.match(entry.name):
                entry.unlink(missing_ok=True)
        (tutor_session_dir / "student.png").unlink(missing_ok=True)

        for idx, source_path in enumerate(source_paths, start=1):
            image = QtGui.QImage(str(source_path))
            if image.isNull():
                self.statusBar().showMessage(f"Failed to load image: {source_path}")
                return
            target = tutor_session_dir / f"manuscript_{idx}.png"
            target.unlink(missing_ok=True)
            if not image.save(str(target), "PNG"):
                self.statusBar().showMessage(f"Failed to save {target.name}.")
                return

        self._feynman_submit_button.setEnabled(False)
        self._feynman_pending_review = True
        self._maybe_start_feynman_bug_review()

    def _maybe_start_feynman_bug_review(self) -> None:
        if not self._feynman_mode_active or not self._feynman_context:
            return
        if self._bug_finder_in_progress or not self._feynman_pending_review:
            return

        asset_name, group_idx, tutor_idx, tutor_session_dir = self._feynman_context
        has_manuscript = any(tutor_session_dir.glob("manuscript_*.png"))
        has_manuscript |= (tutor_session_dir / "manuscript.png").is_file()
        has_manuscript |= (tutor_session_dir / "student.png").is_file()
        if not has_manuscript:
            return

        note_path = tutor_session_dir / "note.md"
        if not note_path.is_file():
            if self._integrate_in_progress:
                self.statusBar().showMessage("Waiting for note.md...")
                return
            self.statusBar().showMessage("note.md not found. Please start Feynman mode again.")
            return

        self._feynman_pending_review = False
        self._bug_finder_in_progress = True
        self._feynman_submit_button.setEnabled(False)
        self._update_prompt_visibility()
        self.statusBar().showMessage(f"Reviewing deduction (group {group_idx}, tutor {tutor_idx})...")

        task = _BugFinderTask(asset_name, group_idx, tutor_idx)
        task.signals.finished.connect(self._on_bug_finder_finished)
        task.signals.failed.connect(self._on_bug_finder_failed)
        self._bug_finder_pool.start(task)

    @QtCore.Slot(str)
    def _on_bug_finder_finished(self, output_path: str) -> None:
        self._bug_finder_in_progress = False
        self._feynman_submit_button.setEnabled(True)
        self._feynman_finish_button.setVisible(True)
        self._feynman_questions_enabled = True
        self._update_prompt_visibility()

        path = Path(output_path)
        if path.is_file():
            self.statusBar().showMessage(f"Updated {path.name}")
            self._show_feynman_markdown(path)
        else:
            self.statusBar().showMessage(f"Updated {output_path}")

    @QtCore.Slot(str)
    def _on_bug_finder_failed(self, error: str) -> None:
        self._bug_finder_in_progress = False
        self._feynman_submit_button.setEnabled(True)
        self._update_prompt_visibility()
        self.statusBar().showMessage(f"Bug review failed: {error}")

    @QtCore.Slot(str)
    def _on_student_note_finished(self, output_path: str) -> None:
        self._student_note_in_progress = False
        path = Path(output_path)
        if path.is_file():
            self.statusBar().showMessage(f"Inserted note_student into {path.name}")
            self._refresh_open_markdown_file(path)
            return
        self.statusBar().showMessage(f"Inserted note_student into {output_path}")

    @QtCore.Slot(str)
    def _on_student_note_failed(self, error: str) -> None:
        self._student_note_in_progress = False
        self.statusBar().showMessage(f"Student note failed: {error}")

    def _show_feynman_markdown(self, path: Path) -> None:
        view = self._feynman_view
        if not view or not path.is_file():
            return
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to read {path.name}: {exc}")
            return
        try:
            html = markdown_helper.render_markdown_content(content)
        except Exception as exc:  # pragma: no cover - GUI runtime path
            self.statusBar().showMessage(f"Failed to render markdown: {exc}")
            return
        base_url = QtCore.QUrl.fromLocalFile(str(path.parent))
        view.setHtml(html, baseUrl=base_url)

    def _handle_ask(self) -> None:
        text = self._prompt_input.toPlainText().strip()
        if not text:
            self.statusBar().showMessage("Enter a question first.")
            return
        if self._ask_in_progress:
            self.statusBar().showMessage("Ask already in progress.")
            return
        if self._feynman_mode_active:
            if not self._feynman_context or not self._feynman_questions_enabled:
                self.statusBar().showMessage("Submit your deduction first.")
                return
            if self._bug_finder_in_progress:
                self.statusBar().showMessage("Bug review is still running.")
                return

            asset_name, group_idx, tutor_idx, _tutor_session_dir = self._feynman_context
            self._ask_in_progress = True
            self._update_prompt_visibility()
            preview = text if len(text) <= 60 else f"{text[:60]}..."
            self.statusBar().showMessage(f"Ask (re_tutor, group {group_idx}, tutor {tutor_idx}): {preview}")
            task = _ReTutorTask(asset_name, group_idx, tutor_idx, text)
            task.signals.finished.connect(self._on_re_tutor_finished)
            task.signals.failed.connect(self._on_re_tutor_failed)
            self._ask_pool.start(task)
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
    def _on_re_tutor_finished(self, output_path: str) -> None:
        self._ask_in_progress = False
        self._update_prompt_visibility()
        self._prompt_input.clear()

        path = Path(output_path)
        if self._feynman_mode_active and path.is_file():
            self._show_feynman_markdown(path)
        if path.is_file():
            self.statusBar().showMessage(f"Updated {path.name}")
            return
        self.statusBar().showMessage(f"Updated {output_path}")

    @QtCore.Slot(str)
    def _on_re_tutor_failed(self, error: str) -> None:
        self._ask_in_progress = False
        self._update_prompt_visibility()
        self.statusBar().showMessage(f"Ask (re_tutor) failed: {error}")

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
        if self._feynman_mode_active:
            self.statusBar().showMessage("Feynman mode is active; opening other markdown is disabled.")
            return

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
        title = self._markdown_sidebar_markdown_title(resolved, title)
        existing_index = self._find_markdown_tab(resolved)
        if existing_index is not None:
            widget = self._markdown_tabs.widget(existing_index)
            if isinstance(widget, QtWebEngineWidgets.QWebEngineView):
                self._configure_markdown_view(widget, resolved)
                self._queue_markdown_scroll_restore(widget, resolved)
                widget.setHtml(html, baseUrl=QtCore.QUrl.fromLocalFile(str(resolved.parent)))
            if self._markdown_tabs.tabText(existing_index) != title:
                self._markdown_tabs.setTabText(existing_index, title)
            self._markdown_tabs.setCurrentIndex(existing_index)
            self._set_current_markdown_path(resolved)
            self.statusBar().showMessage(f"Updated {title}")
            return

        view = QtWebEngineWidgets.QWebEngineView()
        self._configure_markdown_view(view, resolved)
        self._queue_markdown_scroll_restore(view, resolved)
        view.setHtml(html, baseUrl=QtCore.QUrl.fromLocalFile(str(resolved.parent)))
        index = self._markdown_tabs.addTab(view, title)
        self._markdown_tabs.setCurrentIndex(index)
        self._markdown_tabs.setTabsClosable(True)
        self._markdown_views[resolved] = view
        self._set_current_markdown_path(resolved)
        self.statusBar().showMessage(f"Opened {title}")

    def _refresh_open_markdown_file(self, path: Path) -> None:
        if self._feynman_mode_active:
            return
        resolved = path.resolve()
        existing_index = self._find_markdown_tab(resolved)
        if existing_index is None:
            return
        widget = self._markdown_tabs.widget(existing_index)
        if not isinstance(widget, QtWebEngineWidgets.QWebEngineView):
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
        self._configure_markdown_view(widget, resolved)
        self._queue_markdown_scroll_restore(widget, resolved)
        widget.setHtml(html, baseUrl=QtCore.QUrl.fromLocalFile(str(resolved.parent)))

    def _configure_markdown_view(self, view: QtWebEngineWidgets.QWebEngineView, path: Path) -> None:
        view.setProperty("markdown_path", str(path))
        if not view.property("_markdown_context_menu_ready"):
            view.setProperty("_markdown_context_menu_ready", True)
            view.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
            view.customContextMenuRequested.connect(
                lambda point, _view=view: self._show_markdown_context_menu(_view, point)
            )

        if not view.property("_markdown_scroll_tracking_ready"):
            view.setProperty("_markdown_scroll_tracking_ready", True)
            try:
                view.page().scrollPositionChanged.connect(
                    lambda pos, _view=view: self._on_markdown_scroll_position_changed(_view, pos)
                )
            except Exception:
                pass
            view.loadFinished.connect(
                lambda ok, _view=view: self._on_markdown_view_load_finished(_view, ok)
            )

    def _on_markdown_scroll_position_changed(
        self, view: QtWebEngineWidgets.QWebEngineView, pos: QtCore.QPointF
    ) -> None:
        asset_name = self._current_asset_name
        if not asset_name:
            return
        markdown_path = self._markdown_path_for_view(view)
        if not markdown_path:
            return
        key = self._serialize_asset_markdown_path(asset_name, markdown_path)
        try:
            scroll_y = float(pos.y())
        except Exception:
            return
        self._markdown_scroll_y_by_path[key] = scroll_y
        self._schedule_persist_asset_ui_state()

    def _on_markdown_view_load_finished(
        self, view: QtWebEngineWidgets.QWebEngineView, ok: bool
    ) -> None:
        if not ok:
            return
        self._apply_pending_markdown_scroll_restore(view)

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
            self._schedule_persist_asset_ui_state()
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
        self._schedule_persist_asset_ui_state()

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
