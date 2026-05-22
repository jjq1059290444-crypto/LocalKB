"""api_config_page.py — LLM API configuration with provider presets."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QGroupBox, QMessageBox, QComboBox,
)
from PySide6.QtCore import Qt

from config.manager import ConfigManager
from config.presets import PROVIDER_PRESETS
from workers.config_worker import ConfigWorker


class APIConfigPage(QWidget):
    """API configuration: provider, key, base URL, model, test connection."""

    def __init__(self, config_manager: ConfigManager, i18n, parent=None):
        super().__init__(parent)
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

        # ── API config group ──
        self._api_group = QGroupBox()
        api_layout = QVBoxLayout(self._api_group)
        api_layout.setSpacing(14)

        # Provider dropdown
        prov_row = QHBoxLayout()
        self._prov_lbl = QLabel()
        self._prov_lbl.setStyleSheet("font-size: 13px; color: #636E72; min-width: 100px;")
        prov_row.addWidget(self._prov_lbl)

        self._provider_combo = QComboBox()
        for name in PROVIDER_PRESETS:
            self._provider_combo.addItem(name)
        self._provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self._provider_combo.setStyleSheet("""
            QComboBox {
                background: #FFFFFF; border: 1px solid #DFE6E9;
                border-radius: 8px; padding: 8px 12px; font-size: 13px;
            }
        """)
        prov_row.addWidget(self._provider_combo, 1)
        api_layout.addLayout(prov_row)

        # API Key
        key_row = QHBoxLayout()
        self._key_lbl = QLabel()
        self._key_lbl.setStyleSheet("font-size: 13px; color: #636E72; min-width: 100px;")
        key_row.addWidget(self._key_lbl)

        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.Password)
        input_style = """
            QLineEdit {
                background: #FFFFFF; border: 1px solid #DFE6E9;
                border-radius: 8px; padding: 8px 12px; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #4A90D9; }
        """
        self._key_input.setStyleSheet(input_style)
        key_row.addWidget(self._key_input, 1)

        show_btn = QPushButton("\U0001F441")
        show_btn.setFixedWidth(36)
        show_btn.setCheckable(True)
        show_btn.toggled.connect(
            lambda v: self._key_input.setEchoMode(
                QLineEdit.Normal if v else QLineEdit.Password
            )
        )
        key_row.addWidget(show_btn)
        api_layout.addLayout(key_row)

        # Base URL
        url_row = QHBoxLayout()
        self._url_lbl = QLabel()
        self._url_lbl.setStyleSheet("font-size: 13px; color: #636E72; min-width: 100px;")
        url_row.addWidget(self._url_lbl)

        self._url_input = QLineEdit()
        self._url_input.setStyleSheet(input_style)
        url_row.addWidget(self._url_input, 1)
        api_layout.addLayout(url_row)

        # Model
        model_row = QHBoxLayout()
        self._model_lbl = QLabel()
        self._model_lbl.setStyleSheet("font-size: 13px; color: #636E72; min-width: 100px;")
        model_row.addWidget(self._model_lbl)

        self._model_input = QLineEdit()
        self._model_input.setStyleSheet(input_style)
        model_row.addWidget(self._model_input, 1)
        api_layout.addLayout(model_row)

        layout.addWidget(self._api_group)

        # ── Buttons ──
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self._test_btn = QPushButton()
        self._test_btn.setStyleSheet("""
            QPushButton {
                background: #F0F4F8; color: #4A90D9;
                border: 1px solid #DCE8F5; border-radius: 8px;
                padding: 10px 24px; font-weight: 600;
            }
            QPushButton:hover { background: #DCE8F5; }
            QPushButton:disabled { background: #F0F0F0; color: #B2BEC3; }
        """)
        self._test_btn.clicked.connect(self._on_test)
        btn_row.addWidget(self._test_btn)

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

        layout.addLayout(btn_row)
        layout.addStretch()

        self._load_current()
        self.retranslate()

    def retranslate(self):
        self._title_lbl.setText(self._i18n.t("api.title"))
        self._desc_lbl.setText(self._i18n.t("api.desc"))
        self._api_group.setTitle(self._i18n.t("api.connection_group"))
        self._prov_lbl.setText(self._i18n.t("api.provider_label"))
        self._key_lbl.setText(self._i18n.t("api.key_label"))
        self._key_input.setPlaceholderText(self._i18n.t("api.key_placeholder"))
        self._url_lbl.setText(self._i18n.t("api.url_label"))
        self._url_input.setPlaceholderText(self._i18n.t("api.url_placeholder"))
        self._model_lbl.setText(self._i18n.t("api.model_label"))
        self._model_input.setPlaceholderText(self._i18n.t("api.model_placeholder"))
        self._test_btn.setText(self._i18n.t("api.test_btn"))
        self._save_btn.setText(self._i18n.t("api.save_btn"))

    def _on_provider_changed(self, name: str):
        preset = PROVIDER_PRESETS.get(name, {})
        if preset.get("api_base"):
            self._url_input.setText(preset["api_base"])
        if preset.get("model"):
            self._model_input.setText(preset["model"])

    def _load_current(self):
        config = self._config_mgr.load()
        if config.get("api_key"):
            self._key_input.setText(config["api_key"])
        self._url_input.setText(config.get("api_base", ""))
        self._model_input.setText(config.get("model", ""))

        api_base = config.get("api_base", "")
        for name, preset in PROVIDER_PRESETS.items():
            if preset.get("api_base") == api_base:
                self._provider_combo.setCurrentText(name)
                break

    def _on_save(self):
        key = self._key_input.text().strip()
        url = self._url_input.text().strip()
        model = self._model_input.text().strip()

        if not key:
            QMessageBox.warning(
                self,
                self._i18n.t("api.missing_key_title"),
                self._i18n.t("api.missing_key_msg"),
            )
            return

        config = self._config_mgr.load()
        config["api_key"] = key
        config["api_base"] = url
        config["model"] = model
        config["setup_complete"] = True
        self._config_mgr.save(config)

        QMessageBox.information(
            self,
            self._i18n.t("api.saved_title"),
            self._i18n.t("api.saved_msg"),
        )

    def _on_test(self):
        if self._worker and self._worker.isRunning():
            return

        api_key = self._key_input.text().strip()
        base_url = self._url_input.text().strip()
        model = self._model_input.text().strip()

        if not api_key:
            QMessageBox.warning(
                self,
                self._i18n.t("api.missing_key_title"),
                self._i18n.t("api.no_key_first"),
            )
            return

        self._test_btn.setEnabled(False)
        self._test_btn.setText(self._i18n.t("api.testing"))

        self._worker = ConfigWorker(
            api_base=base_url, api_key=api_key, model=model,
        )
        self._worker.ping_signal.connect(self._on_ping_result)
        self._worker.start()

    def _on_ping_result(self, success: bool, key: str, args: dict):
        self._test_btn.setEnabled(True)
        self._test_btn.setText(self._i18n.t("api.test_btn"))
        detail = self._i18n.t(key, **args)
        if success:
            QMessageBox.information(
                self, self._i18n.t("api.connection_success"), detail
            )
        else:
            QMessageBox.critical(
                self, self._i18n.t("api.connection_failed"), detail
            )
