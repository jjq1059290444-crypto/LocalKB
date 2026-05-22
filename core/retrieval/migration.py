"""migration.py — ChromaDB → Qdrant data migration.

Triggered automatically on first launch after upgrade when the old ChromaDB
directory still exists and the Qdrant directory is empty or missing.
"""

from pathlib import Path

from core.paths import CHROMA_DIR, CHROMA_COLLECTION


_MIGRATION_MARKER = ".qdrant_migration_done"


def needs_migration(qdrant_dir: Path) -> bool:
    """Return True if old ChromaDB data exists and migration hasn't been done."""
    if not CHROMA_DIR.exists():
        return False
    marker = qdrant_dir / _MIGRATION_MARKER
    if marker.exists():
        return False
    # Check chroma actually has data
    try:
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
        col = client.get_collection(CHROMA_COLLECTION)
        return col.count() > 0
    except Exception:
        return False


def run_migration(chroma_dir: Path, qdrant_store, embed_fn,
                  embed_model_name: str = "BAAI/bge-small-zh-v1.5",
                  use_sparse: bool = False,
                  progress_callback=None) -> int:
    """Migrate all data from ChromaDB to Qdrant.

    Steps:
    1. Read all chunks from ChromaDB.
    2. Re-embed texts with the current embedding model.
    3. Write to Qdrant (dense + optional sparse).
    4. Mark migration complete.

    Returns:
        Number of chunks migrated.
    """
    try:
        import chromadb
        from chromadb.config import Settings
    except ImportError:
        raise RuntimeError("chromadb must be installed to read old data")

    client = chromadb.PersistentClient(
        path=str(chroma_dir),
        settings=Settings(anonymized_telemetry=False),
    )

    try:
        col = client.get_collection(CHROMA_COLLECTION)
    except Exception:
        return 0

    # Read all data from ChromaDB
    results = col.get(include=["documents", "metadatas"])
    ids = results.get("ids", [])
    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])

    if not ids:
        return 0

    total = len(ids)
    batch_size = 32

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_ids = ids[batch_start:batch_end]
        batch_docs = documents[batch_start:batch_end]
        batch_metas = metadatas[batch_start:batch_end]

        if progress_callback:
            progress_callback(batch_start, total)

        # Generate embeddings
        if use_sparse:
            from core.indexing.embedder import embed_both
            dense, sparse_list = embed_both(batch_docs, model_name=embed_model_name)
        else:
            from core.indexing.embedder import embed_dense
            dense = embed_dense(batch_docs, model_name=embed_model_name)
            sparse_list = None

        # Write to Qdrant
        qdrant_store.add(
            ids=batch_ids,
            embeddings=dense,
            metadatas=batch_metas,
            documents=batch_docs,
            sparse_vectors=sparse_list,
        )

    if progress_callback:
        progress_callback(total, total)

    # Mark migration done — delete ChromaDB data
    try:
        client.delete_collection(CHROMA_COLLECTION)
    except Exception:
        pass

    # Write marker
    qdrant_dir = Path(qdrant_store._path)
    qdrant_dir.mkdir(parents=True, exist_ok=True)
    (qdrant_dir / _MIGRATION_MARKER).touch()

    return total
