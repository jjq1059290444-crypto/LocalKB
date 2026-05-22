"""chunkers/__init__.py — chunking strategy registry."""

from .structural_chunker import chunk_structural
from .semantic_chunker import chunk_semantic

CHUNKERS = {
    "structural": chunk_structural,
    "semantic": chunk_semantic,
}

# late (Late Chunking) requires BGE-M3 — registered lazily on first use
# so that ImportError from FlagEmbedding doesn't break the other strategies.
_LATE_REGISTERED = False


def _ensure_late():
    global _LATE_REGISTERED
    if not _LATE_REGISTERED:
        try:
            from .late_chunker import chunk_late
            CHUNKERS["late"] = chunk_late
        except ImportError:
            pass
        _LATE_REGISTERED = True


def get_chunker(strategy: str = "structural"):
    """Return the chunking function for *strategy*.

    Valid strategies: structural, semantic, late (BGE-M3 only).
    """
    if strategy == "late":
        _ensure_late()
    fn = CHUNKERS.get(strategy)
    if fn is None:
        raise ValueError(
            f"Unknown chunking strategy '{strategy}'. "
            f"Available: {', '.join(sorted(CHUNKERS.keys()))}"
        )
    return fn
