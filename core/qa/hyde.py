"""hyde.py — HyDE (Hypothetical Document Embeddings) query expansion.

HyDE bridges the vocabulary gap between natural-language questions and
knowledge-base documents by first asking the LLM to generate a hypothetical
answer, then embedding that answer for retrieval instead of the raw question.

The resulting embedding captures richer domain vocabulary and document-like
structure, improving retrieval recall by 15–30% in typical RAG benchmarks.

Usage
-----
.. code-block:: python

    from core.qa.hyde import expand_query

    hypothetical = expand_query("What is the capital of France?", llm)
    # hypothetical = "The capital of France is Paris. Paris is located..."
    query_vec = embed(hypothetical)
    results = retriever.search_with_vector(query_vec)
"""

from typing import Iterator


_HYDE_PROMPT = (
    "You are a helpful assistant. Write a concise, factual paragraph "
    "answering the following question. Use the style and vocabulary of an "
    "encyclopedia entry or technical document. Do NOT say 'I think' or "
    "'I believe'. Just state the facts directly.\n\n"
    "Question: {question}\n\n"
    "Answer:"
)


def expand_query(question: str, llm,
                 prompt_template: str | None = None) -> str:
    """Generate a hypothetical document via the LLM.

    Args:
        question: the user's raw question.
        llm: an LLM client with a stream_chat(messages) → Iterator[str] method.
        prompt_template: override the HyDE prompt. Use ``{question}`` placeholder.

    Returns:
        A string of generated text suitable for embedding.
    """
    template = prompt_template or _HYDE_PROMPT
    prompt_text = template.format(question=question)

    messages = [{"role": "user", "content": prompt_text}]

    parts = []
    try:
        for token in llm.stream_chat(messages, temperature=0.1):
            parts.append(token)
    except Exception:
        # If LLM fails, fall back to the raw question
        return question

    hypothetical = "".join(parts).strip()
    if not hypothetical:
        return question

    return hypothetical
