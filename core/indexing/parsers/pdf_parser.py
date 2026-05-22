"""pdf_parser.py — parse PDF files via PyMuPDF (fitz)."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from .base import BaseParser


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


class PdfParser(BaseParser):
    """Parse PDF documents extracting text and tables."""

    def parse(self, filepath: Path) -> dict:
        import fitz  # PyMuPDF

        doc = fitz.open(str(filepath))
        pages_text: list[str] = []
        tables: list[list[str]] = []

        try:
            for page in doc:
                # ---- text extraction ----
                text = page.get_text("text")
                if text:
                    pages_text.append(text.strip())

                # ---- table extraction ----
                # PyMuPDF's built-in table detection
                found = page.find_tables()
                if found and found.tables:
                    for table in found.tables:
                        rows = table.extract()
                        if rows:
                            for row in rows:
                                clean = [
                                    str(cell).strip() if cell is not None else ""
                                    for cell in row
                                ]
                                # skip fully empty rows
                                if any(clean):
                                    tables.append(clean)
        finally:
            doc.close()

        content = "\n\n".join(pages_text)

        return {
            "source_file": filepath.name,
            "source_path": str(filepath),
            "content": content,
            "source_type": "pdf",
            "char_count": len(content),
            "line_count": content.count("\n") + 1,
            "md5": _md5(content),
            "parsed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tables": tables,
        }
