from typing import AsyncIterator

from pacli.provider import Provider


class MockAdapter:
    async def stream_completion(self, prompt: str) -> AsyncIterator[str]:
        for token in ["Hello", " from", " MockAdapter!"]:
            yield token
