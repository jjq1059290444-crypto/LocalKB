"""index_worker.py — QThread for document indexing with 4-stage progress."""

from pathlib import Path

from PySide6.QtCore import QThread, Signal


class IndexWorker(QThread):
    """Index documents in a background thread.

    4 stages: parse → chunk → embed → store
    Emits translation keys + format args; the GUI layer translates them.
    """

    progress_signal = Signal(int, str, object)
    finished_signal = Signal(dict)
    error_signal = Signal(str, object)

    def __init__(self, file_paths: list[str], vector_store,
                 embed_model_name: str = "BAAI/bge-small-zh-v1.5",
                 chunking_strategy: str = "structural",
                 matryoshka_dim: int = 0,
                 use_sparse: bool = False,
                 parent=None):
        super().__init__(parent)
        self._paths = file_paths
        self._store = vector_store
        self._embed_model = embed_model_name
        self._chunking_strategy = chunking_strategy
        self._matryoshka_dim = matryoshka_dim
        self._use_sparse = use_sparse
        self._canceled = False

    def cancel(self):
        self._canceled = True

    def run(self):
        added = 0
        skipped = 0
        errors = []

        try:
            from core.indexing.parser import parse_file
            from core.indexing.chunker import chunk_document
            from core.indexing.embedder import embed_dense, embed_both
        except ImportError as e:
            self.error_signal.emit(
                "index.import_error", {"detail": str(e)}
            )
            return

        for fp in self._paths:
            if self._canceled:
                break

            path = Path(fp)
            try:
                # Stage 1: Parse
                self.progress_signal.emit(
                    1, "index.parsing", {"name": path.name}
                )
                doc = parse_file(path)

                # Stage 2: Chunk
                self.progress_signal.emit(
                    2, "index.chunking", {"name": path.name}
                )
                chunks = chunk_document(doc, strategy=self._chunking_strategy)
                if not chunks:
                    skipped += 1
                    continue

                # Stage 3: Embed
                self.progress_signal.emit(
                    3, "index.embedding",
                    {"count": len(chunks), "name": path.name}
                )
                texts = [c["content"] for c in chunks]

                sparse_vecs = None
                if self._use_sparse:
                    try:
                        dense, sparse_vecs = embed_both(
                            texts, model_name=self._embed_model,
                            matryoshka_dim=self._matryoshka_dim or None,
                        )
                    except (ImportError, Exception):
                        # FlagEmbedding not installed or sparse failed —
                        # fall back to dense-only gracefully
                        dense = embed_dense(
                            texts, model_name=self._embed_model,
                            matryoshka_dim=self._matryoshka_dim or None,
                        )
                else:
                    dense = embed_dense(
                        texts, model_name=self._embed_model,
                        matryoshka_dim=self._matryoshka_dim or None,
                    )

                # Stage 4: Store
                self.progress_signal.emit(
                    4, "index.storing", {"count": len(chunks)}
                )
                ids = [f"{doc['source_file']}_{c['chunk_index']}" for c in chunks]
                metadatas = [
                    {"source_file": c["source_file"],
                     "chunk_index": c["chunk_index"]}
                    for c in chunks
                ]
                self._store.add(
                    ids=ids, embeddings=dense,
                    metadatas=metadatas, documents=texts,
                    sparse_vectors=sparse_vecs,
                )
                added += len(chunks)

            except Exception as e:
                errors.append(f"{path.name}: {e}")

        self.finished_signal.emit({
            "added": added,
            "skipped": skipped,
            "errors": errors,
        })
