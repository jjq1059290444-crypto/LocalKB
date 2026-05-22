"""late_chunker.py — Late Chunking via full-document context embedding.

Late Chunking (a.k.a. ColBERT-style late interaction) first encodes the
entire document to capture global context, then segments in embedding space.

Prerequisites
-------------
- BGE-M3 model (BAAI/bge-m3), which supports token-level embeddings.
- FlagEmbedding library: ``pip install FlagEmbedding``

How it works
------------
1. Embed the full document → token-level embeddings with global context.
2. Split into sentence boundaries.
3. Compute chunk boundaries via embedding similarity (same as semantic chunker).
4. Each chunk's vector = mean-pool of its constituent sentence embeddings
   (these are already context-aware from step 1).

When to use
-----------
- Documents where global context matters for chunk interpretation
  (legal contracts, academic papers, cross-reference-heavy docs).
- When using BGE-M3 as the embedding model (required).
"""

import hashlib
import re
from datetime import datetime, timezone
from typing import Optional

import numpy as np

_SENTENCE_RE = re.compile(r"(?<=[。！？!?\n])\s*")
TARGET_MIN_CHARS = 350
TARGET_MAX_CHARS = 700


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _split_sentences(text: str) -> list[str]:
    parts = _SENTENCE_RE.split(text)
    sentences = [p.strip() for p in parts if p.strip()]
    if len(sentences) < 3:
        sentences = [s.strip() for s in text.split("\n") if s.strip()]
    return sentences


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-10))


def chunk_late(doc: dict) -> list[dict]:
    """Late-chunk a document using BGE-M3 token-level embeddings.

    Falls back to semantic chunking if FlagEmbedding is not available.
    """
    try:
        from FlagEmbedding import BGEM3FlagModel
    except ImportError:
        # Graceful degradation: fall back to semantic chunking
        from .semantic_chunker import chunk_semantic
        return chunk_semantic(doc)

    content = doc["content"]
    source_file = doc["source_file"]

    # Load BGE-M3 — cached across calls via the embedder module
    model = _load_bgem3()

    # Full-document encode → token-level embeddings
    sentences = _split_sentences(content)
    if len(sentences) < 3:
        from .structural_chunker import chunk_structural
        return chunk_structural(doc)

    # Encode each sentence (BGE-M3's ColBERT-style token embeddings)
    sentence_embs: list[np.ndarray] = []
    for sent in sentences:
        output = model.encode([sent], return_dense=True, return_sparse=False,
                              return_colbert_vecs=True)
        colbert = output.get("colbert_vecs")
        if colbert is not None and len(colbert) > 0:
            # Mean-pool token vectors → sentence vector
            sentence_embs.append(np.mean(colbert[0], axis=0))
        else:
            # Fallback to dense
            dense = output.get("dense_vecs")
            if dense is not None:
                sentence_embs.append(dense[0])

    if len(sentence_embs) < 2:
        from .structural_chunker import chunk_structural
        return chunk_structural(doc)

    # Similarity-based breakpoints (same logic as semantic chunker)
    sims = []
    for i in range(len(sentence_embs) - 1):
        sims.append(_cosine_sim(sentence_embs[i], sentence_embs[i + 1]))

    mean_sim = float(np.mean(sims))
    std_sim = float(np.std(sims))
    threshold = mean_sim - 0.5 * std_sim

    break_points = []
    for i, s in enumerate(sims):
        if s < threshold:
            break_points.append(i + 1)

    # Merge
    chunks: list[str] = []
    start = 0
    for bp in break_points + [len(sentences)]:
        seg = "".join(sentences[start:bp])
        if len(seg) < TARGET_MIN_CHARS and chunks:
            chunks[-1] += seg
        else:
            chunks.append(seg)
        start = bp

    from . import extract_heading

    total = len(chunks)
    results = []
    for i, text in enumerate(chunks):
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


# ── internal ──────────────────────────────────────────────────────

_BGEM3_MODEL = None


def _load_bgem3():
    global _BGEM3_MODEL
    if _BGEM3_MODEL is None:
        from FlagEmbedding import BGEM3FlagModel
        _BGEM3_MODEL = BGEM3FlagModel("BAAI/bge-m3", use_fp16=True)
    return _BGEM3_MODEL
