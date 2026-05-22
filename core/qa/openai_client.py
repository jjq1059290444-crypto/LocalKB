"""openai_client.py — OpenAI-compatible LLM client.

Covers DeepSeek, OpenAI, and any OpenAI-compatible API (Ollama, etc.).
"""

from typing import Iterator

from openai import OpenAI

from .base import BaseLLMClient


class OpenAICompatibleClient(BaseLLMClient):
    def __init__(self, api_base: str, api_key: str, model: str,
                 temperature: float = 0.3):
        self._client = OpenAI(base_url=api_base, api_key=api_key)
        self._model = model
        self._temperature = temperature

    def stream_chat(self, messages: list[dict], **kwargs) -> Iterator[str]:
        import time as _time
        print(f"[DEBUG {_time.strftime('%H:%M:%S')}] LLM: calling {self._model}...", flush=True)
        kwargs.setdefault("temperature", self._temperature)
        t0 = _time.perf_counter()
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
            **kwargs,
        )
        token_count = 0
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                if token_count == 0:
                    print(f"[DEBUG {_time.strftime('%H:%M:%S')}] LLM: first token ({_time.perf_counter() - t0:.2f}s)", flush=True)
                token_count += 1
                yield delta.content
        print(f"[DEBUG {_time.strftime('%H:%M:%S')}] LLM: {token_count} tokens ({_time.perf_counter() - t0:.2f}s)", flush=True)

    def ping(self) -> bool:
        try:
            list(self._client.models.list())
            return True
        except Exception:
            return False
