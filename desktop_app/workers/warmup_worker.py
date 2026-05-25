"""warmup_worker.py — background model warmup thread.

Loads the embedding model at app startup so that the first QA query
doesn't block the UI with a synchronous warmup call.  Once the model
is loaded and cached at module level, subsequent QAWorker threads can
use it without re-loading.
"""

from PySide6.QtCore import QThread, Signal


class WarmupWorker(QThread):
    """Load the embedding model in a background thread.

    Signals:
        ready()  – model loaded successfully, UI can enable input
        error(str) – loading failed, error message for status bar
    """

    ready = Signal()
    error = Signal(str)

    def __init__(self, embed_model_name: str, parent=None):
        super().__init__(parent)
        self._embed_model_name = embed_model_name

    def run(self):
        import time as _time

        try:
            print(
                f"[DEBUG {_time.strftime('%H:%M:%S')}] WarmupWorker: "
                f"loading {self._embed_model_name}...",
                flush=True,
            )
            t0 = _time.perf_counter()

            from core.indexing.embedder import warmup_model

            warmup_model(self._embed_model_name)

            elapsed = _time.perf_counter() - t0
            print(
                f"[DEBUG {_time.strftime('%H:%M:%S')}] WarmupWorker: "
                f"done ({elapsed:.1f}s)",
                flush=True,
            )
            self.ready.emit()

        except Exception as e:
            print(
                f"[DEBUG {_time.strftime('%H:%M:%S')}] WarmupWorker: "
                f"FAILED: {e}",
                flush=True,
            )
            self.error.emit(str(e))
