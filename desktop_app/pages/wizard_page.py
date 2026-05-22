"""wizard_page.py — first-launch 3-step setup wizard."""

from PySide6.QtWidgets import (
    QWizard, QWizardPage, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QButtonGroup, QComboBox, QMessageBox,
    QGroupBox, QProgressBar,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from config.manager import ConfigManager
from config.presets import PROVIDER_PRESETS, EMBED_MODELS
from workers.config_worker import ConfigWorker


# ── Wizard ────────────────────────────────────────────────────────

class SetupWizard(QWizard):
    """3-step first-launch wizard: Welcome → LLM Config → Embed Model."""

    wizard_finished = Signal(dict)  # emits the final config dict

    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self._config_mgr = config_manager
        self._config = config_manager.load()

        self.setWindowTitle("LocalKB Setup")
        self.setMinimumSize(640, 520)
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOptions(
            QWizard.NoBackButtonOnStartPage |
            QWizard.NoCancelButtonOnLastPage
        )

        # Pages
        self._welcome = WelcomePage(self._config)
        self._llm_page = LLMConfigPage(self._config)
        self._embed_page = EmbedModelPage(self._config)

        self.addPage(self._welcome)
        self.addPage(self._llm_page)
        self.addPage(self._embed_page)

        self.setButtonText(QWizard.NextButton, "Next >")
        self.setButtonText(QWizard.BackButton, "< Back")
        self.setButtonText(QWizard.FinishButton, "Finish")
        self.setButtonText(QWizard.CancelButton, "Cancel")

        self.finished.connect(self._on_finished)

    def _on_finished(self, result):
        if result == QWizard.Accepted:
            # Collect config from all pages
            self._config.update(self._welcome.get_config())
            self._config.update(self._llm_page.get_config())
            self._config.update(self._embed_page.get_config())
            self._config["setup_complete"] = True
            self._config_mgr.save(self._config)
            self.wizard_finished.emit(self._config)


# ── Page 1: Welcome + Language ────────────────────────────────────

class WelcomePage(QWizardPage):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self.setTitle("Welcome to LocalKB")
        self.setSubTitle(
            "Local KB is a local-first RAG knowledge base. "
            "Let's set up your environment in 3 steps."
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        desc = QLabel(
            "Your documents stay on your machine. No cloud upload. "
            "Choose your preferred language below."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("font-size: 13px; color: #636E72;")
        layout.addWidget(desc)

        layout.addSpacing(12)

        lang_group = QGroupBox("Language / 语言")
        lang_layout = QVBoxLayout(lang_group)

        self._lang_group = QButtonGroup(self)
        self._lang_zh = QRadioButton("中文 (Chinese)")
        self._lang_en = QRadioButton("English")
        self._lang_group.addButton(self._lang_zh, 0)
        self._lang_group.addButton(self._lang_en, 1)

        current_lang = self._config.get("language", "zh")
        if current_lang == "zh":
            self._lang_zh.setChecked(True)
        else:
            self._lang_en.setChecked(True)

        lang_layout.addWidget(self._lang_zh)
        lang_layout.addWidget(self._lang_en)
        layout.addWidget(lang_group)
        layout.addStretch()

    def get_config(self) -> dict:
        return {"language": "zh" if self._lang_zh.isChecked() else "en"}


# ── Page 2: LLM API Configuration ─────────────────────────────────

class LLMConfigPage(QWizardPage):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self._worker = None

        self.setTitle("LLM API Configuration")
        self.setSubTitle(
            "Supports DeepSeek, OpenAI, and any OpenAI-compatible API."
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        input_style = """
            QLineEdit {
                background: #FFFFFF; border: 1px solid #DFE6E9;
                border-radius: 8px; padding: 8px 12px; font-size: 13px;
            }
            QLineEdit:focus { border: 1px solid #4A90D9; }
        """
        lbl_style = "font-size: 13px; color: #636E72; min-width: 95px;"

        # Provider
        prov_row = QHBoxLayout()
        prov_lbl = QLabel("Provider:")
        prov_lbl.setStyleSheet(lbl_style)
        prov_row.addWidget(prov_lbl)

        self._provider_combo = QComboBox()
        for name in PROVIDER_PRESETS:
            self._provider_combo.addItem(name)
        self._provider_combo.currentTextChanged.connect(self._on_provider)
        self._provider_combo.setStyleSheet("""
            QComboBox {
                background: #FFFFFF; border: 1px solid #DFE6E9;
                border-radius: 8px; padding: 6px 10px; font-size: 13px;
            }
        """)
        prov_row.addWidget(self._provider_combo, 1)
        layout.addLayout(prov_row)

        # API Key
        key_row = QHBoxLayout()
        key_lbl = QLabel("API Key:")
        key_lbl.setStyleSheet(lbl_style)
        key_row.addWidget(key_lbl)
        self._key_input = QLineEdit()
        self._key_input.setEchoMode(QLineEdit.Password)
        self._key_input.setPlaceholderText("sk-xxxxxxxxxxxxxxxx")
        self._key_input.setStyleSheet(input_style)
        self._key_input.setText(self._config.get("api_key", ""))
        key_row.addWidget(self._key_input, 1)
        layout.addLayout(key_row)

        # Base URL
        url_row = QHBoxLayout()
        url_lbl = QLabel("Base URL:")
        url_lbl.setStyleSheet(lbl_style)
        url_row.addWidget(url_lbl)
        self._url_input = QLineEdit()
        self._url_input.setPlaceholderText("https://api.deepseek.com")
        self._url_input.setStyleSheet(input_style)
        self._url_input.setText(self._config.get("api_base", ""))
        url_row.addWidget(self._url_input, 1)
        layout.addLayout(url_row)

        # Model
        model_row = QHBoxLayout()
        model_lbl = QLabel("Model:")
        model_lbl.setStyleSheet(lbl_style)
        model_row.addWidget(model_lbl)
        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("deepseek-chat")
        self._model_input.setStyleSheet(input_style)
        self._model_input.setText(self._config.get("model", ""))
        model_row.addWidget(self._model_input, 1)
        layout.addLayout(model_row)

        # Test connection button + progress
        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setStyleSheet("""
            QPushButton {
                background: #F0F4F8; color: #4A90D9;
                border: 1px solid #DCE8F5; border-radius: 8px;
                padding: 8px 20px; font-weight: 600;
            }
            QPushButton:hover { background: #DCE8F5; }
            QPushButton:disabled { background: #F0F0F0; color: #B2BEC3; }
        """)
        self._test_btn.clicked.connect(self._on_test)
        test_row.addWidget(self._test_btn)

        self._test_status = QLabel("")
        self._test_status.setStyleSheet("font-size: 12px; color: #636E72;")
        test_row.addWidget(self._test_status)
        test_row.addStretch()
        layout.addLayout(test_row)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setStyleSheet("""
            QProgressBar {
                background: #E8ECF0; border: none;
                border-radius: 6px; height: 6px; text-align: center;
            }
            QProgressBar::chunk {
                background: #4A90D9; border-radius: 6px;
            }
        """)
        layout.addWidget(self._progress)

        layout.addStretch()

        # Initial provider fill
        self._on_provider(self._provider_combo.currentText())

    def _on_provider(self, name: str):
        preset = PROVIDER_PRESETS.get(name, {})
        if preset.get("api_base") and not self._url_input.text():
            self._url_input.setText(preset["api_base"])
        if preset.get("model") and not self._model_input.text():
            self._model_input.setText(preset["model"])

    def _on_test(self):
        if self._worker and self._worker.isRunning():
            return
        api_key = self._key_input.text().strip()
        base_url = self._url_input.text().strip()
        model = self._model_input.text().strip()

        if not api_key:
            self._test_status.setText("Please enter an API Key first.")
            self._test_status.setStyleSheet("font-size: 12px; color: #E17055;")
            return

        self._test_btn.setEnabled(False)
        self._test_status.setText("Testing...")
        self._test_status.setStyleSheet("font-size: 12px; color: #636E72;")

        self._worker = ConfigWorker(
            api_base=base_url, api_key=api_key, model=model,
        )
        self._worker.ping_signal.connect(self._on_ping_result)
        self._worker.start()

    def _on_ping_result(self, success: bool, key: str, args: dict):
        self._test_btn.setEnabled(True)
        if success:
            self._test_status.setText("✓ Connection successful!")
            self._test_status.setStyleSheet("font-size: 12px; color: #27AE60; font-weight: 600;")
        else:
            detail = args.get("detail", "Unknown error")
            self._test_status.setText(f"✗ Failed: {detail}")
            self._test_status.setStyleSheet("font-size: 12px; color: #E17055;")

    def get_config(self) -> dict:
        return {
            "api_key": self._key_input.text().strip(),
            "api_base": self._url_input.text().strip(),
            "model": self._model_input.text().strip(),
        }

    def validatePage(self) -> bool:
        """Require API key before proceeding."""
        if not self._key_input.text().strip():
            QMessageBox.warning(
                self, "Missing API Key",
                "Please enter your API Key to continue."
            )
            return False
        return True


# ── Page 3: Embed Model Selection ─────────────────────────────────

EMBED_OPTIONS = [
    {
        "key": "bge-small-zh-v1.5",
        "label": "Lightweight Local (bge-small-zh-v1.5)",
        "desc": "~110MB download | 512-dim | Chinese-optimized | Works offline",
    },
    {
        "key": "bge-m3",
        "label": "Recommended (BGE-M3)",
        "desc": "~1.4GB download | 1024-dim | Dense + Sparse | Multi-language | Best quality",
    },
    {
        "key": "text-embedding-3-small",
        "label": "Cloud API (text-embedding-3-small)",
        "desc": "No local download | 1536-dim | Requires internet + API key | Low-resource devices",
    },
]


class EmbedModelPage(QWizardPage):
    def __init__(self, config: dict, parent=None):
        super().__init__(parent)
        self._config = config
        self.setTitle("Choose Embedding Model")
        self.setSubTitle(
            "The embedding model converts text to vectors for semantic search. "
            "You can change this later in Settings."
        )

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._btn_group = QButtonGroup(self)
        current = self._config.get("embed_model", "bge-small-zh-v1.5")

        for i, opt in enumerate(EMBED_OPTIONS):
            group = QGroupBox()
            group_layout = QVBoxLayout(group)
            group_layout.setSpacing(4)

            radio = QRadioButton(opt["label"])
            font = QFont()
            font.setBold(True)
            radio.setFont(font)
            radio.setStyleSheet("font-size: 13px; color: #2D3436;")

            desc = QLabel(opt["desc"])
            desc.setWordWrap(True)
            desc.setStyleSheet("font-size: 11px; color: #A0AEC0; margin-left: 20px;")

            group_layout.addWidget(radio)
            group_layout.addWidget(desc)

            self._btn_group.addButton(radio, i)
            if opt["key"] == current:
                radio.setChecked(True)

            layout.addWidget(group)

        layout.addStretch()

    def get_config(self) -> dict:
        idx = self._btn_group.checkedId()
        if 0 <= idx < len(EMBED_OPTIONS):
            return {"embed_model": EMBED_OPTIONS[idx]["key"]}
        return {}
