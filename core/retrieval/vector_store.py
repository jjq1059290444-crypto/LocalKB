"""vector_store.py — Qdrant Embedded wrapper for dense + sparse vector storage.

Replaces ChromaStore + BM25Searcher with a single engine that natively
supports both dense vectors and sparse lexical vectors with built-in RRF fusion.

API is intentionally identical to ChromaStore for drop-in compatibility.
"""

import uuid
from pathlib import Path
from typing import Optional

# Lazy-loaded to avoid ~7s import penalty at app startup
_QdrantClient = None
_qmodels = None


def _lazy_import():
    global _QdrantClient, _qmodels
    if _QdrantClient is None:
        from qdrant_client import QdrantClient as QC
        _QdrantClient = QC
    if _qmodels is None:
        from qdrant_client.http import models as qm
        _qmodels = qm

NAMESPACE_KB = uuid.uuid5(uuid.NAMESPACE_DNS, "localkb")

def _make_point_id(raw_id: str) -> str:
    """Convert a non-UUID string ID to a deterministic UUID5."""
    return str(uuid.uuid5(NAMESPACE_KB, raw_id))


class VectorStore:
    """Local vector storage backed by Qdrant Embedded (Rust + RocksDB).

    One collection = one knowledge base. Thread-safe.

    Supports both dense vectors (cosine) and sparse vectors (dot-product
    lexical weights from BGE-M3) in a single collection.
    """

    def __init__(self, db_path: Path, collection_name: str = "local_kb",
                 vector_size: int = 1024,
                 use_sparse: bool = False):
        self._path = str(db_path)
        self._collection_name = collection_name
        self._vector_size = vector_size
        self._use_sparse = use_sparse
        self._client: Optional[object] = None  # QdrantClient, lazy-loaded
        _lazy_import()
        self._ensure_collection()

    # ── public API (ChromaStore-compatible) ──────────────────────

    def add(self, ids: list[str], embeddings,
            metadatas: list[dict], documents: list[str],
            sparse_vectors: Optional[list[dict[int, float]]] = None) -> None:
        """Insert chunks into the collection.

        Args:
            ids: unique chunk IDs.
            embeddings: dense vectors, shape [N, dim] as np.ndarray or list.
            metadatas: per-chunk metadata dicts.
            documents: per-chunk full text.
            sparse_vectors: optional sparse lexical weights (BGE-M3).
        """
        points = []
        for i, cid in enumerate(ids):
            dense = embeddings[i]
            if hasattr(dense, "tolist"):
                dense = dense.tolist()

            point_kwargs = {
                "id": _make_point_id(cid),
                "vector": dense,
                "payload": {
                    "source_file": metadatas[i].get("source_file", ""),
                    "chunk_index": metadatas[i].get("chunk_index", 0),
                    "heading": metadatas[i].get("heading", ""),
                    "content": documents[i] if i < len(documents) else "",
                },
            }

            # Attach sparse vector if available
            if sparse_vectors and i < len(sparse_vectors) and sparse_vectors[i]:
                sv = sparse_vectors[i]
                point_kwargs["vector"] = {
                    "": dense,  # default dense
                    "sparse": _qmodels.SparseVector(
                        indices=list(sv.keys()),
                        values=list(sv.values()),
                    ),
                }

            points.append(_qmodels.PointStruct(**point_kwargs))

        self.client.upsert(
            collection_name=self._collection_name,
            points=points,
            wait=True,
        )

    def query(self, query_embedding, top_k: int = 10,
              query_sparse: Optional[dict[int, float]] = None) -> list[dict]:
        """Search the collection.

        When query_sparse is provided, uses Qdrant's native RRF fusion.
        Otherwise, dense-only cosine search.
        """
        if query_sparse and self._use_sparse:
            return self._hybrid_query(query_embedding, query_sparse, top_k)
        return self._dense_query(query_embedding, top_k)

    def count(self) -> int:
        try:
            info = self.client.get_collection(self._collection_name)
            return info.points_count or 0
        except Exception:
            return 0

    def delete_by_ids(self, ids: list[str]) -> None:
        self.client.delete(
            collection_name=self._collection_name,
            points_selector=_qmodels.PointIdsList(
                points=[_make_point_id(i) for i in ids]
            ),
            wait=True,
        )

    def get_all_documents(self) -> list[tuple[str, str, str]]:
        """Return all stored documents as [(id, source_file, content), ...]."""
        try:
            all_points = []
            offset = None
            while True:
                batch, offset = self.client.scroll(
                    collection_name=self._collection_name,
                    limit=50000,
                    offset=offset,
                    with_payload=True,
                )
                if batch:
                    all_points.extend(batch)
                if offset is None:
                    break
            return [
                (p.id, p.payload.get("source_file", ""), p.payload.get("content", ""))
                for p in all_points
            ]
        except Exception:
            return []

    def get_source_files(self) -> dict[str, int]:
        """Return {source_file: chunk_count} for all indexed documents."""
        try:
            all_points = []
            offset = None
            while True:
                batch, offset = self.client.scroll(
                    collection_name=self._collection_name,
                    limit=50000,  # read all in one batch for typical collections
                    offset=offset,
                    with_payload=["source_file"],
                )
                if batch:
                    all_points.extend(batch)
                if offset is None:
                    break
            counts: dict[str, int] = {}
            for p in all_points:
                src = p.payload.get("source_file", "unknown")
                counts[src] = counts.get(src, 0) + 1
            return counts
        except Exception:
            return {}

    def reset(self) -> None:
        """Delete the entire collection."""
        try:
            self.client.delete_collection(self._collection_name)
        except Exception:
            pass
        self._ensure_collection()

    def import_from(self, source_db_path: str, source_collection: str) -> int:
        """Import all points from another Qdrant database directly.

        Args:
            source_db_path: Path to the source Qdrant data directory.
            source_collection: Collection name in the source database.

        Returns:
            Number of points imported.
        """
        _lazy_import()
        source = _QdrantClient(path=source_db_path)

        # Scroll all points from source
        imported = 0
        offset = None
        while True:
            batch, offset = source.scroll(
                collection_name=source_collection,
                limit=500,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            if not batch:
                break

            points = []
            for pt in batch:
                payload = pt.payload or {}
                # Map source vector to target format:
                # Source may use named vectors like {"dense": [...]},
                # target uses anonymous "" key. Extract the raw dense vector.
                raw_vec = pt.vector
                if isinstance(raw_vec, dict):
                    # Named vectors: pick the first dense vector
                    for vk, vv in raw_vec.items():
                        if vk != "sparse":
                            raw_vec = vv
                            break
                # Build point with same id, vector, and core payload fields
                points.append(_qmodels.PointStruct(
                    id=pt.id,
                    vector=raw_vec,
                    payload={
                        "source_file": payload.get("source_file", ""),
                        "chunk_index": payload.get("chunk_index", 0),
                        "content": payload.get("content_preview", payload.get("content", "")),
                    },
                ))

            self.client.upsert(
                collection_name=self._collection_name,
                points=points,
                wait=True,
            )
            imported += len(points)

            if offset is None:
                break

        source.close()
        return imported

    # ── internal ─────────────────────────────────────────────────

    @property
    def client(self) -> object:  # QdrantClient, lazy-loaded
        if self._client is None:
            _lazy_import()
            Path(self._path).mkdir(parents=True, exist_ok=True)
            self._client = _QdrantClient(path=self._path)
        return self._client

    def _ensure_collection(self):
        try:
            existing = self.client.get_collection(self._collection_name)
            # Migration: add sparse index to existing collection if enabled
            if self._use_sparse:
                existing_sparse = getattr(existing.config.params, "sparse_vectors", None) or {}
                if "sparse" not in existing_sparse:
                    try:
                        self.client.update_collection(
                            collection_name=self._collection_name,
                            sparse_vectors={
                                "sparse": _qmodels.SparseVectorParams(),
                            },
                        )
                    except Exception:
                        pass  # best-effort; will work for new docs
        except Exception:
            sparse_config = None
            if self._use_sparse:
                sparse_config = {
                    "sparse": _qmodels.SparseVectorParams(),
                }
            self.client.create_collection(
                collection_name=self._collection_name,
                vectors_config=_qmodels.VectorParams(
                    size=self._vector_size,
                    distance=_qmodels.Distance.COSINE,
                ),
                sparse_vectors_config=sparse_config,
            )

    def _dense_query(self, query_embedding, top_k: int) -> list[dict]:
        qvec = query_embedding
        if hasattr(qvec, "tolist"):
            qvec = qvec.tolist()

        results = self.client.query_points(
            collection_name=self._collection_name,
            query=qvec,
            limit=top_k,
            with_payload=True,
        )
        return _flatten_results(results)

    def _hybrid_query(self, query_embedding, query_sparse: dict[int, float],
                      top_k: int) -> list[dict]:
        qvec = query_embedding
        if hasattr(qvec, "tolist"):
            qvec = qvec.tolist()

        results = self.client.query_points(
            collection_name=self._collection_name,
            prefetch=[
                _qmodels.Prefetch(
                    query=qvec,
                    using="",
                    limit=max(top_k * 2, 20),
                ),
                _qmodels.Prefetch(
                    query=_qmodels.SparseVector(
                        indices=list(query_sparse.keys()),
                        values=list(query_sparse.values()),
                    ),
                    using="sparse",
                    limit=max(top_k, 15),
                ),
            ],
            query=_qmodels.FusionQuery(fusion=_qmodels.Fusion.RRF),
            limit=top_k,
            with_payload=True,
        )
        return _flatten_results(results)


def _flatten_results(results) -> list[dict]:
    out = []
    for pt in results.points:
        payload = pt.payload or {}
        heading = payload.get("heading", "")
        if not heading:
            # Fallback: extract from content for old data
            heading = _extract_heading(payload.get("content", ""))
        out.append({
            "id": pt.id,
            "source_file": payload.get("source_file", ""),
            "chunk_index": payload.get("chunk_index", 0),
            "heading": heading,
            "content": payload.get("content", ""),
            "score": pt.score or 0.0,
        })
    return out


def _extract_heading(text: str) -> str:
    """Extract the first H2 heading from chunk text (old-data fallback)."""
    import re
    m = re.search(r'^##\s+(.+)$', text, re.MULTILINE)
    return m.group(1).strip() if m else ""
