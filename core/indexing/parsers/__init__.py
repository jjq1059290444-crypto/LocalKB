"""parsers — pluggable document parsers registered by file extension."""

from .base import BaseParser
from .text_parser import TextParser
from .pdf_parser import PdfParser
from .docx_parser import DocxParser
from .ppt_parser import PptParser

PARSER_MAP: dict[str, BaseParser] = {
    ".md": TextParser(),
    ".txt": TextParser(),
    ".pdf": PdfParser(),
    ".docx": DocxParser(),
    ".pptx": PptParser(),
    ".ppt": PptParser(),
}


def get_parser(ext: str) -> BaseParser | None:
    """Return the registered parser for a file extension, or None."""
    return PARSER_MAP.get(ext.lower(), None)


def supported_extensions() -> list[str]:
    """Return sorted list of supported file extensions."""
    return sorted(PARSER_MAP.keys())
