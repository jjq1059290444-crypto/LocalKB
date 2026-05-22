"""structural_chunker.py — H2-heading-based chunking (original algorithm)."""

import re
import hashlib
from datetime import datetime, timezone

TARGET_MIN_CHARS = 350
TARGET_MAX_CHARS = 700
OVERLAP_CHARS = 90


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def chunk_structural(doc: dict) -> list[dict]:
    """Split document by H2 boundaries + blank lines + char windows."""
    content = doc["content"]
    source_file = doc["source_file"]

    sections = _split_by_h2(content + "\n")
    raw_chunks = _flatten_sections(sections)
    chunks = _add_overlap(raw_chunks)

    total = len(chunks)
    from . import extract_heading

    results = []
    for i, text in enumerate(chunks):
        results.append({
            "source_file": source_file,
            "chunk_index": i,
            "total_chunks": total,
            "char_count": len(text),
            "content": text,
            "heading": extract_heading(text),
            "md5": _md5(text),
            "chunked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return results


# ── internal helpers ──────────────────────────────────────────────


def _split_by_h2(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(r"^(##\s+.+)$", re.MULTILINE)
    parts = []
    last_pos = 0
    last_heading = ""

    for m in pattern.finditer(text):
        if last_pos < m.start():
            body = text[last_pos:m.start()].strip()
            if body:
                parts.append((last_heading, body))
        last_heading = m.group(1).strip()
        last_pos = m.end()

    if last_pos < len(text):
        body = text[last_pos:].strip()
        if body:
            parts.append((last_heading, body))
    elif not parts and text.strip():
        parts.append(("", text.strip()))

    return parts


def _flatten_sections(sections: list[tuple[str, str]]) -> list[str]:
    chunks = []
    for heading, body in sections:
        header_line = (heading + "\n\n") if heading else ""
        if len(body) <= TARGET_MAX_CHARS:
            combined = header_line + body
            if combined.strip():
                chunks.append(combined)
            continue

        sub_blocks = _split_body(body)
        current = header_line
        for block in sub_blocks:
            if len(current) + len(block) > TARGET_MAX_CHARS and len(current) > len(header_line) + 10:
                chunks.append(current.strip())
                current = block
            else:
                current += block
        if current.strip():
            chunks.append(current.strip())
    return chunks


def _split_body(text: str) -> list[str]:
    lines = text.split("\n")
    blocks = []
    buf = []
    in_fence = False
    in_table = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            buf.append(line)
            if not in_fence:
                blocks.append("\n".join(buf))
                buf = []
            continue
        if in_fence:
            buf.append(line)
            continue
        if stripped.startswith("|") and "|" in stripped[1:]:
            in_table = True
            buf.append(line)
            continue
        elif in_table and not stripped:
            in_table = False
            blocks.append("\n".join(buf))
            buf = []
            continue
        elif in_table:
            buf.append(line)
            continue
        if not stripped and buf:
            blocks.append("\n".join(buf))
            buf = []
        else:
            buf.append(line)

    if buf:
        blocks.append("\n".join(buf))
    return [b for b in blocks if b.strip()]


def _add_overlap(chunks: list[str]) -> list[str]:
    if len(chunks) <= 1:
        return chunks
    result = []
    for i, chunk in enumerate(chunks):
        if i == 0:
            result.append(chunk[:TARGET_MAX_CHARS + OVERLAP_CHARS])
        else:
            prev_end = chunks[i - 1][-OVERLAP_CHARS:] if len(chunks[i - 1]) > OVERLAP_CHARS else chunks[i - 1]
            result.append(prev_end + "\n\n" + chunk[:TARGET_MAX_CHARS])
    return result
