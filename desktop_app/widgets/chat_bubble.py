"""chat_bubble.py — single chat bubble with state machine."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QSizePolicy
from PySide6.QtCore import Qt


class ChatBubble(QFrame):
    """Chat bubble with states: PENDING / STREAMING / DONE / ERROR.

    User bubbles: gray background, right-aligned.
    AI bubbles:   transparent full-width when DONE/STREAMING,
                  gray when PENDING, red-tinted when ERROR.
    """

    def __init__(self, text: str = "", is_user: bool = False,
                 state: str = "DONE", parent=None):
        super().__init__(parent)
        self.setObjectName("ChatBubble")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._is_user = is_user
        self._state = state

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        self._bubble = QFrame()
        bubble_layout = QVBoxLayout(self._bubble)

        self._label = QLabel(text)
        self._label.setWordWrap(True)
        self._label.setTextFormat(Qt.RichText)
        self._label.setOpenExternalLinks(True)
        self._label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        bubble_layout.addWidget(self._label)

        if is_user:
            self._apply_user_style()
            layout.addStretch(1)
            layout.addWidget(self._bubble)
        else:
            self._apply_ai_style(state)
            layout.addWidget(self._bubble, 1)

    def _apply_user_style(self):
        self._bubble.setMaximumWidth(520)
        self._bubble.setMinimumHeight(44)
        self._bubble.setStyleSheet("""
            QFrame { background: #F3F4F6; border-radius: 14px; }
            QLabel { color: #2D3436; font-size: 14px; }
        """)
        self._label.setContentsMargins(14, 10, 14, 10)

    def _apply_ai_style(self, state: str):
        if state == "PENDING":
            self._bubble.setMaximumWidth(520)
            self._bubble.setMinimumHeight(44)
            self._bubble.setStyleSheet("""
                QFrame { background: #F3F4F6; border-radius: 14px; }
                QLabel { color: #636E72; font-size: 14px; }
            """)
        elif state == "ERROR":
            self._bubble.setMaximumWidth(520)
            self._bubble.setMinimumHeight(44)
            self._bubble.setStyleSheet("""
                QFrame { background: #FFF0F0; border: 1px solid #FFCDD2; border-radius: 14px; }
                QLabel { color: #C62828; font-size: 14px; }
            """)
        else:  # STREAMING or DONE
            self._bubble.setMaximumWidth(99999)
            self._bubble.setStyleSheet("""
                QFrame { background: transparent; border: none; }
                QLabel { color: #2D3436; font-size: 14px; }
            """)
        self._label.setContentsMargins(14, 10, 14, 10)

    def set_text(self, text: str, state: str = None):
        """Replace the bubble's text and optionally change state."""
        self._label.setText(text)
        if state is not None and state != self._state and not self._is_user:
            self._state = state
            self._apply_ai_style(state)
            self._relayout_for_ai()

    def append_token(self, token: str):
        """Append a token during streaming. Switches PENDING → STREAMING."""
        if self._is_user:
            return
        if self._state == "PENDING":
            self._state = "STREAMING"
            self._apply_ai_style("STREAMING")
            self._relayout_for_ai()
            self._label.setText(token)
        else:
            current = self._label.text()
            self._label.setText(current + token)

    def _relayout_for_ai(self):
        """Ensure the bubble stretches full-width after state change."""
        layout = self.layout()
        if layout is None:
            return
        for i in range(layout.count()):
            layout.setStretch(i, 1 if i == 0 else 0)
