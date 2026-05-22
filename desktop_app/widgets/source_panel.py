"""source_panel.py — reference sources panel (file, chapter, score, preview)."""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QScrollArea, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt


class SourcePanel(QWidget):
    """Right panel: shows reference sources with file, chapter, match score."""

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

    # ── helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _short_name(source_file: str) -> str:
        """Extract a human-friendly file name from a full source path."""
        name = Path(source_file).name
        # Drop common extensions
        for ext in (".md", ".txt", ".pdf", ".docx", ".pptx", ".ppt"):
            if name.endswith(ext):
                name = name[:-len(ext)]
                break
        return name if name else source_file

    @staticmethod
    def _score_pct(score: float) -> int:
        """Convert Qdrant score to a 0–100 percentage for display."""
        # Qdrant cosine scores are typically in [0, 1]; clamp safely
        return max(0, min(100, round(score * 100)))

    def _score_bar_html(self, pct: int) -> str:
        """Render a slim CSS progress bar as inline HTML."""
        bar_color = (
            "#00B894" if pct >= 70 else
            "#FDCB6E" if pct >= 40 else
            "#E17055"
        )
        return (
            f'<span style="'
            f'display:inline-block;width:60px;height:6px;'
            f'background:#E8ECF0;border-radius:3px;'
            f'vertical-align:middle;margin:0 6px;'
            f'">'
            f'<span style="'
            f'display:inline-block;width:{pct}%;height:6px;'
            f'background:{bar_color};border-radius:3px;'
            f'"></span>'
            f'</span>'
            f'<span style="font-size:11px;color:#636E72;">{pct}%</span>'
        )

    # ── set sources ──────────────────────────────────────────────────

    def set_sources(self, sources: list):
        """Update source list.

        sources: [{source_file, heading, content, score}, ...]
        """
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
            src = s.get("source_file", "")
            if src in seen:
                continue
            seen.add(src)

            heading = s.get("heading", "")
            content = s.get("content", "")[:100]
            score = s.get("score", 0.0)
            pct = self._score_pct(score)

            # ── Card ──
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

            # Row 1: File name (bold)
            file_lbl = QLabel(self._short_name(src))
            file_lbl.setStyleSheet(
                "font-size: 12px; font-weight: 600; color: #2D3436;"
            )
            file_lbl.setWordWrap(True)
            card_layout.addWidget(file_lbl)

            # Row 2: Chapter heading (if any)
            if heading:
                ch_lbl = QLabel(
                    self._i18n.t("source.chapter_label",
                                 heading=heading)
                )
                ch_lbl.setStyleSheet("font-size: 11px; color: #636E72;")
                ch_lbl.setWordWrap(True)
                card_layout.addWidget(ch_lbl)

            # Row 3: Match score bar
            score_lbl = QLabel()
            score_lbl.setTextFormat(Qt.RichText)
            score_lbl.setText(
                self._i18n.t("source.score_label") + " " + self._score_bar_html(pct)
            )
            score_lbl.setStyleSheet("font-size: 11px; color: #636E72;")
            card_layout.addWidget(score_lbl)

            # Row 4: Content preview
            if content:
                content_lbl = QLabel(content)
                content_lbl.setStyleSheet(
                    "font-size: 11px; color: #A0AEC0;"
                    "border-top: 1px solid #E8ECF0; padding-top: 4px;"
                )
                content_lbl.setWordWrap(True)
                card_layout.addWidget(content_lbl)

            self._list_layout.addWidget(card)

        self._list_layout.addStretch()

    def clear_sources(self):
        self.set_sources([])
