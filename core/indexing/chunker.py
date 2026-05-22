"""chunker.py — document chunking dispatcher.

Delegates to pluggable chunking strategies registered in chunkers/__init__.py.

Strategies
----------
* structural — H2-heading based (default, works well for markdown)
* semantic   — sentence-embedding similarity based (better for prose/PDFs)
* late       — ColBERT-style late interaction (requires BGE-M3 + FlagEmbedding)
"""

from .chunkers import get_chunker


def chunk_document(doc: dict, strategy: str = "structural") -> list[dict]:
    """Split a parsed document into text chunks.

    Args:
        doc: dict from parser with keys: source_file, content, etc.
        strategy: one of 'structural', 'semantic', 'late'

    Returns:
        list of chunk dicts, each with: source_file, chunk_index,
        total_chunks, char_count, content, md5, chunked_at
    """
    chunk_fn = get_chunker(strategy)
    return chunk_fn(doc)
