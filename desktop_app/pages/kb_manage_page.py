"""kb_manage_page.py — knowledge base management: upload .md/.txt files."""

import shutil
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QFrame, QMessageBox, QProgressBar,
    QGroupBox,
)
from PySide6.QtCore import Qt

from core.paths import VECTOR_DB_DIR, DOCS_DIR
from core.retrieval.vector_store import VectorStore
from workers.index_worker import IndexWorker
from workers.qdrant_import_worker import QdrantImportWorker
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
        self._import_worker = None

        DOCS_DIR.mkdir(parents=True, exist_ok=True)

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

        # ── Saved files list ──
        self._saved_group = QGroupBox()
        saved_layout = QVBoxLayout(self._saved_group)
        saved_layout.setSpacing(10)

        self._saved_stats = QLabel()
        self._saved_stats.setStyleSheet("font-size: 12px; color: #636E72;")
        saved_layout.addWidget(self._saved_stats)

        self._saved_list = QListWidget()
        self._saved_list.setMaximumHeight(120)
        saved_layout.addWidget(self._saved_list)

        layout.addWidget(self._saved_group)

        # ── Indexed files list ──
        self._indexed_group = QGroupBox()
        files_layout = QVBoxLayout(self._indexed_group)
        files_layout.setSpacing(10)

        self._stats_lbl = QLabel()
        self._stats_lbl.setStyleSheet("font-size: 12px; color: #636E72;")
        files_layout.addWidget(self._stats_lbl)

        self._file_list = QListWidget()
        self._file_list.setMaximumHeight(120)
        files_layout.addWidget(self._file_list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._refresh_btn = QPushButton()
        self._refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(self._refresh_btn)

        self._scan_btn = QPushButton()
        self._scan_btn.setStyleSheet("""
            QPushButton {
                background: #E8F4FD; color: #1565C0;
                border: 1px solid #BBDEFB; border-radius: 8px;
                padding: 8px 18px; font-weight: 600;
            }
            QPushButton:hover { background: #BBDEFB; }
        """)
        self._scan_btn.clicked.connect(self._on_scan)
        btn_row.addWidget(self._scan_btn)

        self._reindex_btn = QPushButton()
        self._reindex_btn.setStyleSheet("""
            QPushButton {
                background: #E8F4FD; color: #1565C0;
                border: 1px solid #BBDEFB; border-radius: 8px;
                padding: 8px 18px; font-weight: 600;
            }
            QPushButton:hover { background: #BBDEFB; }
        """)
        self._reindex_btn.clicked.connect(self._on_reindex)
        btn_row.addWidget(self._reindex_btn)

        self._import_btn = QPushButton()
        self._import_btn.setStyleSheet("""
            QPushButton {
                background: #F5F0FF; color: #6A1B9A;
                border: 1px solid #D1C4E9; border-radius: 8px;
                padding: 8px 18px; font-weight: 600;
            }
            QPushButton:hover { background: #D1C4E9; }
        """)
        self._import_btn.clicked.connect(self._on_import_qdrant)
        btn_row.addWidget(self._import_btn)

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
        self._saved_group.setTitle(self._i18n.t("kb.saved_group"))
        self._indexed_group.setTitle(self._i18n.t("kb.indexed_group"))
        self._refresh_btn.setText(self._i18n.t("kb.refresh_btn"))
        self._reindex_btn.setText(self._i18n.t("kb.reindex_btn"))
        self._scan_btn.setText(self._i18n.t("kb.scan_btn"))
        self._reset_btn.setText(self._i18n.t("kb.clear_btn"))
        self._import_btn.setText(self._i18n.t("kb.import_btn"))
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

        # Copy uploaded files to docs/ so they survive index resets
        saved = []
        for p in paths:
            src = Path(p)
            dst = DOCS_DIR / src.name
            # If a file with same name exists, overwrite (user re-uploaded updated version)
            shutil.copy2(src, dst)
            saved.append(str(dst))

        self._progress.setVisible(True)
        self._progress.setMaximum(0)
        self._stage_lbl.setVisible(True)

        config = self._config_mgr.load()
        embed_model = config.get("embed_model", "bge-small-zh-v1.5")
        embed_info = EMBED_MODELS.get(embed_model, EMBED_MODELS["bge-small-zh-v1.5"])
        model_name = get_embed_model_path(embed_model)
        use_sparse = embed_info.get("sparse", False)

        self._worker = IndexWorker(
            saved, self._store,
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

    def _on_import_done(self, result: dict):
        self._progress.setMaximum(1)
        self._progress.setVisible(False)
        self._stage_lbl.setVisible(False)

        imported = result.get("imported", 0)
        QMessageBox.information(
            self,
            self._i18n.t("kb.import_complete_title"),
            self._i18n.t("kb.imported_count", count=imported),
        )
        self._refresh()

    def _on_scan(self):
        """Incremental scan: index only new files from data/docs/."""
        if self._worker and self._worker.isRunning():
            return

        saved = {f.name: f for f in DOCS_DIR.iterdir() if f.is_file()}
        if not saved:
            QMessageBox.information(
                self,
                self._i18n.t("kb.no_saved_title"),
                self._i18n.t("kb.no_saved_msg"),
            )
            return

        # Find files not yet indexed
        try:
            indexed = set(self._store.get_source_files().keys())
        except Exception:
            indexed = set()

        new_files = [str(saved[name]) for name in sorted(saved) if name not in indexed]
        if not new_files:
            QMessageBox.information(
                self,
                self._i18n.t("kb.scan_title"),
                self._i18n.t("kb.scan_up_to_date"),
            )
            return

        self._process_files(new_files)

    def _on_import_qdrant(self):
        """Import all points from a pre-built Qdrant database."""
        if self._import_worker and self._import_worker.isRunning():
            return

        source_dir = QFileDialog.getExistingDirectory(
            self,
            self._i18n.t("kb.import_dialog_title"),
            "",
        )
        if not source_dir:
            return

        # Read meta.json to find collection name
        import json
        meta_path = Path(source_dir) / "meta.json"
        if not meta_path.exists():
            QMessageBox.critical(
                self,
                self._i18n.t("kb.error_title"),
                self._i18n.t("kb.import_no_meta"),
            )
            return

        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            collections = list(meta.get("collections", {}).keys())
            if not collections:
                raise ValueError("No collections found")
        except Exception:
            QMessageBox.critical(
                self,
                self._i18n.t("kb.error_title"),
                self._i18n.t("kb.import_invalid_meta"),
            )
            return

        source_collection = collections[0]

        self._progress.setVisible(True)
        self._progress.setMaximum(0)
        self._stage_lbl.setVisible(True)
        self._stage_lbl.setText(self._i18n.t("kb.import_reading", path=source_dir))

        self._import_worker = QdrantImportWorker(
            self._store, source_dir, source_collection
        )
        self._import_worker.progress_signal.connect(self._on_progress)
        self._import_worker.finished_signal.connect(self._on_import_done)
        self._import_worker.error_signal.connect(self._on_error)
        self._import_worker.start()

    def _on_reindex(self):
        """Full re-index: reset then rebuild all saved files (for model switch)."""
        if self._worker and self._worker.isRunning():
            return

        saved = list(DOCS_DIR.glob("*"))
        if not saved:
            QMessageBox.information(
                self,
                self._i18n.t("kb.no_saved_title"),
                self._i18n.t("kb.no_saved_msg"),
            )
            return

        # Reset first, then re-index
        self._store.reset()
        self._process_files([str(f) for f in saved])

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
        self._saved_list.clear()

        # Show saved files (data/docs/)
        try:
            saved_files = sorted(
                f for f in DOCS_DIR.iterdir() if f.is_file()
            )
        except Exception:
            saved_files = []

        self._saved_stats.setText(
            self._i18n.t("kb.saved_count", count=len(saved_files))
        )
        for f in saved_files:
            size_kb = f.stat().st_size / 1024
            self._saved_list.addItem(
                f"{f.name}  —  {size_kb:.1f} KB"
            )

        # Show indexed chunks (from vector store)
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
