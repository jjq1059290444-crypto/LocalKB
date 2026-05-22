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

        _p = lambda tag, msg: print(
            f"[DEBUG {time.strftime('%H:%M:%S')}] {tag}: {msg}", flush=True
        )

        t0 = time.perf_counter()
        try:
            k = self.top_k or self.qa_chain.top_k

            # ── HyDE query expansion ──
            effective_query = self.question
            if self.qa_chain._use_hyde:
                _p("HyDE", "generating hypothetical answer...")
                t_hyde = time.perf_counter()
                effective_query = expand_query(self.question, self.qa_chain.llm)
                _p("HyDE", f"done ({time.perf_counter() - t_hyde:.2f}s)")
                _p("HyDE", f"expanded: {effective_query[:150]}...")
            else:
                _p("HyDE", "disabled")

            # ── Retrieve ──
            _p("Retrieval", f"searching (k={k})...")
            t_ret = time.perf_counter()
            chunks = self.qa_chain.retriever.search(effective_query, top_k=k)
            _p("Retrieval", f"found {len(chunks)} chunks ({time.perf_counter() - t_ret:.2f}s)")
            for i, c in enumerate(chunks[:3]):
                src = c.get("source_file", "?")
                txt = c.get("content", "")[:80]
                _p("Retrieval", f"  [{i+1}] {src}: \"{txt}...\"")

            # ── Build context with history ──
            history = self.session.build_history_context() if self.session else None
            _p("Context", f"history turns: {len(history)//2 if history else 0}")

            t_ctx = time.perf_counter()
            messages = build_messages(
                self.qa_chain.system_prompt, self.question, chunks,
                history=history,
            )
            _p("Context", f"prompt built ({time.perf_counter() - t_ctx:.2f}s)")

            # ── LLM streaming ──
            _p("LLM", "streaming...")
            t_llm = time.perf_counter()
            first_token = None
            answer_parts = []
            for token in self.qa_chain.llm.stream_chat(messages):
                if first_token is None:
                    first_token = time.perf_counter()
                answer_parts.append(token)
                self.token_signal.emit(token)

            answer = "".join(answer_parts)
            elapsed = round(time.perf_counter() - t0, 2)
            _p("LLM", f"done: {len(answer_parts)} tokens, {len(answer)} chars ({elapsed}s total)")

            sources = [
                {"source_file": c.get("source_file", ""),
                 "heading": c.get("heading", ""),
                 "content": c.get("content", "")[:120],
                 "score": c.get("score", 0.0)}
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
