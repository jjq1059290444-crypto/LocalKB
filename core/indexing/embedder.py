"""embedder.py — text embedding with model registry + sparse support.

Supports two backends:
- sentence-transformers  (all models, dense-only)
- FlagEmbedding          (BGE-M3: dense + sparse + ColBERT)

Public API
----------
embed(texts, model_name)              → np.ndarray [N, dim]
embed_dense(texts, model_name, dim)   → np.ndarray
embed_sparse(texts, model_name)       → list[dict[str, float]]
embed_both(texts, model_name, dim)    → (dense_ndarray, list[dict])
embed_dim(model_name)                 → int
warmup_model(model_name)              → None (load & cache in current thread)
"""

from typing import Optional

import numpy as np

# ── model cache ───────────────────────────────────────────────────
_ST_MODEL = None          # sentence-transformers model
_ST_NAME: Optional[str] = None

_FLAG_MODEL = None        # FlagEmbedding BGEM3FlagModel
_FLAG_NAME: Optional[str] = None


# ── dense embedding (all models) ──────────────────────────────────

def embed(texts: list[str],
          model_name: str = "BAAI/bge-small-zh-v1.5",
          batch_size: int = 32) -> np.ndarray:
    """Encode texts into a float32 dense array [N, dim]."""
    return embed_dense(texts, model_name=model_name, batch_size=batch_size)


def embed_dense(texts: list[str],
                model_name: str = "BAAI/bge-small-zh-v1.5",
                matryoshka_dim: Optional[int] = None,
                batch_size: int = 32) -> np.ndarray:
    """Encode texts into dense vectors, optionally with Matryoshka truncation.

    For sparse-capable models (BGE-M3), delegates to embed_both to avoid
    loading two separate model backends (SentenceTransformer + FlagEmbedding)
    for the same model, which can cause memory exhaustion and crashes.
    """
    # ── BGE-M3 / sparse-capable → use FlagEmbedding (dense + sparse in one model) ──
    if supports_sparse(model_name):
        dense, _sparse = embed_both(
            texts,
            model_name=model_name,
            matryoshka_dim=matryoshka_dim,
            batch_size=batch_size,
        )
        return dense

    # ── Other models → SentenceTransformer ──
    model = _load_st(model_name)
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        normalize_embeddings=True,
    )
    arr = np.array(embeddings, dtype=np.float32)
    if matryoshka_dim and matryoshka_dim < arr.shape[1]:
        arr = arr[:, :matryoshka_dim]
        # Re-normalize after truncation
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        arr = arr / (norms + 1e-10)
    return arr


# ── sparse embedding ─────────────────────────────────────────────

# Cache for pure-Python fallback embedder
_SPARSE_FALLBACK = None


def _get_sparse_fallback():
    """Return the pure-Python SparseEmbedder singleton."""
    global _SPARSE_FALLBACK
    if _SPARSE_FALLBACK is None:
        from core.indexing.sparse_embedder import SparseEmbedder
        _SPARSE_FALLBACK = SparseEmbedder()
    return _SPARSE_FALLBACK


def sparse_fallback_available() -> bool:
    """Whether the pure-Python sparse fallback is available (always True)."""
    return True


def embed_sparse(texts: list[str],
                 model_name: str = "BAAI/bge-m3") -> list[dict[int, float]]:
    """Encode texts into sparse lexical-weight vectors.

    Uses FlagEmbedding for BGE-M3 when available; falls back to
    pure-Python character n-gram hashing for any model.

    Returns:
        List of dicts, one per input text.
    """
    if supports_sparse(model_name):
        _, sparse_list = embed_both(texts, model_name=model_name)
        return sparse_list
    return _get_sparse_fallback().encode(texts)


def embed_both(texts: list[str],
               model_name: str = "BAAI/bge-m3",
               matryoshka_dim: Optional[int] = None,
               batch_size: int = 32) -> tuple[np.ndarray, list[dict[int, float]]]:
    """One-pass dense + sparse encoding.

    Uses FlagEmbedding for sparse-capable models (BGE-M3) when the
    library is importable. Falls back to SentenceTransformer (dense)
    + pure-Python character n-gram hashing (sparse) otherwise.

    Returns:
        (dense_array [N, dim], list[dict[int, float]])
    """
    if supports_sparse(model_name):
        return _embed_both_flag(texts, model_name, matryoshka_dim, batch_size)

    # Fallback: dense from SentenceTransformer, sparse from n-gram hasher
    dense = embed_dense(texts, model_name=model_name,
                        matryoshka_dim=matryoshka_dim, batch_size=batch_size)
    sparse_list = _get_sparse_fallback().encode(texts)
    return dense, sparse_list


def _embed_both_flag(texts: list[str],
                     model_name: str,
                     matryoshka_dim: Optional[int],
                     batch_size: int) -> tuple[np.ndarray, list[dict[int, float]]]:
    """Dense + sparse via FlagEmbedding (BGE-M3 only)."""
    flag = _load_flag(model_name)

    output = flag.encode(
        texts,
        batch_size=batch_size,
        max_length=8192,
        return_dense=True,
        return_sparse=True,
        return_colbert_vecs=False,
    )

    dense = np.array(output["dense_vecs"], dtype=np.float32)
    if matryoshka_dim and matryoshka_dim < dense.shape[1]:
        dense = dense[:, :matryoshka_dim]
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        dense = dense / (norms + 1e-10)

    # FlagEmbedding returns sparse as dict[int, float] — keep int keys
    raw_sparse = output.get("lexical_weights", [])
    sparse_list: list[dict[int, float]] = []
    for entry in raw_sparse:
        if isinstance(entry, dict):
            converted = {int(k): float(v) for k, v in entry.items()}
            sparse_list.append(converted)
        else:
            sparse_list.append({})

    return dense, sparse_list


# ── model info ────────────────────────────────────────────────────

def embed_dim(model_name: str = "BAAI/bge-small-zh-v1.5") -> int:
    """Return the embedding dimension for a model."""
    model = _load_st(model_name)
    return model.get_sentence_embedding_dimension()


def warmup_model(model_name: str) -> None:
    """Load and cache the embedding model in the *current* thread.

    Call this from the main thread BEFORE starting a background QThread
    that will use the model. PyTorch/FlagEmbedding model loading is not
    thread-safe and can segfault (~50% crash rate) when called from a
    background thread. Loading from the main thread avoids that race.
    Subsequent calls are a no-op (model is cached at module level).
    """
    import time as _time
    if supports_sparse(model_name):
        print(f"[DEBUG {_time.strftime('%H:%M:%S')}] Embedder: warmup FlagEmbedding...", flush=True)
        _load_flag(model_name)
    else:
        print(f"[DEBUG {_time.strftime('%H:%M:%S')}] Embedder: warmup SentenceTransformer...", flush=True)
        _load_st(model_name)


def supports_sparse(model_name: str) -> bool:
    """Whether this model can output sparse lexical weights natively."""
    # BGE-M3 is the only model we know supports sparse natively
    if "bge-m3" in model_name.lower():
        from importlib.util import find_spec
        if find_spec("FlagEmbedding") is not None:
            return True
    return False


# ── internal loaders ──────────────────────────────────────────────

def _load_st(model_name: str):
    global _ST_MODEL, _ST_NAME
    if _ST_MODEL is not None and _ST_NAME == model_name:
        return _ST_MODEL
    from sentence_transformers import SentenceTransformer
    _ST_MODEL = SentenceTransformer(model_name)
    _ST_NAME = model_name
    return _ST_MODEL


def _load_flag(model_name: str):
    global _FLAG_MODEL, _FLAG_NAME
    if _FLAG_MODEL is not None and _FLAG_NAME == model_name:
        return _FLAG_MODEL
    import time as _time
    print(f"[DEBUG {_time.strftime('%H:%M:%S')}] Embedder: loading FlagEmbedding ({model_name})...", flush=True)
    t0 = _time.perf_counter()
    try:
        from FlagEmbedding import BGEM3FlagModel
        _FLAG_MODEL = BGEM3FlagModel(model_name, use_fp16=False)
        _FLAG_NAME = model_name
        print(f"[DEBUG {_time.strftime('%H:%M:%S')}] Embedder: FlagEmbedding loaded ({_time.perf_counter() - t0:.1f}s)", flush=True)
        return _FLAG_MODEL
    except Exception as e:
        print(f"[DEBUG {_time.strftime('%H:%M:%S')}] Embedder: FlagEmbedding load FAILED: {e}", flush=True)
        raise
