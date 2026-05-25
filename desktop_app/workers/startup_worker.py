"""startup_worker.py — background Qdrant + QAChain init thread.

Runs VectorStore initialization (~9s for 45k points) and QAChain
construction in a background thread so the main window can appear
immediately with a loading indicator.

Signal flow:
    status_signal(str)         – human-readable progress updates
    ready_signal(qa_chain|None, vector_store|None) – init complete
    error_signal(str phase, str detail) – unrecoverable error
"""

from PySide6.QtCore import QThread, Signal


class StartupWorker(QThread):
    """Initialize VectorStore + QAChain in a background thread.

    Emits:
        status_signal(str)  – progress messages for the status bar
        ready_signal(object, object)  – (qa_chain_or_none, vector_store_or_none)
        error_signal(str, str) – (phase, detail)
    """

    status_signal = Signal(str)
    ready_signal = Signal(object, object)
    error_signal = Signal(str, str)

    def __init__(self, config: dict, vector_db_dir, vector_size: int,
                 use_sparse: bool, embed_model_name: str,
                 history_file, parent=None):
        super().__init__(parent)
        self._config = config
        self._vector_db_dir = vector_db_dir
        self._vector_size = vector_size
        self._use_sparse = use_sparse
        self._embed_model_name = embed_model_name
        self._history_file = history_file

    def run(self):
        import time as _time

        # ── Phase 1: Open Qdrant VectorStore (~9s) ──
        self.status_signal.emit("Opening vector database…")
        print(f"[STARTUP {_time.perf_counter():7.3f}s] StartupWorker: opening Qdrant...",
              flush=True)
        t0 = _time.perf_counter()

        try:
            from core.retrieval.vector_store import VectorStore
            vector_store = VectorStore(
                self._vector_db_dir,
                collection_name="local_kb",
                vector_size=self._vector_size,
                use_sparse=self._use_sparse,
            )
        except Exception as e:
            elapsed = _time.perf_counter() - t0
            print(f"[STARTUP {elapsed:7.3f}s] StartupWorker: Qdrant FAILED: {e}",
                  flush=True)
            self.error_signal.emit("vector_db", str(e))
            return

        elapsed = _time.perf_counter() - t0
        point_count = vector_store.count()
        print(f"[STARTUP {elapsed:7.3f}s] StartupWorker: Qdrant opened"
              f" ({point_count} points)", flush=True)
        self.status_signal.emit(f"Vector DB ready ({point_count} chunks)")

        # ── Phase 2: Build QAChain ──
        self.status_signal.emit("Initializing QA engine…")
        print(f"[STARTUP {_time.perf_counter():7.3f}s] StartupWorker: building QA chain...",
              flush=True)
        t0 = _time.perf_counter()

        try:
            from core.qa.openai_client import OpenAICompatibleClient
            from core.retrieval.hybrid import HybridRetriever
            from core.qa.chain import QAChain

            api_key = self._config.get("api_key", "")
            api_base = self._config.get("api_base", "https://api.deepseek.com")
            model = self._config.get("model", "deepseek-chat")
            system_prompt = self._config.get("system_prompt", "")
            temperature = self._config.get("temperature", 0.3)
            top_k = self._config.get("top_k", 10)

            llm = OpenAICompatibleClient(
                api_base=api_base,
                api_key=api_key,
                model=model,
                temperature=temperature,
            )

            retriever = HybridRetriever(
                vector_store=vector_store,
                use_reranker=self._config.get("use_reranker", False),
                reranker_model=self._config.get("reranker_model",
                                                "BAAI/bge-reranker-v2-m3"),
            )
            retriever.embed_model_name = self._embed_model_name

            qa_chain = QAChain(
                retriever=retriever,
                llm=llm,
                system_prompt=system_prompt,
                top_k=top_k,
                history_file=self._history_file,
                use_hyde=self._config.get("hyde_enabled", False),
            )
        except Exception as e:
            elapsed = _time.perf_counter() - t0
            print(f"[STARTUP {elapsed:7.3f}s] StartupWorker: QA chain FAILED: {e}",
                  flush=True)
            # QA chain failed but vector store is alive — pass vector_store back
            self.ready_signal.emit(None, vector_store)
            return

        elapsed = _time.perf_counter() - t0
        print(f"[STARTUP {elapsed:7.3f}s] StartupWorker: QA chain ready", flush=True)
        self.status_signal.emit("QA engine ready")
        self.ready_signal.emit(qa_chain, vector_store)
