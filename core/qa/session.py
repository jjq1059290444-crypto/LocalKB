"""session.py — conversation session with multi-turn message history."""

import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class Turn:
    """One Q&A round."""
    question: str
    answer: str
    sources: list[dict] = field(default_factory=list)
    timestamp: str = ""


class Session:
    """Manages conversation history for one chat window.

    Each Session tracks message turns and builds context for the
    next LLM call so the model can see previous Q&A pairs.
    """

    def __init__(self, max_turns: int = 10):
        self.id: str = uuid.uuid4().hex[:12]
        self.max_turns = max_turns
        self._turns: list[Turn] = []

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    def add_turn(self, question: str, answer: str,
                 sources: list[dict] | None = None):
        """Record a completed Q&A round."""
        turn = Turn(
            question=question,
            answer=answer,
            sources=sources or [],
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self._turns.append(turn)
        # Prune old turns
        if len(self._turns) > self.max_turns:
            self._turns = self._turns[-self.max_turns:]

    def build_history_context(self) -> list[dict]:
        """Build chat-message history for the LLM context window.

        Returns a list of {"role": "user"|"assistant", "content": str}
        representing prior turns. Does NOT include the system prompt
        or the current question — those are added by prompt.build_messages().
        """
        messages = []
        for turn in self._turns:
            messages.append({"role": "user", "content": turn.question})
            messages.append({"role": "assistant", "content": turn.answer})
        return messages

    def clear(self):
        """Reset conversation history."""
        self._turns.clear()
        self.id = uuid.uuid4().hex[:12]

    def to_dict(self) -> dict:
        return {
            "session_id": self.id,
            "max_turns": self.max_turns,
            "turns": [
                {
                    "question": t.question,
                    "answer": t.answer,
                    "sources": t.sources,
                    "timestamp": t.timestamp,
                }
                for t in self._turns
            ],
        }
