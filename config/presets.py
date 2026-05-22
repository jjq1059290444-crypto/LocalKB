"""presets.py — LLM provider presets + embed model registry."""

import os
from pathlib import Path

from core.paths import MODELS_DIR

# ── Helper: resolve model name to local path if bundled ───────────

def _local_or_remote(hf_id: str) -> str:
    """Return local path if model is bundled, otherwise the HF ID."""
    local_name = hf_id.replace("/", "_")
    local_dir = MODELS_DIR / local_name
    if local_dir.exists() and (local_dir / "config.json").exists():
        return str(local_dir)
    return hf_id


# ── Providers ─────────────────────────────────────────────────────

PROVIDER_PRESETS = {
    "DeepSeek": {
        "api_base": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "OpenAI": {
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-4o",
    },
    "Custom": {
        "api_base": "",
        "model": "",
    },
}

# ── Embed Models ──────────────────────────────────────────────────

# name = _local_or_remote(...)  -- RESOLVED AT RUNTIME, see get_embed_model_path()
EMBED_MODELS = {
    "bge-small-zh-v1.5": {
        "name": "BAAI/bge-small-zh-v1.5",
        "dim": 512,
        "lang": "zh",
        "matryoshka": None,
        "sparse": False,
    },
    "all-MiniLM-L6-v2": {
        "name": "sentence-transformers/all-MiniLM-L6-v2",
        "dim": 384,
        "lang": "en",
        "matryoshka": None,
        "sparse": False,
    },
    "bge-m3": {
        "name": "BAAI/bge-m3",
        "dim": 1024,
        "lang": "multi",
        "matryoshka": [1024, 768, 512, 256],
        "sparse": True,
    },
}


def get_embed_model_path(key: str) -> str:
    """Return local path if model is bundled, otherwise the HF ID.

    Call this at *runtime* (not module-import time) so it picks up
    models that were downloaded after the app started.
    """
    info = EMBED_MODELS.get(key, EMBED_MODELS["bge-small-zh-v1.5"])
    return _local_or_remote(info["name"])
