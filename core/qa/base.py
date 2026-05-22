"""base.py — abstract base class for all LLM clients."""

from abc import ABC, abstractmethod
from typing import Iterator


class BaseLLMClient(ABC):
    """Every LLM backend implements stream_chat() and ping()."""

    @abstractmethod
    def stream_chat(self, messages: list[dict], **kwargs) -> Iterator[str]:
        """Streaming chat completion. Yields one token string at a time."""
        ...

    @abstractmethod
    def ping(self) -> bool:
        """Test connectivity. Returns True if the backend is reachable."""
        ...
