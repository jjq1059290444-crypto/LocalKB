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

    Args:
        texts: list of input strings.
        model_name: HuggingFace model ID.
        matryoshka_dim: if set, truncate output to this many dimensions.
            Useful for BGE-M3 which supports 1024 → 768 / 512 / 256.
        batch_size: encoding batch size.
    """
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


# ── sparse embedding (BGE-M3 only) ────────────────────────────────

def embed_sparse(texts: list[str],
                 model_name: str = "BAAI/bge-m3") -> list[dict[str, float]]:
    """Encode texts into sparse lexical-weight vectors.

    Each element is a dict mapping token_id (int) → weight (float).
    Requires FlagEmbedding and a sparse-capable model like BGE-M3.

    Returns:
        List of dicts, one per input text.
    """
    _, sparse_list = embed_both(texts, model_name=model_name)
    return sparse_list


def embed_both(texts: list[str],
               model_name: str = "BAAI/bge-m3",
               matryoshka_dim: Optional[int] = None,
               batch_size: int = 32) -> tuple[np.ndarray, list[dict[int, float]]]:
    """One-pass dense + sparse encoding (BGE-M3 only).

    Returns:
        (dense_array [N, dim], list[dict[int, float]])
    """
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


def supports_sparse(model_name: str) -> bool:
    """Whether this model can output sparse lexical weights."""
    # BGE-M3 is the only model we know supports sparse natively
    if "bge-m3" in model_name.lower():
        try:
            import FlagEmbedding  # noqa: F401
            return True
        except ImportError:
            return False
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
    from FlagEmbedding import BGEM3FlagModel
    _FLAG_MODEL = BGEM3FlagModel(model_name, use_fp16=True)
    _FLAG_NAME = model_name
    return _FLAG_MODEL
