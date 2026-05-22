"""history_list.py — history sidebar with search + local cache."""

import json

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLineEdit, QListWidget, QListWidgetItem, QLabel,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from core.paths import QA_HISTORY_FILE


class HistoryList(QWidget):
    """Right panel: search box + question list + cached answers."""

    question_selected = Signal(str)
    answer_selected = Signal(str, str)

    def __init__(self, i18n, parent=None):
        super().__init__(parent)
        self._i18n = i18n
        self.setMinimumWidth(200)
        self.setMaximumWidth(300)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self._title_lbl = QLabel()
        self._title_lbl.setStyleSheet("""
            font-size: 14px; font-weight: 600; color: #2D3436;
            padding: 6px 10px; border-bottom: 1px solid #E5E7EB;
        """)
        layout.addWidget(self._title_lbl)

        self._search = QLineEdit()
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet("""
            QLineEdit {
                background: #FFFFFF; color: #2D3436;
                border: 1px solid #DFE6E9; border-radius: 8px;
                padding: 8px 12px; font-size: 12px;
            }
            QLineEdit:focus { border: 1px solid #4A90D9; }
        """)
        self._search.textChanged.connect(self._on_search)
        layout.addWidget(self._search)

        self._list = QListWidget()
        self._list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setStyleSheet("""
            QListWidget {
                background: transparent; border: none; outline: none;
            }
            QListWidget::item {
                color: #2D3436; font-size: 12px;
                padding: 6px 10px; border: none;
            }
            QListWidget::item:hover { background: #F0F4F8; }
            QListWidget::item:selected { background: #E5E7EB; }
        """)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self._all_records = []
        self.retranslate()
        self._load_history()

    def retranslate(self):
        self._title_lbl.setText(self._i18n.t("history.title"))
        self._search.setPlaceholderText(self._i18n.t("history.search_placeholder"))

    def _load_history(self):
        self._all_records.clear()
        if not QA_HISTORY_FILE.exists():
            return
        try:
            with open(QA_HISTORY_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        r = json.loads(line)
                        q = r.get("question", "").strip()
                        a = r.get("answer", "").strip()
                        ts = r.get("timestamp", "")
                        if q:
                            self._all_records.append((q, a, ts))
                    except Exception:
                        pass
        except OSError:
            pass
        self._all_records.reverse()
        self._refresh_list(self._all_records)

    def refresh(self):
        self._load_history()

    def _refresh_list(self, records):
        self._list.clear()
        for q, a, ts in records:
            display = "• " + q[:50] + ("…" if len(q) > 50 else "")
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, (q, a))
            self._list.addItem(item)

    def _on_search(self, text):
        if not text.strip():
            self._refresh_list(self._all_records)
            return
        kw = text.strip().lower()
        filtered = [(q, a, ts) for q, a, ts in self._all_records if kw in q.lower()]
        self._refresh_list(filtered)

    def _on_item_clicked(self, item):
        q, a = item.data(Qt.UserRole) or (item.text().lstrip("• "), "")
        self.question_selected.emit(q)
        if a:
            self.answer_selected.emit(q, a)
