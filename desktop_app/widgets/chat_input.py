"""chat_input.py — input box + send button."""

from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QTextEdit, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent


class ChatInput(QFrame):
    """Bottom input area: multi-line text box + send button."""

    send_clicked = Signal(str)

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self.setFixedHeight(62)
        self.setStyleSheet("ChatInput { background: #F9F9F9; border: none; }")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(10)

        self._input = QTextEdit()
        self._input.setFixedHeight(50)
        self._input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._input.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF;
                color: #2D3436;
                border: 1px solid #DFE6E9;
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 14px;
            }
            QTextEdit:focus {
                border: 1px solid #4A90D9;
            }
        """)
        layout.addWidget(self._input)

        self._send_btn = QPushButton()
        self._send_btn.setFixedSize(72, 50)
        self._send_btn.setCursor(Qt.PointingHandCursor)
        self._send_btn.setStyleSheet("""
            QPushButton {
                background: #E5E7EB;
                color: #2D3436;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #D1D5DB; }
            QPushButton:pressed { background: #C5C9D0; }
            QPushButton:disabled {
                background: #F0F0F0;
                color: #B2BEC3;
            }
        """)
        self._send_btn.clicked.connect(self._on_send)
        layout.addWidget(self._send_btn)

        self.retranslate()

    def retranslate(self):
        self._input.setPlaceholderText(self._i18n.t("input.placeholder"))
        self._send_btn.setText(self._i18n.t("input.send"))

    def _on_send(self):
        text = self._input.toPlainText().strip()
        if text:
            self.send_clicked.emit(text)
            self._input.clear()

    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            self._on_send()
        else:
            super().keyPressEvent(event)

    def set_enabled(self, enabled: bool):
        self._input.setEnabled(enabled)
        self._send_btn.setEnabled(enabled)
