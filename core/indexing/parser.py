"""parser.py — document parser dispatcher.

Delegates to pluggable parsers registered by file extension in parsers/__init__.py.
"""

from pathlib import Path

from .parsers import get_parser, PARSER_MAP


def parse_file(filepath: Path) -> dict:
    """Parse a file using the registered parser for its extension.

    Returns:
        dict with keys: source_file, source_path, content, source_type,
        char_count, line_count, md5, parsed_at, tables
    """
    ext = filepath.suffix.lower()
    parser = get_parser(ext)
    if parser is None:
        raise ValueError(
            f"Unsupported file type '{ext}'. "
            f"Supported: {', '.join(sorted(PARSER_MAP.keys()))}"
        )
    return parser.parse(filepath)


def parse_files(filepaths: list[Path]) -> list[dict]:
    """Batch parse multiple files."""
    return [parse_file(p) for p in filepaths]
