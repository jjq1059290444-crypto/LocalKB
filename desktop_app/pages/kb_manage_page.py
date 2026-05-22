"""kb_manage_page.py — knowledge base management: upload .md/.txt files."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QFrame, QMessageBox, QProgressBar,
    QGroupBox,
)
from PySide6.QtCore import Qt

from core.paths import VECTOR_DB_DIR
from core.retrieval.vector_store import VectorStore
from workers.index_worker import IndexWorker
from config.manager import ConfigManager
from config.presets import EMBED_MODELS, get_embed_model_path


class KBManagePage(QWidget):
    """Knowledge base management page."""

    def __init__(self, vector_store: VectorStore, config_manager: ConfigManager,
                 i18n, parent=None):
        super().__init__(parent)
        self._store = vector_store
        self._config_mgr = config_manager
        self._i18n = i18n
        self._worker = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet("font-size: 22px; font-weight: 700; color: #2D3436;")
        layout.addWidget(self._title_lbl)

        self._desc_lbl = QLabel()
        self._desc_lbl.setStyleSheet("font-size: 13px; color: #636E72;")
        self._desc_lbl.setWordWrap(True)
        layout.addWidget(self._desc_lbl)

        # ── Upload area ──
        self._upload_group = QGroupBox()
        upload_layout = QVBoxLayout(self._upload_group)
        upload_layout.setSpacing(12)

        self._upload_area = QFrame()
        self._upload_area.setAcceptDrops(True)
        self._upload_area.setStyleSheet("""
            QFrame {
                background: #F8FAFB;
                border: 2px dashed #C8D6E5;
                border-radius: 12px;
            }
            QFrame:hover {
                border-color: #4A90D9;
                background: #EEF3FA;
            }
        """)
        self._upload_area.setMinimumHeight(100)
        self._upload_area.setCursor(Qt.PointingHandCursor)

        def _on_upload_click(event):
            self._on_pick_files()
        self._upload_area.mousePressEvent = _on_upload_click

        self._upload_area.dragEnterEvent = self._upload_drag_enter
        self._upload_area.dropEvent = self._upload_drop

        area_layout = QVBoxLayout(self._upload_area)
        area_layout.setAlignment(Qt.AlignCenter)

        self._pick_lbl = QLabel()
        self._pick_lbl.setStyleSheet(
            "font-size: 14px; color: #636E72; border: none; background: transparent;"
        )
        self._pick_lbl.setAlignment(Qt.AlignCenter)
        area_layout.addWidget(self._pick_lbl)

        self._sub_lbl = QLabel()
        self._sub_lbl.setStyleSheet(
            "font-size: 11px; color: #A0AEC0; border: none; background: transparent;"
        )
        self._sub_lbl.setAlignment(Qt.AlignCenter)
        area_layout.addWidget(self._sub_lbl)

        upload_layout.addWidget(self._upload_area)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                background: #E8ECF0; border: none;
                border-radius: 6px; height: 8px; text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4A90D9, stop:1 #6DB9E8);
                border-radius: 6px;
            }
        """)
        upload_layout.addWidget(self._progress)

        self._stage_lbl = QLabel("")
        self._stage_lbl.setStyleSheet("font-size: 12px; color: #636E72;")
        self._stage_lbl.setVisible(False)
        upload_layout.addWidget(self._stage_lbl)

        layout.addWidget(self._upload_group)

        # ── Indexed files list ──
        self._indexed_group = QGroupBox()
        files_layout = QVBoxLayout(self._indexed_group)
        files_layout.setSpacing(10)

        self._stats_lbl = QLabel()
        self._stats_lbl.setStyleSheet("font-size: 12px; color: #636E72;")
        files_layout.addWidget(self._stats_lbl)

        self._file_list = QListWidget()
        self._file_list.setMaximumHeight(200)
        files_layout.addWidget(self._file_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._refresh_btn = QPushButton()
        self._refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(self._refresh_btn)

        self._reset_btn = QPushButton()
        self._reset_btn.setStyleSheet("""
            QPushButton {
                background: #FFF0F0; color: #C62828;
                border: 1px solid #FFCDD2; border-radius: 8px;
                padding: 8px 18px; font-weight: 600;
            }
            QPushButton:hover { background: #FFCDD2; }
        """)
        self._reset_btn.clicked.connect(self._on_reset)
        btn_row.addWidget(self._reset_btn)

        btn_row.addStretch()
        files_layout.addLayout(btn_row)

        layout.addWidget(self._indexed_group)
        layout.addStretch()

        self.retranslate()
        self._refresh()

    def retranslate(self):
        self._title_lbl.setText(self._i18n.t("kb.title"))
        self._desc_lbl.setText(self._i18n.t("kb.desc"))
        self._upload_group.setTitle(self._i18n.t("kb.upload_group"))
        self._pick_lbl.setText(self._i18n.t("kb.upload_hint"))
        self._sub_lbl.setText(self._i18n.t("kb.upload_sub"))
        self._indexed_group.setTitle(self._i18n.t("kb.indexed_group"))
        self._refresh_btn.setText(self._i18n.t("kb.refresh_btn"))
        self._reset_btn.setText(self._i18n.t("kb.clear_btn"))
        self._refresh()

    def _on_pick_files(self, event=None):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            self._i18n.t("kb.file_dialog_title"),
            "",
            self._i18n.t("kb.file_filter"),
        )
        if paths:
            self._process_files(paths)

    def _process_files(self, paths: list):
        if self._worker and self._worker.isRunning():
            return

        self._progress.setVisible(True)
        self._progress.setMaximum(0)
        self._stage_lbl.setVisible(True)

        config = self._config_mgr.load()
        embed_model = config.get("embed_model", "bge-small-zh-v1.5")
        embed_info = EMBED_MODELS.get(embed_model, EMBED_MODELS["bge-small-zh-v1.5"])
        model_name = get_embed_model_path(embed_model)
        use_sparse = embed_info.get("sparse", False)

        self._worker = IndexWorker(
            paths, self._store,
            embed_model_name=model_name,
            chunking_strategy=config.get("chunking_strategy", "structural"),
            matryoshka_dim=config.get("matryoshka_dim", 0),
            use_sparse=use_sparse,
        )
        self._worker.progress_signal.connect(self._on_progress)
        self._worker.finished_signal.connect(self._on_done)
        self._worker.error_signal.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, stage: int, key: str, args: dict):
        msg = self._i18n.t(key, **args)
        self._stage_lbl.setText(msg)
        if stage == 4:
            self._progress.setMaximum(1)

    def _on_done(self, result: dict):
        self._progress.setMaximum(1)
        self._progress.setVisible(False)
        self._stage_lbl.setVisible(False)

        added = result.get("added", 0)
        skipped = result.get("skipped", 0)
        errors = result.get("errors", [])

        msg = self._i18n.t("kb.added_chunks", added=added)
        if skipped:
            msg += self._i18n.t("kb.skipped_files", skipped=skipped)
        if errors:
            msg += self._i18n.t("kb.errors_prefix", errors="; ".join(errors[:3]))

        QMessageBox.information(self, self._i18n.t("kb.complete_title"), msg)
        self._refresh()

    def _on_error(self, key: str, args: dict):
        self._progress.setVisible(False)
        self._stage_lbl.setVisible(False)
        msg = self._i18n.t(key, **args)
        QMessageBox.critical(self, self._i18n.t("kb.error_title"), msg)

    def _on_reset(self):
        reply = QMessageBox.question(
            self,
            self._i18n.t("kb.confirm_title"),
            self._i18n.t("kb.confirm_clear"),
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._store.reset()
            self._refresh()
            QMessageBox.information(
                self,
                self._i18n.t("kb.done_title"),
                self._i18n.t("kb.cleared_msg"),
            )

    def _refresh(self):
        self._file_list.clear()
        try:
            count = self._store.count()
            sources = self._store.get_source_files()
        except Exception:
            count = 0
            sources = {}
        self._stats_lbl.setText(self._i18n.t("kb.total_chunks", count=count))
        for filename, chunk_count in sorted(sources.items()):
            self._file_list.addItem(
                f"{filename}  —  {chunk_count} chunks"
            )

    def _upload_drag_enter(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _upload_drop(self, event):
        paths = []
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p.endswith((".md", ".txt", ".pdf", ".docx", ".pptx", ".ppt")):
                paths.append(p)
        if paths:
            self._process_files(paths)
