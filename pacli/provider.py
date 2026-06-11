from typing import AsyncIterator, Protocol


class Provider(Protocol):
    async def stream_completion(self, prompt: str) -> AsyncIterator[str]: ...
