"""settings_page.py — retrieval parameters + system prompt + embed model."""

import subprocess
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QTextEdit,
    QPushButton, QGroupBox, QSpinBox, QMessageBox, QSizePolicy, QComboBox,
    QCheckBox, QApplication,
)
from PySide6.QtCore import Qt

from config.manager import ConfigManager
from config.presets import EMBED_MODELS
from utils.model_download import download_model_if_needed

CHUNK_STRATEGIES = {
    "structural": "H2 Structural",
    "semantic": "Semantic (similarity)",
    "late": "Late Chunking (BGE-M3)",
}


class SettingsPage(QWidget):
    """Settings: top_k, temperature, system prompt, embed model."""

    def __init__(self, config_manager: ConfigManager, i18n, parent=None):
        super().__init__(parent)
        self._config_mgr = config_manager
        self._i18n = i18n

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(20)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet("font-size: 22px; font-weight: 700; color: #2D3436;")
        layout.addWidget(self._title_lbl)

        # ── Retrieval settings ──
        self._ret_group = QGroupBox()
        ret_layout = QHBoxLayout(self._ret_group)
        ret_layout.setSpacing(24)

        # ── Common styles ──
        _LBL = "font-size: 13px; color: #636E72; min-width: 100px;"
        _CMB = """
            QComboBox {
                background: #FFFFFF; border: 1px solid #DFE6E9;
                border-radius: 8px; padding: 6px 10px; font-size: 13px;
                min-width: 240px;
            }
        """
        _SPN = """
            QSpinBox {
                background: #FFFFFF; border: 1px solid #DFE6E9;
                border-radius: 8px; padding: 6px 10px; font-size: 14px;
                min-width: 100px;
            }
        """

        def _row(lbl, widget, stretch=True):
            row = QHBoxLayout()
            row.setSpacing(8)
            l = QLabel()
            l.setStyleSheet(_LBL)
            row.addWidget(l)
            row.addWidget(widget, 1)
            if stretch:
                row.addStretch()
            return row, l

        # ── Left column ──
        left = QVBoxLayout()
        left.setSpacing(12)

        self._topk_spin = QSpinBox()
        self._topk_spin.setRange(1, 20)
        self._topk_spin.setValue(10)
        self._topk_spin.setStyleSheet(_SPN)
        r, self._topk_lbl = _row("", self._topk_spin)
        left.addLayout(r)

        self._embed_combo = QComboBox()
        for key in EMBED_MODELS:
            self._embed_combo.addItem(key, key)
        self._embed_combo.setStyleSheet(_CMB)
        self._embed_combo.currentIndexChanged.connect(self._on_embed_changed)
        r, self._embed_lbl = _row("", self._embed_combo)
        left.addLayout(r)
        self._refresh_embed_combo_labels()

        self._matryoshka_combo = QComboBox()
        self._matryoshka_combo.addItem("Full (no truncation)", 0)
        self._matryoshka_combo.setStyleSheet(_CMB)
        r, self._matryoshka_lbl = _row("", self._matryoshka_combo)
        left.addLayout(r)

        self._chunk_combo = QComboBox()
        for key, label in CHUNK_STRATEGIES.items():
            self._chunk_combo.addItem(label, key)
        self._chunk_combo.setStyleSheet(_CMB)
        r, self._chunk_lbl = _row("", self._chunk_combo)
        left.addLayout(r)

        left.addStretch()
        ret_layout.addLayout(left)

        # ── Right column ──
        right = QVBoxLayout()
        right.setSpacing(12)

        temp_row = QHBoxLayout()
        temp_row.setSpacing(8)
        self._temp_lbl = QLabel()
        self._temp_lbl.setStyleSheet(_LBL)
        temp_row.addWidget(self._temp_lbl)
        self._temp_slider = QSlider(Qt.Horizontal)
        self._temp_slider.setRange(0, 20)
        self._temp_slider.setValue(3)
        self._temp_slider.setTickPosition(QSlider.TicksBelow)
        self._temp_slider.setTickInterval(2)
        temp_row.addWidget(self._temp_slider, 1)
        self._temp_val = QLabel("0.3")
        self._temp_val.setStyleSheet(
            "font-size: 14px; font-weight: 600; color: #4A90D9; min-width: 36px;"
        )
        self._temp_val.setAlignment(Qt.AlignCenter)
        self._temp_slider.valueChanged.connect(
            lambda v: self._temp_val.setText(f"{v / 10:.1f}")
        )
        temp_row.addWidget(self._temp_val)
        right.addLayout(temp_row)

        self._rerank_check = QCheckBox()
        self._rerank_check.setStyleSheet("font-size: 13px; color: #636E72;")
        r, self._rerank_lbl = _row("", self._rerank_check)
        right.addLayout(r)

        self._hyde_check = QCheckBox()
        self._hyde_check.setStyleSheet("font-size: 13px; color: #636E72;")
        r, self._hyde_lbl = _row("", self._hyde_check)
        right.addLayout(r)

        self._conv_combo = QComboBox()
        self._conv_combo.addItem(self._i18n.t("settings.conversation_mode_single"), "single")
        self._conv_combo.addItem(self._i18n.t("settings.conversation_mode_multi"), "multi")
        self._conv_combo.setStyleSheet(_CMB)
        r, self._conv_lbl = _row("", self._conv_combo)
        right.addLayout(r)

        self._hist_spin = QSpinBox()
        self._hist_spin.setRange(0, 20)
        self._hist_spin.setValue(6)
        self._hist_spin.setStyleSheet(_SPN)
        r, self._hist_lbl = _row("", self._hist_spin)
        right.addLayout(r)

        right.addStretch()
        ret_layout.addLayout(right)

        layout.addWidget(self._ret_group)

        # ── System Prompt ──
        self._prompt_group = QGroupBox()
        prompt_layout = QVBoxLayout(self._prompt_group)
        prompt_layout.setSpacing(10)

        self._prompt_desc = QLabel()
        self._prompt_desc.setStyleSheet("font-size: 12px; color: #A0AEC0;")
        self._prompt_desc.setWordWrap(True)
        prompt_layout.addWidget(self._prompt_desc)

        self._prompt_edit = QTextEdit()
        self._prompt_edit.setMinimumHeight(200)
        self._prompt_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._prompt_edit.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF; color: #2D3436;
                border: 1px solid #DFE6E9; border-radius: 10px;
                padding: 12px;
                font-family: "Consolas", "Microsoft YaHei UI", monospace;
                font-size: 12px; line-height: 1.6;
            }
        """)
        prompt_layout.addWidget(self._prompt_edit)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._reset_btn = QPushButton()
        self._reset_btn.clicked.connect(self._on_reset)
        btn_row.addWidget(self._reset_btn)

        btn_row.addStretch()

        self._save_btn = QPushButton()
        self._save_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4A90D9, stop:1 #6DB9E8);
                color: white; border: none;
                border-radius: 10px; padding: 10px 28px;
                font-size: 14px; font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3A7BC8, stop:1 #5DA8D9);
            }
        """)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        prompt_layout.addLayout(btn_row)
        layout.addWidget(self._prompt_group)
        layout.addStretch()

        self._load_settings()
        self.retranslate()

    def retranslate(self):
        self._title_lbl.setText(self._i18n.t("settings.title"))
        self._ret_group.setTitle(self._i18n.t("settings.retrieval_params"))
        self._topk_lbl.setText(self._i18n.t("settings.top_k"))
        self._temp_lbl.setText(self._i18n.t("settings.temperature"))
        self._embed_lbl.setText(self._i18n.t("settings.embed_model"))
        self._matryoshka_lbl.setText(self._i18n.t("settings.matryoshka_dim"))
        self._chunk_lbl.setText(self._i18n.t("settings.chunk_strategy"))
        self._rerank_lbl.setText(self._i18n.t("settings.reranker"))
        self._rerank_check.setText(self._i18n.t("settings.reranker_desc"))
        self._hyde_lbl.setText(self._i18n.t("settings.hyde"))
        self._hyde_check.setText(self._i18n.t("settings.hyde_desc"))
        self._hist_lbl.setText(self._i18n.t("settings.max_history"))
        self._conv_lbl.setText(self._i18n.t("settings.conversation_mode"))
        self._prompt_group.setTitle(self._i18n.t("settings.system_prompt"))
        self._prompt_desc.setText(self._i18n.t("settings.prompt_desc"))
        self._reset_btn.setText(self._i18n.t("settings.restore_default"))
        self._save_btn.setText(self._i18n.t("settings.save"))

    def _load_settings(self):
        config = self._config_mgr.load()
        self._topk_spin.setValue(config.get("top_k", 10))
        self._temp_slider.setValue(int(config.get("temperature", 0.3) * 10))
        self._prompt_edit.setPlainText(config.get("system_prompt", ""))

        embed_model = config.get("embed_model", "bge-small-zh-v1.5")
        idx = self._embed_combo.findData(embed_model)
        if idx >= 0:
            self._embed_combo.setCurrentIndex(idx)

        self._rerank_check.setChecked(config.get("use_reranker", False))
        self._hyde_check.setChecked(config.get("hyde_enabled", False))
        self._hist_spin.setValue(config.get("max_history_turns", 6))

        conv_mode = config.get("conversation_mode", "single")
        cidx = self._conv_combo.findData(conv_mode)
        if cidx >= 0:
            self._conv_combo.setCurrentIndex(cidx)

        chunk_strategy = config.get("chunking_strategy", "structural")
        cidx = self._chunk_combo.findData(chunk_strategy)
        if cidx >= 0:
            self._chunk_combo.setCurrentIndex(cidx)

        matryoshka_dim = config.get("matryoshka_dim", 0)
        midx = self._matryoshka_combo.findData(matryoshka_dim)
        if midx >= 0:
            self._matryoshka_combo.setCurrentIndex(midx)

        # Refresh matryoshka options and embed labels for the current embed model
        self._refresh_matryoshka_options()
        self._refresh_embed_combo_labels()

    def _on_embed_changed(self):
        self._refresh_matryoshka_options()
        self._refresh_embed_combo_labels()

    def _refresh_matryoshka_options(self):
        """Rebuild matryoshka dropdown based on selected embed model."""
        embed_key = self._embed_combo.currentData()
        info = EMBED_MODELS.get(embed_key)

        self._matryoshka_combo.clear()
        dims = info.get("matryoshka") if info else None
        if dims:
            _matryoshka_notes = {
                1024: "1024（完整）",
                768:  "768",
                512:  "512（轻量）",
                256:  "256（最快）",
            }
            for d in dims:
                label = _matryoshka_notes.get(d, str(d))
                self._matryoshka_combo.addItem(label, d)
        else:
            self._matryoshka_combo.addItem(
                self._i18n.t("settings.matryoshka_na"), 0
            )

    def _refresh_embed_combo_labels(self):
        """Add download-status notes to each embed model combo item."""
        from core.paths import MODELS_DIR

        _notes = {
            "bge-small-zh-v1.5": self._i18n.t("settings.embed_builtin"),
            "all-MiniLM-L6-v2": self._i18n.t("settings.embed_en"),
            "bge-m3":            self._i18n.t("settings.embed_multi"),
        }

        for i in range(self._embed_combo.count()):
            key = self._embed_combo.itemData(i)
            info = EMBED_MODELS.get(key, {})
            model_name = info.get("name", "")
            local_name = model_name.replace("/", "_")
            local_dir = MODELS_DIR / local_name
            is_downloaded = local_dir.exists() and (local_dir / "config.json").exists()

            note = _notes.get(key, "")
            if is_downloaded:
                status = self._i18n.t("settings.embed_downloaded")
            else:
                status = self._i18n.t("settings.embed_need_download")

            display = f"{key}  |  {note}{status}"
            self._embed_combo.setItemText(i, display)

    def _on_reset(self):
        from config.manager import DEFAULT_CONFIG
        self._prompt_edit.setPlainText(DEFAULT_CONFIG["system_prompt"])
        self._topk_spin.setValue(DEFAULT_CONFIG["top_k"])
        self._temp_slider.setValue(int(DEFAULT_CONFIG["temperature"] * 10))
        self._rerank_check.setChecked(DEFAULT_CONFIG.get("use_reranker", False))
        self._hyde_check.setChecked(DEFAULT_CONFIG.get("hyde_enabled", False))
        self._hist_spin.setValue(DEFAULT_CONFIG.get("max_history_turns", 6))

        cidx = self._conv_combo.findData(DEFAULT_CONFIG.get("conversation_mode", "single"))
        if cidx >= 0:
            self._conv_combo.setCurrentIndex(cidx)

        cidx = self._chunk_combo.findData(DEFAULT_CONFIG.get("chunking_strategy", "structural"))
        if cidx >= 0:
            self._chunk_combo.setCurrentIndex(cidx)

        midx = self._matryoshka_combo.findData(DEFAULT_CONFIG.get("matryoshka_dim", 0))
        if midx >= 0:
            self._matryoshka_combo.setCurrentIndex(midx)
        self._refresh_matryoshka_options()

    def _on_save(self):
        config = self._config_mgr.load()
        old_embed = config.get("embed_model", "")
        new_embed = self._embed_combo.currentData()
        embed_changed = (old_embed and old_embed != new_embed)

        config["top_k"] = self._topk_spin.value()
        config["temperature"] = self._temp_slider.value() / 10.0
        config["system_prompt"] = self._prompt_edit.toPlainText()
        config["embed_model"] = new_embed
        config["use_reranker"] = self._rerank_check.isChecked()
        config["hyde_enabled"] = self._hyde_check.isChecked()
        config["max_history_turns"] = self._hist_spin.value()
        config["conversation_mode"] = self._conv_combo.currentData()
        config["chunking_strategy"] = self._chunk_combo.currentData()
        config["matryoshka_dim"] = self._matryoshka_combo.currentData()
        self._config_mgr.save(config)

        # ── Download embed model if needed ──
        if new_embed != "text-embedding-3-small":
            info = EMBED_MODELS.get(new_embed, {})
            model_name = info.get("name", "")
            if model_name:
                ok = download_model_if_needed(model_name, self)
                if not ok:
                    return  # download failed or cancelled — config already saved

        # ── Restart prompt if embed model changed ──
        if embed_changed:
            box = QMessageBox(self)
            box.setWindowTitle(self._i18n.t("settings.restart_title"))
            box.setText(self._i18n.t(
                "settings.restart_msg",
                old=old_embed,
                new=new_embed,
            ))
            box.setIcon(QMessageBox.Question)
            restart_btn = box.addButton(self._i18n.t("settings.restart_now"), QMessageBox.AcceptRole)
            later_btn = box.addButton(self._i18n.t("settings.restart_later"), QMessageBox.RejectRole)
            box.setDefaultButton(restart_btn)
            box.exec()

            if box.clickedButton() == restart_btn:
                # Relaunch the app
                main_script = Path(__file__).resolve().parent.parent / "main.py"
                subprocess.Popen(
                    [sys.executable, str(main_script)],
                    creationflags=subprocess.CREATE_NO_WINDOW
                    if sys.platform == "win32" else 0,
                )
                QApplication.instance().quit()
            return

        QMessageBox.information(
            self,
            self._i18n.t("settings.saved_title"),
            self._i18n.t("settings.saved_msg"),
        )
