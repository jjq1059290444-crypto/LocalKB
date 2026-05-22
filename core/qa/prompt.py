"""prompt.py — build messages array with system prompt + history + context chunks."""


def build_messages(system_prompt: str, question: str,
                   context_chunks: list[dict],
                   history: list[dict] | None = None) -> list[dict]:
    """Construct the messages array for the LLM.

    Args:
        system_prompt: user-defined system prompt.
        question: user question.
        context_chunks: retrieved chunks, each with 'content' and 'source_file'.
        history: prior turns as [{"role": ..., "content": ...}, ...].

    Returns:
        list of {"role": ..., "content": ...} dicts for OpenAI API.
    """
    import time as _time
    context_text = _build_context(context_chunks)

    user_content = (
        f"## Reference Materials\n\n"
        f"{context_text}\n\n"
        f"## Question\n\n"
        f"{question}"
    )

    messages = [{"role": "system", "content": system_prompt}]

    # Insert history between system prompt and current question
    if history:
        messages.extend(history)

    messages.append({"role": "user", "content": user_content})

    # Debug: estimate total chars
    total_chars = sum(len(m.get("content", "")) for m in messages)
    history_turns = len(history) // 2 if history else 0
    print(
        f"[DEBUG {_time.strftime('%H:%M:%S')}] Context: "
        f"{len(context_chunks)} chunks + {history_turns} history turns "
        f"= ~{total_chars} chars total",
        flush=True,
    )
    return messages


def _build_context(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks):
        src = c.get("source_file", "unknown")
        parts.append(f"[{i + 1}] Source: {src}\n{c['content']}")
    return "\n\n---\n\n".join(parts)
