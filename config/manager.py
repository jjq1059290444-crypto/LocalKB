"""manager.py — config persistence with DEFAULT merge + version migration."""

import json
from pathlib import Path
from typing import Any

from .presets import PROVIDER_PRESETS

CURRENT_VERSION = 1

DEFAULT_CONFIG: dict[str, Any] = {
    "version": CURRENT_VERSION,
    "api_base": "https://api.deepseek.com",
    "api_key": "",
    "model": "deepseek-chat",
    "system_prompt": (
        "You are an assistant that answers questions based solely on "
        "the reference materials provided by the user. "
        "If the reference materials do not contain relevant information, "
        "say so honestly. Never fabricate answers."
    ),
    "temperature": 0.3,
    "top_k": 10,
    "embed_model": "bge-small-zh-v1.5",
    "language": "zh",
    "setup_complete": False,
    "use_reranker": False,
    "reranker_model": "BAAI/bge-reranker-v2-m3",
    "chunking_strategy": "structural",
    "matryoshka_dim": 0,
    "hyde_enabled": False,
    "max_history_turns": 6,
}


class ConfigManager:
    def __init__(self, config_file: Path):
        self._file = config_file

    def load(self) -> dict[str, Any]:
        config = DEFAULT_CONFIG.copy()
        if self._file.exists():
            try:
                saved = json.loads(self._file.read_text("utf-8"))
                config.update(saved)
            except (json.JSONDecodeError, OSError):
                pass
        return self.migrate(config)

    def save(self, config: dict[str, Any]) -> None:
        config["version"] = CURRENT_VERSION
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def migrate(self, config: dict[str, Any]) -> dict[str, Any]:
        while config.get("version", 0) < CURRENT_VERSION:
            config = self._step(config, config["version"])
        return config

    def _step(self, config: dict[str, Any], _v: int) -> dict[str, Any]:
        config["version"] = _v + 1
        return config

    def provider_defaults(self, provider: str) -> dict[str, str]:
        return PROVIDER_PRESETS.get(provider, {})
