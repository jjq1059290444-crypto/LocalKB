"""reranker.py — cross-encoder re-ranking for search results (optional)."""

from typing import Optional


_RERANKER = None


def _load_reranker(model_name: str = "BAAI/bge-reranker-v2-m3"):
    global _RERANKER
    if _RERANKER is not None:
        return _RERANKER
    from FlagEmbedding import FlagReranker
    _RERANKER = FlagReranker(model_name, use_fp16=False)
    return _RERANKER


def rerank(query: str, candidates: list[dict],
           model_name: str = "BAAI/bge-reranker-v2-m3") -> list[dict]:
    """Re-rank candidate chunks with a cross-encoder.

    Each candidate should have 'content' key.
    Returns the same list with updated 'score' values.
    """
    if not candidates:
        return candidates

    reranker = _load_reranker(model_name)
    pairs = [[query, c["content"]] for c in candidates]
    scores = reranker.compute_score(pairs)

    if isinstance(scores, float):
        scores = [scores]

    for i, score in enumerate(scores):
        candidates[i]["score"] = float(score)

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates
