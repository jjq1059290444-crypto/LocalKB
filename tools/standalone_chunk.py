"""standalone_chunk.py — 零依赖 structural chunking。

用法:
    python standalone_chunk.py <md文件或文件夹>
    python standalone_chunk.py book.md                        # 单个文件
    python standalone_chunk.py ./books_md                     # 批量处理
    python standalone_chunk.py ./books_md --out ./output/     # 统一输出目录

输出:
    - 每本书一个 .jsonl
    - 合并的 all_chunks.jsonl
    - summary.json (全局统计)

切分策略:
    - 按 H1/H2 (# / ##) 切分章节
    - 每段 350–700 字符
    - 保留代码块和表格不被截断
    - 自动剥离 MinerU YAML frontmatter
    - 层级索引: parent (完整节) + child (检索块) + parent_key 关联
"""

import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── 配置 ────────────────────────────────────────────────────────────
TARGET_MIN_CHARS = 350
TARGET_MAX_CHARS = 700
OVERLAP_CHARS = 90


# ── frontmatter ─────────────────────────────────────────────────────

def _strip_frontmatter(text: str) -> str:
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:]).strip()
    return text.strip()


def _md5(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ── structural chunking ─────────────────────────────────────────────

def _split_by_headings(text: str) -> list[tuple[str, str]]:
    """按 # / ## 标题切分，返回 [(heading, body), ...]"""
    pattern = re.compile(r"^(#{1,2}\s+.+)$", re.MULTILINE)
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


def _split_body(text: str) -> list[str]:
    """在一个 section body 内按空行/代码块/表格边界切分"""
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


def chunk_document(source_file: str, content: str, use_overlap: bool = False) -> list[dict]:
    """单文档 structural chunking + 层级索引

    每个 section 产出两种 entry:
      - type=parent:  完整节文本 (检索命中后喂 LLM 用)
      - type=child:   切分后的子块 (实际检索用), 带 parent_key 指回 parent
    """
    text = _strip_frontmatter(content)
    sections = _split_by_headings(text + "\n")

    entries = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    for sec_idx, (heading, body) in enumerate(sections):
        header_line = (heading + "\n\n") if heading else ""
        parent_id = f"{source_file}__sec_{sec_idx:04d}"
        full_text = (header_line + body).strip()
        if not full_text:
            continue

        # ── parent: 完整节文本 ──
        entries.append({
            "id":         parent_id,
            "type":       "parent",
            "heading":    heading,
            "content":    full_text,
            "char_count": len(full_text),
            "source_file": source_file,
            "chunked_at": ts,
        })

        # ── children: 子块 ──
        if len(body) <= TARGET_MAX_CHARS:
            entries.append({
                "id":         f"{parent_id}__c_0000",
                "type":       "child",
                "parent_key": parent_id,
                "heading":    heading,
                "content":    full_text,
                "char_count": len(full_text),
                "source_file": source_file,
                "chunked_at": ts,
            })
        else:
            sub_blocks = _split_body(body)
            current = header_line
            ci = 0
            for block in sub_blocks:
                if len(current) + len(block) > TARGET_MAX_CHARS and len(current) > len(header_line) + 10:
                    entries.append({
                        "id":         f"{parent_id}__c_{ci:04d}",
                        "type":       "child",
                        "parent_key": parent_id,
                        "heading":    heading,
                        "content":    current.strip(),
                        "char_count": len(current.strip()),
                        "source_file": source_file,
                        "chunked_at": ts,
                    })
                    ci += 1
                    current = header_line + block
                else:
                    current += block
            if current.strip():
                entries.append({
                    "id":         f"{parent_id}__c_{ci:04d}",
                    "type":       "child",
                    "parent_key": parent_id,
                    "heading":    heading,
                    "content":    current.strip(),
                    "char_count": len(current.strip()),
                    "source_file": source_file,
                    "chunked_at": ts,
                })

    # ── 全局索引 + MD5 ──
    total = len(entries)
    for i, e in enumerate(entries):
        e["chunk_index"]   = i
        e["total_entries"] = total
        e["md5"]           = _md5(e["content"])

    return entries


# ── 入口 ────────────────────────────────────────────────────────────

def process_one(md_path: Path, output_dir: Path) -> dict:
    """处理单个 md 文件，输出到统一目录"""
    output_dir.mkdir(parents=True, exist_ok=True)

    output_jsonl  = output_dir / f"{md_path.stem}.jsonl"
    raw = md_path.read_text(encoding="utf-8", errors="replace")
    chunks = chunk_document(md_path.name, raw)

    with open(output_jsonl, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    total_chars = sum(c["char_count"] for c in chunks)
    chars_list  = [c["char_count"] for c in chunks]
    parents     = [c for c in chunks if c.get("type") == "parent"]
    children    = [c for c in chunks if c.get("type") == "child"]
    headings    = [c["heading"] for c in chunks if c.get("heading")]

    return {
        "source_file": md_path.name,
        "parents":  len(parents),
        "children": len(children),
        "total_chunks": len(chunks),
        "total_chars": total_chars,
        "avg_chars":   round(total_chars / len(chunks)) if chunks else 0,
        "min_chars":   min(chars_list) if chars_list else 0,
        "max_chars":   max(chars_list) if chars_list else 0,
        "chunks_with_heading": len(headings),
    }


def main():
    if len(sys.argv) < 2:
        print(f"用法: python {sys.argv[0]} <md文件或文件夹> [--out 输出目录]")
        print(f"  python {sys.argv[0]} book.md                    # 单个文件")
        print(f"  python {sys.argv[0]} ./books_md --out ./out/    # 批量到统一目录")
        sys.exit(1)

    input_path = Path(sys.argv[1])

    # --out 参数
    output_dir = input_path.parent if input_path.is_file() else input_path
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--out" and i + 1 < len(args):
            output_dir = Path(args[i + 1]); i += 2
        else:
            i += 1

    if not input_path.exists():
        print(f"错误: 路径不存在 — {input_path}")
        sys.exit(1)

    # 收集 .md 文件
    if input_path.is_file():
        md_files = [input_path]
    else:
        md_files = sorted(input_path.glob("*.md"))

    if not md_files:
        print(f"错误: 未找到 .md 文件")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"找到 {len(md_files)} 个 .md 文件")
    print(f"输出: {output_dir}\n")

    total = 0
    all_summaries = []
    for i, md_path in enumerate(md_files):
        summary = process_one(md_path, output_dir)
        all_summaries.append(summary)
        p = summary["parents"]
        c = summary["children"]
        n = summary["total_chunks"]
        print(f"[{i+1}/{len(md_files)}] {md_path.name}  →  parent:{p} child:{c} total:{n}  "
              f"(avg: {summary['avg_chars']} chars)")
        total += n

    # ── 合并 all_chunks.jsonl ──
    all_path = output_dir / "all_chunks.jsonl"
    all_count = 0
    with open(all_path, "w", encoding="utf-8") as fout:
        for jsonl in sorted(output_dir.glob("*.jsonl")):
            if jsonl.name == "all_chunks.jsonl":
                continue
            for line in jsonl.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    fout.write(line + "\n")
                    all_count += 1

    # ── 全局统计 ──
    all_chars = [s["total_chars"] for s in all_summaries]
    summary_path = output_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({
            "total_files": len(md_files),
            "total_chunks": total,
            "total_chars": sum(all_chars),
            "avg_chars_per_chunk": round(sum(all_chars) / total) if total else 0,
            "per_book": all_summaries,
        }, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"完成: {total} chunks (合并 {all_count}), {len(md_files)} 本书")
    print(f"合并: {all_path}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
