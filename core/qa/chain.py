"""chain.py — orchestrate retrieval → prompt → LLM streaming."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from core.retrieval.hybrid import HybridRetriever
from .base import BaseLLMClient
from .prompt import build_messages
from .session import Session


class QAData:
    """Holds the full result of a QA round."""
    def __init__(self):
        self.question: str = ""
        self.answer: str = ""
        self.sources: list[dict] = []
        self.elapsed: float = 0.0
        self.timestamp: str = ""


class QAChain:
    """Wires retrieval + LLM for a single question with optional HyDE + Session."""

    def __init__(self, retriever: HybridRetriever, llm: BaseLLMClient,
                 system_prompt: str = "", top_k: int = 10,
                 history_file: Optional[Path] = None,
                 use_hyde: bool = False):
        self.retriever = retriever
        self.llm = llm
        self.system_prompt = system_prompt
        self.top_k = top_k
        self.history_file = history_file
        self._use_hyde = use_hyde

    def ask(self, question: str, top_k: Optional[int] = None,
            session: Optional[Session] = None) -> QAData:
        """Full QA round (blocking).

        Args:
            question: user question.
            top_k: override retrieval count.
            session: optional Session for multi-turn history + HyDE.
        """
        import time
        t0 = time.perf_counter()
        k = top_k or self.top_k

        # ── HyDE query expansion ──
        effective_query = question
        if self._use_hyde:
            from .hyde import expand_query
            effective_query = expand_query(question, self.llm)

        # ── Retrieve ──
        chunks = self.retriever.search(effective_query, top_k=k)

        # ── Build context with history ──
        history = session.build_history_context() if session else None
        messages = build_messages(self.system_prompt, question, chunks, history=history)

        # ── Stream answer ──
        answer_parts = []
        for token in self.llm.stream_chat(messages):
            answer_parts.append(token)

        answer = "".join(answer_parts)
        elapsed = time.perf_counter() - t0

        data = QAData()
        data.question = question
        data.answer = answer
        data.sources = [{"source_file": c["source_file"], "content": c["content"][:120]}
                        for c in chunks]
        data.elapsed = round(elapsed, 2)
        data.timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # ── Record turn ──
        if session:
            session.add_turn(question, answer, data.sources)

        self._save_history(data)
        return data

    def ask_stream(self, question: str, top_k: Optional[int] = None,
                   session: Optional[Session] = None) -> Iterator[str]:
        """Stream answer tokens (non-blocking, for QThread workers).

        Args:
            question: user question.
            top_k: override retrieval count.
            session: optional Session for multi-turn context.
        """
        import time

        k = top_k or self.top_k

        # ── HyDE query expansion ──
        effective_query = question
        if self._use_hyde:
            from .hyde import expand_query
            effective_query = expand_query(question, self.llm)

        # ── Retrieve ──
        chunks = self.retriever.search(effective_query, top_k=k)

        # ── Build context with history ──
        history = session.build_history_context() if session else None
        messages = build_messages(self.system_prompt, question, chunks, history=history)

        for token in self.llm.stream_chat(messages):
            yield token

    def _save_history(self, data: QAData) -> None:
        if not self.history_file:
            return
        entry = {
            "question": data.question,
            "answer": data.answer,
            "sources": data.sources,
            "elapsed_seconds": data.elapsed,
            "timestamp": data.timestamp,
        }
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
