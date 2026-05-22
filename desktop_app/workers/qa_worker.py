"""qa_worker.py — QThread for streaming QA, non-blocking UI."""

from PySide6.QtCore import QThread, Signal


class QAWorker(QThread):
    """Run QAChain.ask_stream() in a background thread.

    Emits tokens one-by-one, then a finished dict with full result.
    Supports multi-turn Session for conversational context.
    """

    token_signal = Signal(str)
    finished_signal = Signal(dict)
    error_signal = Signal(str)

    def __init__(self, qa_chain, question: str, top_k: int = 10,
                 session=None, parent=None):
        super().__init__(parent)
        self.qa_chain = qa_chain
        self.question = question
        self.top_k = top_k
        self.session = session

    def run(self):
        import time
        from datetime import datetime, timezone
        from core.qa.prompt import build_messages
        from core.qa.hyde import expand_query

        t0 = time.perf_counter()
        try:
            k = self.top_k or self.qa_chain.top_k

            # ── HyDE query expansion ──
            effective_query = self.question
            if self.qa_chain._use_hyde:
                effective_query = expand_query(self.question, self.qa_chain.llm)

            # ── Retrieve ──
            chunks = self.qa_chain.retriever.search(effective_query, top_k=k)

            # ── Build context with history ──
            history = self.session.build_history_context() if self.session else None
            messages = build_messages(
                self.qa_chain.system_prompt, self.question, chunks,
                history=history,
            )

            answer_parts = []
            for token in self.qa_chain.llm.stream_chat(messages):
                answer_parts.append(token)
                self.token_signal.emit(token)

            answer = "".join(answer_parts)
            elapsed = round(time.perf_counter() - t0, 2)

            sources = [
                {"source_file": c.get("source_file", ""),
                 "content": c.get("content", "")[:120]}
                for c in chunks
            ]

            # ── Record turn in session ──
            if self.session:
                self.session.add_turn(self.question, answer, sources)

            self.finished_signal.emit({
                "question": self.question,
                "answer": answer,
                "sources": sources,
                "elapsed": elapsed,
                "timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
            })
        except Exception as e:
            self.error_signal.emit(str(e))
