"""cch_enrich.py — Contextual Chunk Headers 批处理（transformers 直出版）

直接加载模型，批量推理生成上下文前缀，不需要 API 服务。

用法（云电脑）:
    python cch_enrich.py /root/books_md \
        --model /root/autodl-tmp/models/Qwen/Qwen3.5-9B \
        --batch-size 6

依赖:
    pip install transformers tqdm
"""

import json
import sys
import time
from pathlib import Path

import torch
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer

# ── 配置 ────────────────────────────────────────────────────────────
BATCH_SIZE = 6          # 每批处理几个 chunk
MAX_NEW_TOKENS = 80     # CCH 前缀最多 80 tokens
CONTENT_SNIPPET = 600   # 发给模型的 content 截断长度

PROMPT_TEMPLATE = """文档：《{book_name}》
章节：{heading}
内容摘要：
{snippet}

《{book_name}》中，该片段位于"""


def build_prompt(book_name: str, heading: str, content: str) -> str:
    heading_str = heading if heading else "未知"
    snippet = content[:CONTENT_SNIPPET]
    return PROMPT_TEMPLATE.format(
        book_name=book_name,
        heading=heading_str,
        snippet=snippet,
    )


def load_model(model_path: str):
    """加载模型和分词器"""
    print(f"加载模型: {model_path}")
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        torch_dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    print(f"模型加载完成, 显存: {torch.cuda.memory_allocated()/1024**3:.1f}GB")
    return model, tokenizer


def generate_contexts(model, tokenizer, prompts: list[str]) -> list[str]:
    """批量生成上下文前缀"""
    inputs = tokenizer(
        prompts,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=2048,
    ).to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,          # greedy，确定性输出
            temperature=None,
            pad_token_id=tokenizer.eos_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )

    # 解码：只取新生成的部分
    results = []
    for i, output in enumerate(outputs):
        prompt_len = inputs["attention_mask"][i].sum().item()
        new_tokens = output[prompt_len:]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        # 清理：去掉可能的换行、引号等
        text = text.split("\n")[0].strip().strip('"').strip("'")
        results.append(text)

    return results


def process_book(book_dir: Path, model, tokenizer) -> dict:
    """处理一本书的所有 chunk"""
    jsonl_path = book_dir / "chunks.jsonl"
    if not jsonl_path.exists():
        return {"book": book_dir.name, "chunks": 0, "skipped": True}

    chunks = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                chunks.append(json.loads(line))

    if not chunks:
        return {"book": book_dir.name, "chunks": 0, "skipped": True}

    book_name = book_dir.name
    enriched = []

    # 分批处理
    for batch_start in tqdm(range(0, len(chunks), BATCH_SIZE), desc=book_name[:40]):
        batch = chunks[batch_start:batch_start + BATCH_SIZE]
        prompts = [
            build_prompt(book_name, c.get("heading", ""), c.get("content", ""))
            for c in batch
        ]

        try:
            contexts = generate_contexts(model, tokenizer, prompts)
        except Exception as e:
            print(f"  批处理错误 [{batch_start}]: {e}, 重试单条...")
            contexts = []
            for prompt in prompts:
                try:
                    ctx = generate_contexts(model, tokenizer, [prompt])
                    contexts.append(ctx[0] if ctx else "")
                except Exception:
                    contexts.append("")

        for chunk, context in zip(batch, contexts):
            chunk["context_prefix"] = context
            chunk["enriched_content"] = f"[{context}] {chunk['content']}" if context else chunk["content"]
            enriched.append(chunk)

    # 写输出
    out_path = book_dir / "enriched_chunks.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for c in enriched:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    empty = sum(1 for c in enriched if not c.get("context_prefix"))
    return {"book": book_dir.name, "chunks": len(enriched), "empty": empty}


def main():
    if len(sys.argv) < 2:
        print(f"用法: python {sys.argv[0]} <books_md_dir> [--model PATH] [--batch-size N]")
        sys.exit(1)

    root = Path(sys.argv[1])
    if not root.is_dir():
        print(f"错误: 目录不存在 — {root}")
        sys.exit(1)

    # 参数解析
    model_path = "/root/autodl-tmp/models/Qwen/Qwen3.5-9B"
    global BATCH_SIZE
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model_path = args[i + 1]
            i += 2
        elif args[i] == "--batch-size" and i + 1 < len(args):
            BATCH_SIZE = int(args[i + 1])
            i += 2
        else:
            i += 1

    # 找所有书
    book_dirs = sorted([
        p.parent for p in root.rglob("chunks.jsonl")
        if "enriched" not in p.name
    ])
    if not book_dirs:
        print(f"错误: 在 {root} 下未找到任何 chunks.jsonl")
        sys.exit(1)

    print(f"找到 {len(book_dirs)} 本书, batch_size={BATCH_SIZE}")
    print()

    # 加载模型
    model, tokenizer = load_model(model_path)

    total_chunks = 0
    total_empty = 0
    start = time.perf_counter()

    for i, d in enumerate(book_dirs):
        print(f"[{i+1}/{len(book_dirs)}]", end=" ")
        result = process_book(d, model, tokenizer)
        if result.get("skipped"):
            print(f"  {result['book']}: 无 chunks.jsonl，跳过")
            continue
        total_chunks += result["chunks"]
        total_empty += result["empty"]
        ok = result["chunks"] - result["empty"]
        print(f"  {result['chunks']} chunks, {ok} 有前缀, {result['empty']} 空")

    elapsed = time.perf_counter() - start
    print(f"\n{'='*55}")
    print(f"完成: {total_chunks} chunks, {total_empty} 空上下文")
    if total_chunks:
        print(f"耗时: {elapsed/60:.1f} 分钟  ({elapsed/total_chunks:.1f}s/chunk)")
    print(f"{'='*55}")


if __name__ == "__main__":
    main()
