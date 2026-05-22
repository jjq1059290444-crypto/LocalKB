"""qdrant_import_worker.py — QThread for importing points from another Qdrant DB."""

from PySide6.QtCore import QThread, Signal


class QdrantImportWorker(QThread):
    """Import points from a source Qdrant DB into the current VectorStore.

    Scrolls all points with vectors and payloads, then upserts in batches.
    """

    progress_signal = Signal(int, str, object)   # (stage, i18n_key, args)
    finished_signal = Signal(dict)               # {"imported": int, "errors": [...]}
    error_signal = Signal(str, object)

    def __init__(self, vector_store, source_path: str,
                 source_collection: str, parent=None):
        super().__init__(parent)
        self._store = vector_store
        self._source_path = source_path
        self._source_collection = source_collection

    def run(self):
        try:
            self.progress_signal.emit(
                1, "kb.import_reading", {"path": self._source_path}
            )
            imported = self._store.import_from(
                self._source_path, self._source_collection
            )
            self.finished_signal.emit({"imported": imported, "errors": []})
        except Exception as e:
            self.error_signal.emit("kb.import_error", {"detail": str(e)})
