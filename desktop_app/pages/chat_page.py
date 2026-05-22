"""chat_page.py — main chat page with streaming QA."""

import json
import re

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QScrollArea, QFrame,
    QSplitter, QSizePolicy,
)
from PySide6.QtCore import Qt

from widgets.chat_bubble import ChatBubble
from widgets.chat_input import ChatInput
from widgets.source_panel import SourcePanel
from widgets.history_list import HistoryList
from utils.markdown_renderer import render as md_render
from workers.qa_worker import QAWorker
from core.paths import QA_HISTORY_FILE
from core.qa.session import Session
from config.manager import ConfigManager


class ChatPage(QWidget):

    def __init__(self, qa_chain, config_manager: ConfigManager, i18n, parent=None):
        super().__init__(parent)
        self.qa_chain = qa_chain
        self._config_mgr = config_manager
        self._i18n = i18n
        self._worker = None
        self._current_ai_bubble = None

        # ── Session (multi-turn conversation) ──
        config = self._config_mgr.load()
        self._session = Session(
            max_turns=config.get("max_history_turns", 6)
        )

        p = self.palette()
        from PySide6.QtGui import QColor
        p.setColor(p.ColorRole.Window, QColor("#F9F9F9"))
        self.setPalette(p)
        self.setAutoFillBackground(True)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(0)

        # Left — chat area
        center = QWidget()
        center.setObjectName("ChatCenter")
        center.setStyleSheet("#ChatCenter { background: #FFFFFF; }")
        center_layout = QVBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)

        self._chat_scroll = QScrollArea()
        self._chat_scroll.setWidgetResizable(True)
        self._chat_scroll.setFrameShape(QFrame.NoFrame)
        self._chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._chat_scroll.setStyleSheet(
            "QScrollArea { background: #FFFFFF; border: none; }"
        )

        self._chat_container = QWidget()
        self._chat_container.setStyleSheet("background: #FFFFFF;")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(12, 12, 12, 12)
        self._chat_layout.setSpacing(6)
        self._chat_layout.addStretch()
        self._chat_scroll.setWidget(self._chat_container)

        center_layout.addWidget(self._chat_scroll, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFixedHeight(1)
        sep.setStyleSheet("background: #E5E7EB; border: none;")
        center_layout.addWidget(sep)

        self.chat_input = ChatInput(i18n)
        self.chat_input.send_clicked.connect(self._on_send)
        center_layout.addWidget(self.chat_input)

        splitter.addWidget(center)

        # Right panel — sources + history
        right_panel = QWidget()
        right_panel.setStyleSheet(
            "QWidget { background: #F9F9F9; border-left: 1px solid #E5E7EB; }"
        )
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.source_panel = SourcePanel(i18n)
        right_layout.addWidget(self.source_panel, 1)

        self.history_list = HistoryList(i18n)
        self.history_list.question_selected.connect(self._on_history_selected)
        self.history_list.answer_selected.connect(self._on_history_answer)
        right_layout.addWidget(self.history_list, 1)

        splitter.addWidget(right_panel)
        splitter.setSizes([700, 280])
        main_layout.addWidget(splitter, 1)

    def retranslate(self):
        self.chat_input.retranslate()
        self.source_panel.retranslate()
        self.history_list.retranslate()

    def _on_send(self, text):
        if self._worker and self._worker.isRunning():
            return
        if self.qa_chain is None:
            self._add_bubble(
                self._i18n.t("chat.engine_not_init"),
                is_user=False, state="ERROR",
            )
            return

        self._add_bubble(text, is_user=True, state="DONE")
        self._current_ai_bubble = self._add_bubble(
            self._i18n.t("chat.thinking"), is_user=False, state="PENDING"
        )
        self.chat_input.set_enabled(False)

        config = self._config_mgr.load()
        top_k = config.get("top_k", 10)

        self._worker = QAWorker(self.qa_chain, text, top_k=top_k,
                               session=self._session)
        self._worker.token_signal.connect(self._on_token)
        self._worker.finished_signal.connect(self._on_answer)
        self._worker.error_signal.connect(self._on_error)
        self._worker.start()

    def _on_token(self, token: str):
        if self._current_ai_bubble:
            self._current_ai_bubble.append_token(token)
        self._scroll_to_bottom()

    def _on_answer(self, result: dict):
        answer = result.get("answer", "")
        sources = result.get("sources", [])
        answer = self._strip_refs(answer)
        html = md_render(answer)
        if self._current_ai_bubble:
            self._current_ai_bubble.set_text(html, state="DONE")
        self.source_panel.set_sources(sources)
        self.history_list.refresh()
        self.chat_input.set_enabled(True)
        self.chat_input._input.setFocus()

        self._save_history(result)

    def _on_error(self, err: str):
        if self._current_ai_bubble:
            msg = self._i18n.t("chat.error_prefix", error=err)
            self._current_ai_bubble.set_text(msg, state="ERROR")
        self.chat_input.set_enabled(True)

    def _save_history(self, result: dict):
        entry = {
            "question": result.get("question", ""),
            "answer": result.get("answer", ""),
            "sources": result.get("sources", []),
            "elapsed_seconds": result.get("elapsed", 0),
            "timestamp": result.get("timestamp", ""),
        }
        try:
            QA_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(QA_HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def _on_history_selected(self, question: str):
        self.chat_input._input.setPlainText(question)

    def _on_history_answer(self, question: str, answer: str):
        self._add_bubble(question, is_user=True, state="DONE")
        html = md_render(self._strip_refs(answer))
        self._add_bubble(html, is_user=False, state="DONE")

    def _strip_refs(self, text: str) -> str:
        text = re.sub(r'\U0001F4DA\s*参考来源[：:].*?(\n|$)', '', text)
        text = re.sub(r'参考来源[：:].*?(\n|$)', '', text)
        return text.strip()

    def _add_bubble(self, text, is_user: bool, state: str = "DONE"):
        if is_user and state == "DONE":
            display = md_render(text)
        elif state in ("PENDING", "ERROR"):
            display = text
        else:
            display = md_render(text) if not is_user else text

        bubble = ChatBubble(display, is_user=is_user, state=state)
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, bubble)
        return bubble

    def _scroll_to_bottom(self):
        sb = self._chat_scroll.verticalScrollBar()
        if sb:
            sb.setValue(sb.maximum())
