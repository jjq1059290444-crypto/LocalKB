"""chroma_store.py — ChromaDB PersistentClient wrapper for vector storage."""

from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings


class ChromaStore:
    """Wraps ChromaDB PersistentClient for local vector storage.

    One collection = one knowledge base. Thread-safe within the same process.
    """

    def __init__(self, db_path: Path, collection_name: str = "local_kb"):
        self._path = str(db_path)
        self._collection_name = collection_name
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None

    @property
    def client(self) -> chromadb.PersistentClient:
        if self._client is None:
            Path(self._path).mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=self._path,
                settings=Settings(anonymized_telemetry=False),
            )
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def add(self, ids: list[str], embeddings, metadatas: list[dict],
            documents: list[str]) -> None:
        self.collection.add(
            ids=ids,
            embeddings=embeddings.tolist() if hasattr(embeddings, "tolist") else embeddings,
            metadatas=metadatas,
            documents=documents,
        )

    def query(self, query_embedding, top_k: int = 10) -> list[dict]:
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist() if hasattr(query_embedding, "tolist") else query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return _flatten_results(results)

    def count(self) -> int:
        return self.collection.count()

    def delete_by_ids(self, ids: list[str]) -> None:
        self.collection.delete(ids=ids)

    def get_all_documents(self) -> list[tuple[str, str, str]]:
        """Return all stored documents as [(id, source_file, content), ...]."""
        try:
            results = self.collection.get(include=["documents", "metadatas"])
            ids = results.get("ids", [])
            metadatas = results.get("metadatas", [])
            documents = results.get("documents", [])
            out = []
            for i, chunk_id in enumerate(ids):
                src = metadatas[i].get("source_file", "") if i < len(metadatas) else ""
                doc = documents[i] if i < len(documents) else ""
                out.append((chunk_id, src, doc))
            return out
        except Exception:
            return []

    def get_source_files(self) -> dict[str, int]:
        """Return {source_file: chunk_count} for all indexed documents."""
        try:
            results = self.collection.get(include=["metadatas"])
            metadatas = results.get("metadatas", [])
            counts: dict[str, int] = {}
            for meta in metadatas:
                src = meta.get("source_file", "unknown")
                counts[src] = counts.get(src, 0) + 1
            return counts
        except Exception:
            return {}

    def reset(self) -> None:
        try:
            self.client.delete_collection(self._collection_name)
        except Exception:
            pass
        self._collection = None


def _flatten_results(raw: dict) -> list[dict]:
    out = []
    ids = raw.get("ids", [[]])[0]
    docs = raw.get("documents", [[]])[0]
    metas = raw.get("metadatas", [[]])[0]
    dists = raw.get("distances", [[]])[0]

    for i, chunk_id in enumerate(ids):
        meta = metas[i] if i < len(metas) else {}
        doc = docs[i] if i < len(docs) else ""
        dist = dists[i] if i < len(dists) else 0.0
        out.append({
            "id": chunk_id,
            "source_file": meta.get("source_file", ""),
            "chunk_index": meta.get("chunk_index", 0),
            "content": doc,
            "score": 1.0 - dist,  # cosine distance → similarity
        })
    return out
