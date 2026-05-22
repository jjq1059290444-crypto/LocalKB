"""text_parser.py — parse .md / .txt files into plain text."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .base import BaseParser


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter if present."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:]).strip()
    return text.strip()


class TextParser(BaseParser):
    """Parser for .md and .txt files."""

    def parse(self, filepath: Path) -> dict:
        raw = filepath.read_text(encoding="utf-8", errors="replace")
        content = _strip_frontmatter(raw)
        ext = filepath.suffix.lower().lstrip(".")

        return {
            "source_file": filepath.name,
            "source_path": str(filepath),
            "content": content,
            "source_type": ext,
            "char_count": len(content),
            "line_count": content.count("\n") + 1,
            "md5": _md5(content),
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tables": [],
        }
