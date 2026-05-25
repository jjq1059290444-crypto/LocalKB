"""main_window.py — main window: sidebar navigation + page stack."""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QStatusBar, QFrame, QComboBox,
)
from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon, QMouseEvent, QColor
from PySide6.QtWidgets import QGraphicsDropShadowEffect

from pages.chat_page import ChatPage
from workers.warmup_worker import WarmupWorker

NAV_ITEMS = [
    ("nav.chat", 0),
    ("nav.kb_manage", 1),
    ("nav.settings", 2),
    ("nav.api_config", 3),
    ("nav.about", 4),
]


def _model_display_name(model_name: str) -> str:
    """Convert a model name/ID/path into a short display label."""
    if not model_name:
        return "—"
    # Extract the last segment from paths like "BAAI/bge-m3" or filesystem paths
    parts = model_name.replace("\\", "/").split("/")
    name = parts[-1]
    # Known friendly names
    friendly = {
        "bge-m3": "BGE-M3",
        "bge-small-zh-v1.5": "bge-small-zh-v1.5",
        "all-MiniLM-L6-v2": "all-MiniLM-L6-v2",
    }
    return friendly.get(name, name)


class _SidebarButton(QPushButton):
    """Sidebar navigation button."""

    def __init__(self, text, page_idx, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(42)
        self.setStyleSheet("""
            QPushButton {
                text-align: center;
                padding: 9px 14px;
                border-radius: 10px;
                color: #2D3436;
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #ECEEF2;
                color: #2D3436;
            }
            QPushButton:checked {
                background: #E5E7EB;
                color: #2D3436;
                font-weight: 600;
            }
        """)


class MainWindow(QMainWindow):
    """Application main window."""

    def __init__(self, qa_chain=None, vector_store=None, config_manager=None,
                 i18n=None, embed_model_name="BAAI/bge-small-zh-v1.5",
                 use_sparse=False):
        super().__init__()
        self.qa_chain = qa_chain
        self.vector_store = vector_store
        self.config_manager = config_manager
        self._i18n = i18n
        self._embed_model_name = embed_model_name
        self._use_sparse = use_sparse

        # Connect language changed signal
        if self._i18n:
            self._i18n.language_changed.connect(self._on_language_changed)

        self.setWindowTitle(self._i18n.t("app.name") if self._i18n else "LocalKB")
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.resize(1320, 840)
        self.setMinimumSize(980, 640)
        self._drag_pos = None

        # Central widget with frame + shadow
        central = QFrame()
        central.setObjectName("windowFrame")
        central.setStyleSheet(
            "#windowFrame { border: 1px solid #000000; background: #FFFFFF; }"
        )
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(12)
        shadow.setOffset(0, 0)
        shadow.setColor(QColor(0, 0, 0, 60))
        central.setGraphicsEffect(shadow)
        self.setCentralWidget(central)
        outer_layout = QVBoxLayout(central)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        # Custom title bar
        title_bar = QFrame()
        title_bar.setFixedHeight(36)
        title_bar.setStyleSheet("""
            QFrame { background: #FFFFFF; border-bottom: 1px solid #E5E7EB; }
        """)

        def _dbl_click(event):
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

        title_bar.mousePressEvent = self._title_press
        title_bar.mouseMoveEvent = self._title_move
        title_bar.mouseReleaseEvent = self._title_release
        title_bar.mouseDoubleClickEvent = _dbl_click
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(12, 0, 4, 0)

        self._title_lbl = QLabel(
            f"  {self._i18n.t('app.name') if self._i18n else 'LocalKB'}  "
        )
        self._title_lbl.setStyleSheet(
            "color: #A0AEC0; font-size: 12px; border: none; background: transparent;"
        )
        title_layout.addWidget(self._title_lbl)
        title_layout.addStretch()

        # Title bar buttons
        icons_dir = Path(__file__).resolve().parent / "icons"
        btn_configs = [
            ("min", icons_dir / "min.svg", self.showMinimized),
            ("max", icons_dir / "max.svg",
             lambda: self.showMaximized() if not self.isMaximized() else self.showNormal()),
            ("close", icons_dir / "close.svg", self.close),
        ]
        for action, icon_path, handler in btn_configs:
            btn = QPushButton()
            btn.setFixedSize(36, 28)
            btn.setCursor(Qt.PointingHandCursor)
            if icon_path.exists():
                btn.setIcon(QIcon(str(icon_path)))
                btn.setIconSize(QSize(12, 12))
            else:
                btn.setText({"min": "_", "max": "□", "close": "×"}[action])
            btn.setFlat(True)
            if action == "close":
                btn.setStyleSheet("""
                    QPushButton { background: transparent; border: none; }
                    QPushButton:hover { background: #E81123; border-radius: 4px; color: white; }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton { background: transparent; border: none; }
                    QPushButton:hover { background: #E5E7EB; border-radius: 4px; }
                """)
            btn.clicked.connect(handler)
            title_layout.addWidget(btn)

        outer_layout.addWidget(title_bar)

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar (200px — wider for CJK labels)
        self._sidebar = QFrame()
        self._sidebar.setFixedWidth(200)
        self._sidebar.setStyleSheet("""
            QFrame {
                background: #F9F9F9;
                border-right: 1px solid #E5E7EB;
                border-radius: 0px;
            }
        """)
        sidebar_layout = QVBoxLayout(self._sidebar)
        sidebar_layout.setContentsMargins(16, 10, 16, 10)
        sidebar_layout.setSpacing(4)

        self._logo_lbl = QLabel(
            self._i18n.t("app.name") if self._i18n else "LocalKB"
        )
        self._logo_lbl.setStyleSheet("""
            font-size: 14px; font-weight: 700; color: #2D3436;
            padding: 6px 10px; border: none; background: transparent;
        """)
        sidebar_layout.addWidget(self._logo_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #E5E7EB; max-height: 1px; border: none;")
        sidebar_layout.addWidget(sep)
        sidebar_layout.addSpacing(6)

        self._nav_buttons = []
        for key, page_idx in NAV_ITEMS:
            text = self._i18n.t(key) if self._i18n else key
            btn = _SidebarButton(text, page_idx)
            btn.clicked.connect(lambda checked, i=page_idx: self._switch_page(i))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sidebar_layout.addStretch()

        # Language switcher
        if self._i18n:
            self._lang_combo = QComboBox()
            self._lang_combo.addItems(["中文", "English"])
            self._lang_combo.setCurrentText(
                "中文" if self._i18n.language == "zh" else "English"
            )
            self._lang_combo.currentTextChanged.connect(self._on_lang_combo_changed)
            self._lang_combo.setStyleSheet("""
                QComboBox {
                    background: transparent; border: 1px solid #DFE6E9;
                    border-radius: 6px; padding: 4px 8px; font-size: 11px;
                    color: #636E72;
                }
                QComboBox:hover { border: 1px solid #4A90D9; }
                QComboBox::drop-down { border: none; width: 16px; }
                QComboBox QAbstractItemView {
                    background: #FFFFFF; border: 1px solid #DFE6E9;
                    selection-background-color: #F0F4F8;
                }
            """)
            sidebar_layout.addWidget(self._lang_combo)
            sidebar_layout.addSpacing(4)

        self._ver_lbl = QLabel(
            self._i18n.t("app.version_label") if self._i18n else "v1.0  .  LocalKB"
        )
        self._ver_lbl.setStyleSheet(
            "font-size: 10px; color: #A0AEC0; padding: 6px 10px;"
            "border: none; background: transparent;"
        )
        sidebar_layout.addWidget(self._ver_lbl)

        main_layout.addWidget(self._sidebar)

        # Page stack — only chat page is created eagerly;
        # pages 1-4 are built on first navigation to speed up cold start.
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: #FFFFFF; }")

        self._pages: list[QWidget | None] = [None] * len(NAV_ITEMS)
        self.chat_page = ChatPage(
            qa_chain=qa_chain,
            config_manager=config_manager,
            i18n=i18n,
        )
        self._pages[0] = self.chat_page
        self._stack.addWidget(self.chat_page)

        # Placeholder attributes for backward-compatible access
        self.kb_page = None
        self.settings_page = None
        self.api_page = None
        self.about_page = None

        main_layout.addWidget(self._stack)

        outer_layout.addLayout(main_layout)

        # Status bar
        self._status = QStatusBar()
        self._status.setStyleSheet("""
            QStatusBar {
                background: #EBF0F7;
                color: #636E72;
                border-top: 1px solid #DFE6E9;
                font-size: 12px;
                padding: 4px 12px;
            }
        """)
        self._status.showMessage(
            self._i18n.t("status.ready") if self._i18n else "Ready"
        )

        # ── Embed model indicator (permanent, bottom-left) ──
        embed_display = _model_display_name(embed_model_name)
        embed_label_text = (
            f"  {self._i18n.t('embed_model')}: {embed_display}  "
            if self._i18n else f"  Embed: {embed_display}  "
        )
        self._embed_model_indicator = QLabel(embed_label_text)
        self._embed_model_indicator.setStyleSheet("""
            QLabel {
                color: #4A90D9;
                font-size: 11px;
                font-weight: 500;
                padding: 2px 8px;
                background: transparent;
                border: none;
            }
        """)
        self._status.addPermanentWidget(self._embed_model_indicator)

        self.setStatusBar(self._status)

        # ── Loading state ──
        # Track parallel init completion (Qdrant+QAChain and model warmup
        # run concurrently in background threads).
        self._startup_done = (self.qa_chain is not None)
        self._warmup_done = (not self._embed_model_name)  # no model → trivially done

        if self.qa_chain is not None:
            # QA chain already initialized (legacy synchronous path) — start warmup
            if self._embed_model_name:
                self._start_model_warmup()
        else:
            # QA chain will be set later via StartupWorker — show both progress bars.
            # WarmupWorker is started in parallel by main.py.
            self.chat_page.set_qdrant_progress_visible(True)
            self.chat_page.set_warmup_progress_visible(True)
            self.chat_page.set_input_enabled(False)

        self._nav_buttons[0].setChecked(True)

    def _switch_page(self, index):
        # Lazy-create page on first navigation
        if self._pages[index] is None:
            self._create_page(index)
        self._stack.setCurrentIndex(index)
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    def _create_page(self, index: int):
        """Create a page on first navigation (lazy init)."""
        if index == 1:
            from pages.kb_manage_page import KBManagePage
            page = KBManagePage(
                vector_store=self.vector_store,
                config_manager=self.config_manager,
                i18n=self._i18n,
            )
            self.kb_page = page
        elif index == 2:
            from pages.settings_page import SettingsPage
            page = SettingsPage(
                config_manager=self.config_manager,
                i18n=self._i18n,
            )
            self.settings_page = page
        elif index == 3:
            from pages.api_config_page import APIConfigPage
            page = APIConfigPage(
                config_manager=self.config_manager,
                i18n=self._i18n,
            )
            self.api_page = page
        elif index == 4:
            from pages.about_page import AboutPage
            page = AboutPage(i18n=self._i18n)
            self.about_page = page
        else:
            return  # page 0 (chat) is already created

        self._pages[index] = page
        self._stack.addWidget(page)

    def set_status(self, text):
        self._status.showMessage(text)

    # ── Parallel startup coordination ──
    # StartupWorker (Qdrant + QAChain) and WarmupWorker (embedding model)
    # run concurrently.  Input is enabled only when BOTH complete.

    def _on_startup_ready(self, qa_chain, vector_store):
        """Called by StartupWorker when Qdrant + QAChain init completes."""
        self.qa_chain = qa_chain
        self.vector_store = vector_store

        # Hide Qdrant progress bar
        self.chat_page.set_qdrant_progress_visible(False)

        # Update lazy-created pages that reference vector_store
        for page in self._pages:
            if page is not None and hasattr(page, 'vector_store'):
                page.vector_store = vector_store
            if page is not None and hasattr(page, 'qa_chain'):
                page.qa_chain = qa_chain

        self.chat_page.set_qa_chain(qa_chain)

        if qa_chain is not None:
            config = self.config_manager.load() if self.config_manager else {}
            self.set_status(
                self._i18n.t("status.ready_with_model",
                             model=config.get("model", "unknown"),
                             api_base=config.get("api_base", ""))
                if self._i18n else "Ready"
            )
        else:
            self.set_status(
                self._i18n.t("status.not_configured")
                if self._i18n else "Not configured"
            )

        self._startup_done = True
        self._check_both_ready()

    def _on_warmup_ready(self):
        """Called by WarmupWorker when the embedding model finishes loading."""
        self.chat_page.set_warmup_progress_visible(False)
        self._warmup_done = True
        self._check_both_ready()

    def _on_warmup_error(self, err: str):
        """Called by WarmupWorker when model loading fails."""
        self.chat_page.set_warmup_progress_visible(False)
        self._warmup_done = True
        if self._i18n:
            self.set_status(self._i18n.t("status.init_error", error=err))
        else:
            self.set_status(f"Model load failed: {err}")
        self._check_both_ready()

    def _check_both_ready(self):
        """Enable chat input when both StartupWorker and WarmupWorker finish."""
        if not (self._startup_done and self._warmup_done):
            return

        if self.qa_chain is not None:
            self.chat_page.set_input_enabled(True)
        # If qa_chain is None, input stays disabled, status already set

    def _on_startup_error(self, phase: str, detail: str):
        """Slot called by StartupWorker when an unrecoverable error occurs.

        Args:
            phase: "vector_db" (Qdrant locked/failed) or "qa_chain" (LLM init failed).
            detail: Human-readable error message.
        """
        if phase == "vector_db":
            # Qdrant locked or failed — show critical dialog, quit
            from PySide6.QtWidgets import QMessageBox
            from core.paths import VECTOR_DB_DIR
            self.chat_page.set_qdrant_progress_visible(False)
            self.chat_page.set_warmup_progress_visible(False)
            msg = detail
            if "already accessed" in msg or "AlreadyLocked" in msg or "Permission denied" in msg:
                QMessageBox.critical(
                    self,
                    self._i18n.t("status.vector_db_locked_title"),
                    self._i18n.t("status.vector_db_locked_msg",
                                 path=str(VECTOR_DB_DIR)),
                )
            else:
                QMessageBox.critical(
                    self,
                    self._i18n.t("status.init_error_title"),
                    self._i18n.t("status.init_error", error=detail),
                )
            from PySide6.QtWidgets import QApplication
            QApplication.quit()
        else:
            # QA chain failed — keep window open, show status error
            self.chat_page.set_qdrant_progress_visible(False)
            self.chat_page.set_warmup_progress_visible(False)
            self.set_status(
                self._i18n.t("status.init_failed", error=detail)
                if self._i18n else f"Init failed: {detail}"
            )

    def _start_model_warmup(self):
        """Disable input, show progress banner, start background warmup."""
        self.chat_page.set_input_enabled(False)
        self.chat_page.set_warmup_progress_visible(True)

        self._warmup_worker = WarmupWorker(self._embed_model_name)
        self._warmup_worker.ready.connect(self._on_model_ready)
        self._warmup_worker.error.connect(self._on_model_error)
        self._warmup_worker.start()

    def _on_model_ready(self):
        """Model loaded — hide banner, enable input."""
        self.chat_page.set_warmup_progress_visible(False)
        self.chat_page.set_input_enabled(True)

    def _on_model_error(self, err: str):
        """Model warmup failed — hide banner, keep input disabled, show hint."""
        self.chat_page.set_warmup_progress_visible(False)
        self.chat_page.set_input_enabled(False)
        if self._i18n:
            self._status.showMessage(
                self._i18n.t("status.init_error", error=err)
            )
        else:
            self._status.showMessage(f"Model load failed: {err}")

    # ── i18n ──
    def _on_lang_combo_changed(self, text: str):
        lang = "zh" if text == "中文" else "en"
        self._i18n.set_language(lang)
        # Save language preference
        if self.config_manager:
            config = self.config_manager.load()
            config["language"] = lang
            self.config_manager.save(config)

    def _on_language_changed(self, lang: str):
        self._retranslate_ui()
        self._retranslate_pages()

    def _retranslate_ui(self):
        if not self._i18n:
            return
        self.setWindowTitle(self._i18n.t("app.name"))
        self._title_lbl.setText(f"  {self._i18n.t('app.name')}  ")
        self._logo_lbl.setText(self._i18n.t("app.name"))
        self._ver_lbl.setText(self._i18n.t("app.version_label"))
        # Update nav buttons
        for btn, (key, _) in zip(self._nav_buttons, NAV_ITEMS):
            btn.setText(self._i18n.t(key))
        # Update embed model indicator
        display = _model_display_name(getattr(self, '_embed_model_name', ''))
        self._embed_model_indicator.setText(
            f"  {self._i18n.t('embed_model')}: {display}  "
        )

    def _retranslate_pages(self):
        for page in self._pages:
            if page is not None and hasattr(page, "retranslate"):
                page.retranslate()

    def _title_press(self, event: QMouseEvent):
        self._drag_pos = event.globalPosition().toPoint()

    def _title_move(self, event: QMouseEvent):
        if self._drag_pos is not None:
            delta = event.globalPosition().toPoint() - self._drag_pos
            self.move(self.pos() + delta)
            self._drag_pos = event.globalPosition().toPoint()

    def _title_release(self, event: QMouseEvent):
        self._drag_pos = None
