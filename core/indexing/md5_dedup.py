"""md5_dedup.py — file-level and chunk-level deduplication."""

import json
import hashlib
from pathlib import Path
from typing import Optional


def file_md5(filepath: Path) -> str:
    """MD5 hash of file contents."""
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def content_md5(text: str) -> str:
    """MD5 hash of text content."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class DedupRegistry:
    """Tracks processed files and chunks to avoid re-processing."""

    def __init__(self, registry_path: Path):
        self._path = registry_path
        self._data: dict[str, dict] = {}

    def load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text("utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = {}

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_processed(self, filepath: Path) -> bool:
        key = filepath.name
        if key not in self._data:
            return False
        return self._data[key].get("md5") == file_md5(filepath)

    def mark_processed(self, filepath: Path) -> None:
        self._data[filepath.name] = {
            "md5": file_md5(filepath),
        }

    def remove(self, filename: str) -> None:
        self._data.pop(filename, None)
