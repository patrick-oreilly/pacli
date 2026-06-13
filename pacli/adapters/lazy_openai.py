from typing import Any


class LazyOpenAI:
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._args = args
        self._kwargs = kwargs
        self._client: Any = None

    def _load(self) -> None:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(*self._args, **self._kwargs)

    def __getattr__(self, name: str) -> Any:
        self._load()
        return getattr(self._client, name)
