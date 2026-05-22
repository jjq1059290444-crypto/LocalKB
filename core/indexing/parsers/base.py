"""base.py — abstract base class for all document parsers."""

from abc import ABC, abstractmethod
from pathlib import Path


class BaseParser(ABC):
    """Every document parser implements parse() returning a standard dict."""

    @abstractmethod
    def parse(self, filepath: Path) -> dict:
        """Parse a file into structured output.

        Returns:
            dict with keys:
                source_file  — file name (str)
                source_path  — absolute path (str)
                content      — plain text body (str)
                source_type  — file extension without dot (str)
                char_count   — length of content (int)
                line_count   — number of lines (int)
                md5          — MD5 hash of content (str)
                parsed_at    — UTC ISO timestamp (str)
                tables       — optional list of table rows (list[list[str]])
        """
        ...
