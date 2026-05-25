"""export_chunks.py — 批量导出 MinerU 解析后的 markdown 为 JSONL chunks.

用法:
    D:/LocalKB/venv/Scripts/python.exe tools/export_chunks.py \
        "D:/开关电源设计知识库/parsed_docs/books" \
        "D:/开关电源设计知识库/chunks_export.jsonl"

输出每行一个 chunk:
    {"source_file": "...", "chunk_index": 0, "total_chunks": 120,
     "char_count": 482, "heading": "2.5 放置元件",
     "content": "...", "md5": "a1b2c3...",  "chunked_at": "..."}
"""

import json
import sys
import time
from pathlib import Path

def main():
    if len(sys.argv) < 3:
        print(f"用法: {sys.argv[0]} <books_dir> <output.jsonl>")
        sys.exit(1)

    books_dir = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    # 收集所有 .md 文件（排除 details 块剥离后的 _cleaned 版本）
    md_files = sorted([
        p for p in books_dir.rglob("*.md")
        if not p.name.endswith("_cleaned.md")
    ])

    print(f"找到 {len(md_files)} 个 .md 文件")
    print()

    # Lazy import — 避免污染脚本启动
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core.indexing.parser import parse_file
    from core.indexing.chunker import chunk_document

    total_chunks = 0
    skipped = 0
    parse_errors = []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    start = time.perf_counter()

    with open(output_path, "w", encoding="utf-8") as out:
        for i, md_path in enumerate(md_files):
            rel = md_path.relative_to(books_dir)
            print(f"[{i+1}/{len(md_files)}] {md_path.name}", end="", flush=True)

            try:
                doc = parse_file(md_path)
                chunks = chunk_document(doc, strategy="structural")
            except Exception as e:
                parse_errors.append(f"{rel}: {e}")
                print(f"  ✗ parse error: {e}")
                skipped += 1
                continue

            if not chunks:
                print(f"  - 0 chunks (skipped)")
                skipped += 1
                continue

            for c in chunks:
                out.write(json.dumps(c, ensure_ascii=False) + "\n")

            total_chunks += len(chunks)
            print(f"  {len(chunks)} chunks")

    elapsed = time.perf_counter() - start
    print()
    print(f"{'='*50}")
    print(f"完成: {total_chunks} chunks → {output_path}")
    print(f"耗时: {elapsed:.1f}s")
    print(f"跳过: {skipped} 文件")
    if parse_errors:
        print(f"解析错误: {len(parse_errors)}")
        for e in parse_errors[:10]:
            print(f"  - {e}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
