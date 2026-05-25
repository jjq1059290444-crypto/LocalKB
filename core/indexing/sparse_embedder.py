"""sparse_embedder.py — pure-Python sparse lexical-weight vectors.

Uses character n-grams (1–3) with a hashing trick to produce fixed-size
sparse vectors. No C extensions, no external tokenizer — works on any
platform without segfault risk.

Format: list[dict[int, float]] where int is a hashed token index and
float is the TF-IDF-like weight (L2-normalized per document).
"""

import math
import re
from typing import Optional

VOCAB_SIZE = 2**24  # ~16.8M, modulo target for hash


def _char_ngrams(text: str, n: int) -> list[str]:
    """Extract character n-grams from text. Whitespace-normalized."""
    # Collapse whitespace to single space
    clean = re.sub(r"\s+", " ", text.strip())
    if len(clean) < n:
        return [clean] if clean else []
    return [clean[i:i + n] for i in range(len(clean) - n + 1)]


def _hash_token(token: str) -> int:
    """Hash a token string to an integer in [0, VOCAB_SIZE)."""
    return hash(token) % VOCAB_SIZE


def _count_tokens(tokens: list[str]) -> dict[int, int]:
    """Count token frequencies, mapping each token to its hashed index."""
    counts: dict[int, int] = {}
    for t in tokens:
        idx = _hash_token(t)
        counts[idx] = counts.get(idx, 0) + 1
    return counts


class SparseEmbedder:
    """Pure-Python sparse vector encoder using character n-grams + hashing.

    Produces L2-normalized sparse vectors compatible with Qdrant's
    SparseVector format. Useful as a fallback when FlagEmbedding's
    C extensions cannot be loaded (e.g. Windows CPU PyTorch segfault).
    """

    def __init__(self, ngram_range: tuple[int, int] = (1, 3),
                 vocab_size: int = VOCAB_SIZE):
        self._ngram_min, self._ngram_max = ngram_range
        self._vocab_size = vocab_size

    def encode(self, texts: list[str]) -> list[dict[int, float]]:
        """Encode texts into sparse lexical-weight vectors.

        Returns one dict per input text, mapping token_id → weight.
        Weights are L2-normalized within each document.
        """
        results: list[dict[int, float]] = []
        for text in texts:
            weights = self._encode_one(text)
            results.append(weights)
        return results

    def _encode_one(self, text: str) -> dict[int, float]:
        # Collect n-grams for n = min..max
        all_tokens: list[str] = []
        for n in range(self._ngram_min, self._ngram_max + 1):
            all_tokens.extend(_char_ngrams(text, n))

        if not all_tokens:
            return {}

        # Term frequencies (hashed)
        tf = _count_tokens(all_tokens)

        # Raw weight: log(1 + tf), dampens repeated terms
        raw: dict[int, float] = {}
        for idx, count in tf.items():
            raw[idx] = math.log(1.0 + count)

        # L2 normalize
        norm = math.sqrt(sum(w * w for w in raw.values()))
        if norm > 0:
            return {idx: w / norm for idx, w in raw.items()}
        return raw
