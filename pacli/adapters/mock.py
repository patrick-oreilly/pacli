from typing import Any, AsyncIterator

from pacli.provider import Message, Provider, ProviderEvent, TextToken


class MockAdapter:
    async def stream_completion(
        self,
        messages: list[Message],
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[ProviderEvent]:
        for token in ["Hello", " from", " MockAdapter!"]:
            yield TextToken(text=token)
