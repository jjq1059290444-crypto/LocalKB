"""chunkers/__init__.py — chunking strategy registry."""

import re

from .structural_chunker import chunk_structural
from .semantic_chunker import chunk_semantic

_HEADING_RE = re.compile(r'^##\s+(.+)$', re.MULTILINE)


def extract_heading(text: str) -> str:
    """Extract the first H2 heading from chunk text."""
    m = _HEADING_RE.search(text)
    return m.group(1).strip() if m else ""

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
