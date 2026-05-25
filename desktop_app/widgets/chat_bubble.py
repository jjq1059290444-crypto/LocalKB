"""chat_bubble.py — single chat bubble with state machine."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt


class ChatBubble(QFrame):
    """Chat bubble with states: PENDING / STREAMING / DONE / ERROR.

    User bubbles:  gray background, right-aligned, max 520 px wide.
    AI PENDING/ERROR:  gray / red background, left-aligned, max 520 px.
    AI STREAMING/DONE: transparent, full-width, flush left.
    """

    def __init__(self, text: str = "", is_user: bool = False,
                 state: str = "DONE", parent=None):
        super().__init__(parent)
        self.setObjectName("ChatBubble")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._is_user = is_user
        self._state = state

        # Outer layout — tight vertical margins
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(0)

        self._bubble = QFrame()
        bubble_layout = QVBoxLayout(self._bubble)
        bubble_layout.setContentsMargins(0, 0, 0, 0)
        bubble_layout.setSpacing(0)

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.RichText)
        self._label.setOpenExternalLinks(True)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._label.setAlignment(Qt.AlignLeft)

        bubble_layout.addWidget(self._label)

        if is_user:
            self._apply_user_style()
            layout.addStretch(1)
            layout.addWidget(self._bubble)
        else:
            # AI layout: [bubble] [spacer] — stretch factors are switched
            # by _apply_ai_style depending on state.
            layout.addWidget(self._bubble, 0)
            layout.addStretch(1)
            self._apply_ai_style(state)

    # ── Styles ──────────────────────────────────────────────────────

    def _apply_user_style(self):
        self._bubble.setMaximumWidth(520)
        self._bubble.setStyleSheet("""
            QFrame { background: #F3F4F6; border-radius: 14px; }
            QLabel { color: #2D3436; font-size: 14px; }
        """)
        lo = self._bubble.layout()
        if lo:
            lo.setContentsMargins(14, 7, 14, 7)
        self._label.setContentsMargins(0, 0, 0, 0)

    def _apply_ai_style(self, state: str):
        lo = self._bubble.layout()
        outer = self.layout()  # QHBoxLayout: [0]=bubble  [1]=spacer

        if state == "PENDING":
            self._bubble.setMaximumWidth(520)
            self._bubble.setStyleSheet("""
                QFrame { background: #F3F4F6; border-radius: 14px; }
                QLabel { color: #636E72; font-size: 14px; }
            """)
            if lo:
                lo.setContentsMargins(14, 7, 14, 7)
            if outer:
                outer.setStretch(0, 0)   # bubble: fixed width
                outer.setStretch(1, 1)   # spacer: push left

        elif state == "ERROR":
            self._bubble.setMaximumWidth(520)
            self._bubble.setStyleSheet("""
                QFrame { background: #FFF0F0; border: 1px solid #FFCDD2;
                         border-radius: 14px; }
                QLabel { color: #C62828; font-size: 14px; }
            """)
            if lo:
                lo.setContentsMargins(14, 7, 14, 7)
            if outer:
                outer.setStretch(0, 0)
                outer.setStretch(1, 1)

        else:  # STREAMING or DONE — full-width, flush-left
            self._bubble.setMaximumWidth(99999)
            self._bubble.setStyleSheet("""
                QFrame { background: transparent; border: none; }
                QLabel { color: #2D3436; font-size: 14px; }
            """)
            if lo:
                lo.setContentsMargins(14, 0, 14, 0)
            if outer:
                outer.setStretch(0, 1)   # bubble: fill width
                outer.setStretch(1, 0)   # spacer: invisible

        self._label.setContentsMargins(0, 0, 0, 0)

    # ── Public API ──────────────────────────────────────────────────

    def set_text(self, text: str, state: str = None):
        """Replace the bubble's text and optionally change state."""
        self._label.setText(text)
        if state is not None and state != self._state and not self._is_user:
            self._state = state
            self._apply_ai_style(state)

    def append_token(self, token: str):
        """Append a token during streaming.  Switches PENDING → STREAMING."""
        if self._is_user:
            return
        if self._state == "PENDING":
            self._state = "STREAMING"
            self._apply_ai_style("STREAMING")
            self._label.setText(token)
        else:
            current = self._label.text()
            self._label.setText(current + token)
