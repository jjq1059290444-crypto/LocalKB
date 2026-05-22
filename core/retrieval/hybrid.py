"""hybrid.py — hybrid retrieval via Qdrant Embedded (dense + sparse + RRF).

Qdrant natively fuses dense and sparse results with Reciprocal Rank Fusion,
so the application-layer RRF code is no longer needed.
"""

from typing import Optional

from .vector_store import VectorStore


class HybridRetriever:
    """Combines dense semantic search and sparse keyword search via Qdrant.

    When BGE-M3 is the embedding model, a single query produces both
    dense and sparse vectors; Qdrant fuses their results with built-in RRF.
    Otherwise, falls back to dense-only cosine search.
    """

    def __init__(self, vector_store: VectorStore,
                 use_reranker: bool = False,
                 reranker_model: str = "BAAI/bge-reranker-v2-m3"):
        self.store = vector_store
        self.embed_model_name = "BAAI/bge-small-zh-v1.5"
        self._embed_fn = None
        self._use_reranker = use_reranker
        self._reranker_model = reranker_model

    def _embed_dense(self, texts: list[str]):
        if self._embed_fn is None:
            from core.indexing.embedder import embed_dense as _e
            self._embed_fn = _e
        return self._embed_fn(texts, model_name=self.embed_model_name)

    def _embed_sparse(self, texts: list[str]) -> Optional[list[dict[int, float]]]:
        try:
            from core.indexing.embedder import embed_sparse, supports_sparse
            if supports_sparse(self.embed_model_name):
                return embed_sparse(texts, model_name=self.embed_model_name)
        except Exception:
            pass
        return None

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        # Dense query vector
        dense_vec = self._embed_dense([query])[0]

        # Sparse query vector (if BGE-M3 is available)
        sparse_list = self._embed_sparse([query])
        sparse_vec = sparse_list[0] if sparse_list else None

        results = self.store.query(
            dense_vec, top_k=top_k, query_sparse=sparse_vec,
        )

        # Optional: re-rank with cross-encoder
        if self._use_reranker and results:
            try:
                from core.retrieval.reranker import rerank
                results = rerank(query, results, model_name=self._reranker_model)
            except Exception:
                pass  # graceful degradation

        return results
