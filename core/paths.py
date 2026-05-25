"""paths.py — unified path management."""

import os
import sys
from pathlib import Path


def _get_base_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


BASE_DIR = _get_base_dir()

DATA_DIR = BASE_DIR / "data"

VECTOR_DB_DIR = DATA_DIR / "vector_db"        # Qdrant Embedded
RAW_DIR = BASE_DIR / "raw_docs"
DOCS_DIR = DATA_DIR / "docs"              # uploaded originals preserved across resets

MODELS_DIR = BASE_DIR / "models"

CHUNKS_FILE = DATA_DIR / "chunks.jsonl"
BM25_INDEX_FILE = DATA_DIR / "bm25_index.pkl"
CHUNK_MAP_FILE = DATA_DIR / "chunk_map.pkl"
EMBEDDINGS_FILE = DATA_DIR / "embeddings.npy"
QA_HISTORY_FILE = DATA_DIR / "qa_history.jsonl"
REGISTRY_FILE = DATA_DIR / "registry.json"

# HuggingFace mirror for mainland China (set before any HF import)
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

DEFAULT_EMBED_MODEL = os.environ.get(
    "EMBED_MODEL_PATH",
    str(MODELS_DIR / "bge-small-zh-v1.5")
)

CONFIG_DIR = Path(os.environ.get(
    "LOCALKB_CONFIG_DIR",
    str(Path.home() / "AppData" / "Roaming" / "LocalKB")
))
CONFIG_FILE = CONFIG_DIR / "config.json"

for _d in [DATA_DIR, MODELS_DIR, CONFIG_DIR, VECTOR_DB_DIR, RAW_DIR, DOCS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)
