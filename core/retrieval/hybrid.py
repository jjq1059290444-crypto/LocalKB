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
        import time as _time
        _p = lambda msg: print(
            f"[DEBUG {_time.strftime('%H:%M:%S')}] Retrieval: {msg}", flush=True
        )

        _p(f"embedding query ({self.embed_model_name})...")
        t_emb = _time.perf_counter()

        # ── BGE-M3 / sparse-capable: one call → both vectors ──
        from core.indexing.embedder import supports_sparse, embed_both

        if supports_sparse(self.embed_model_name):
            try:
                dense_arr, sparse_list = embed_both(
                    [query], model_name=self.embed_model_name,
                )
                dense_vec = dense_arr[0]
                sparse_vec = sparse_list[0] if sparse_list else None
            except Exception as e:
                _p(f"embed_both FAILED: {e}")
                raise
        else:
            # ── Other models: dense-only via SentenceTransformer ──
            try:
                dense_vec = self._embed_dense([query])[0]
            except Exception as e:
                _p(f"dense embedding FAILED: {e}")
                raise
            sparse_vec = None

        _p(f"embedded ({_time.perf_counter() - t_emb:.2f}s), sparse={'yes' if sparse_vec else 'no'}")

        results = self.store.query(
            dense_vec, top_k=top_k, query_sparse=sparse_vec,
        )

        # Optional: re-rank with cross-encoder
        if self._use_reranker and results:
            try:
                _p("reranking...")
                t_rerank = _time.perf_counter()
                from core.retrieval.reranker import rerank
                results = rerank(query, results, model_name=self._reranker_model)
                _p(f"reranked ({_time.perf_counter() - t_rerank:.2f}s)")
            except Exception:
                pass  # graceful degradation

        return results
