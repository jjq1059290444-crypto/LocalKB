"""bm25.py — BM25 keyword search via rank_bm25."""

import pickle
import re
from pathlib import Path
from typing import Optional


def _tokenize(text: str) -> list[str]:
    """Tokenize Chinese + English mixed text."""
    tokens = []
    for seg in re.findall(
        r"[a-zA-Z0-9]+(?:[-'][a-zA-Z0-9]+)*|[一-鿿]|[^\s]",
        text.lower(),
    ):
        if re.match(r"[一-鿿]", seg):
            tokens.extend(list(seg))
        elif seg.strip():
            tokens.append(seg)
    return [t for t in tokens if t.strip()]


class BM25Searcher:
    def __init__(self, index_path: Optional[Path] = None):
        self._index = None
        self._chunk_ids: list[str] = []
        if index_path and index_path.exists():
            self.load(index_path)

    def build(self, texts: list[str], chunk_ids: list[str]) -> None:
        from rank_bm25 import BM25Okapi
        corpus = [_tokenize(t) for t in texts]
        self._index = BM25Okapi(corpus)
        self._chunk_ids = chunk_ids

    def search(self, query: str, top_k: int = 15) -> list[dict]:
        if self._index is None:
            return []
        tokens = _tokenize(query)
        scores = self._index.get_scores(tokens)
        ranked = sorted(
            enumerate(scores), key=lambda x: x[1], reverse=True
        )[:top_k]
        max_score = max(scores) if len(scores) > 0 else 1.0
        return [
            {
                "id": self._chunk_ids[i],
                "score": float(score / max_score) if max_score > 0 else 0.0,
            }
            for i, score in ranked
        ]

    def save(self, path: Path) -> None:
        with open(path, "wb") as f:
            pickle.dump({"index": self._index, "ids": self._chunk_ids}, f)

    def load(self, path: Path) -> None:
        with open(path, "rb") as f:
            data = pickle.load(f)
            self._index = data["index"]
            self._chunk_ids = data["ids"]
