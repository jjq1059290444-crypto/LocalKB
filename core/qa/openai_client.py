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
        kwargs.setdefault("temperature", self._temperature)
        stream = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            stream=True,
            **kwargs,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def ping(self) -> bool:
        try:
            list(self._client.models.list())
            return True
        except Exception:
            return False
