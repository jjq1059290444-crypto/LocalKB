"""source_panel.py — reference sources panel."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt


class SourcePanel(QWidget):
    """Right panel: shows reference sources for the current answer."""

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self.setMinimumWidth(220)
        self.setMaximumWidth(320)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet("""
            font-size: 14px; font-weight: 600;
            color: #2D3436;
            padding: 6px 10px;
            border-bottom: 1px solid #E5E7EB;
        """)
        layout.addWidget(self._title_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._list_widget = QWidget()
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_widget)

        layout.addWidget(scroll)

        self._empty = QLabel()
        self._empty.setAlignment(Qt.AlignCenter)
        self._empty.setStyleSheet("color: #B2BEC3; font-size: 12px; padding: 30px 0;")
        self._empty.setWordWrap(True)
        self._list_layout.insertWidget(0, self._empty)

        self._showing_empty = True
        self.retranslate()

    def retranslate(self):
        self._title_lbl.setText(self._i18n.t("source.title"))
        if self._showing_empty:
            self._empty.setText(self._i18n.t("source.empty_hint"))

    def set_sources(self, sources: list):
        """Update source list. sources: [{source_file, content}, ...]."""
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._showing_empty = False

        if not sources:
            self._empty = QLabel(self._i18n.t("source.no_sources"))
            self._empty.setAlignment(Qt.AlignCenter)
            self._empty.setStyleSheet("color: #B2BEC3; font-size: 12px; padding: 30px 0;")
            self._list_layout.addWidget(self._empty)
            self._list_layout.addStretch()
            self._showing_empty = True
            return

        seen = set()
        for s in sources:
            src = s.get("source_file", self._i18n.t("source.unknown"))
            if src in seen:
                continue
            seen.add(src)

            content = s.get("content", "")[:100]

            card = QFrame()
            card.setStyleSheet("""
                QFrame {
                    background: #F8FAFB;
                    border: 1px solid #E8ECF0;
                    border-radius: 8px;
                }
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 8, 10, 8)
            card_layout.setSpacing(4)

            src_lbl = QLabel(src[:50])
            src_lbl.setStyleSheet("font-size: 12px; font-weight: 600; color: #2D3436;")
            src_lbl.setWordWrap(True)
            card_layout.addWidget(src_lbl)

            if content:
                content_lbl = QLabel(content)
                content_lbl.setStyleSheet("font-size: 11px; color: #636E72;")
                content_lbl.setWordWrap(True)
                card_layout.addWidget(content_lbl)

            self._list_layout.addWidget(card)

        self._list_layout.addStretch()

    def clear_sources(self):
        self.set_sources([])
