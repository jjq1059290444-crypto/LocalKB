"""semantic_chunker.py — sentence-embedding similarity-based chunking.

Algorithm
---------
1. Split text into sentences (on 。！!？?\\n punctuation boundaries).
2. Embed each sentence via the configured embedding model.
3. Compute cosine similarity between adjacent sentences.
4. Identify semantic breakpoints where similarity < (μ − 0.5σ).
5. Merge sentence groups into chunks, respecting 350–700 char targets.

Why
---
Structural chunking (H2-based) works well for well-structured markdown, but
fails on dense prose, technical documentation without headings, or documents
with inconsistent formatting. Semantic chunking detects topic shifts in the
embedding space, producing more coherent chunks regardless of document structure.
"""

import hashlib
import re
from datetime import datetime, timezone

import numpy as np

# ── sentence splitting ────────────────────────────────────────────
_SENTENCE_RE = re.compile(
    r"(?<=[。！？!?\n])\s*"
)


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _split_sentences(text: str) -> list[str]:
    """Split text into sentence-level units, keeping the delimiter."""
    parts = _SENTENCE_RE.split(text)
    sentences = []
    for p in parts:
        p = p.strip()
        if p:
            sentences.append(p)
    # If regex didn't split much (e.g. code-heavy), fall back to newlines
    if len(sentences) < 3:
        sentences = [s.strip() for s in text.split("\n") if s.strip()]
    return sentences


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


# ── chunking ──────────────────────────────────────────────────────

TARGET_MIN_CHARS = 350
TARGET_MAX_CHARS = 700


def chunk_semantic(doc: dict) -> list[dict]:
    """Semantic chunking entry point.

    Requires the embedder to be callable for sentence-level encoding.
    Uses a lazy import so the embedder is only loaded if this strategy is chosen.
    """
    from core.indexing.embedder import embed

    content = doc["content"]
    source_file = doc["source_file"]

    sentences = _split_sentences(content)

    # Short documents: fall back to structural chunking
    if len(sentences) < 3:
        from .structural_chunker import chunk_structural
        return chunk_structural(doc)

    # Embed sentences
    emb = embed(sentences)

    # Adjacent similarities
    sims = []
    for i in range(len(emb) - 1):
        sims.append(_cosine_sim(emb[i], emb[i + 1]))

    if not sims:
        from .structural_chunker import chunk_structural
        return chunk_structural(doc)

    mean_sim = float(np.mean(sims))
    std_sim = float(np.std(sims))

    # Threshold: mean − 0.5σ
    threshold = mean_sim - 0.5 * std_sim

    # Find breakpoints (index after which we break)
    break_points: list[int] = []
    for i, s in enumerate(sims):
        if s < threshold:
            break_points.append(i + 1)

    # Merge sentences into chunks
    chunks: list[str] = []
    start = 0
    for bp in break_points + [len(sentences)]:
        seg = "".join(sentences[start:bp])
        if not seg.strip():
            start = bp
            continue

        # Pack window: if too short, merge with previous
        if len(seg) < TARGET_MIN_CHARS and chunks:
            chunks[-1] += seg
        else:
            chunks.append(seg)
        start = bp

    # Final pass: enforce max char limit by splitting oversized chunks
    final: list[str] = []
    for ch in chunks:
        if len(ch) <= TARGET_MAX_CHARS:
            final.append(ch)
        else:
            # Split by sentences within the oversized chunk
            sub = _split_sentences(ch)
            current = ""
            for s in sub:
                if len(current) + len(s) > TARGET_MAX_CHARS and current:
                    final.append(current.strip())
                    current = s
                else:
                    current += s
            if current.strip():
                final.append(current.strip())

    from . import extract_heading

    total = len(final)
    results = []
    for i, text in enumerate(final):
        results.append({
            "source_file": source_file,
            "chunk_index": i,
            "total_chunks": total,
            "char_count": len(text),
            "content": text,
            "heading": extract_heading(text),
            "md5": _md5(text),
            "chunked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return results
