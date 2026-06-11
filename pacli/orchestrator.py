from typing import AsyncIterator

from pacli.provider import Provider


class Orchestrator:
    def __init__(self, provider: Provider) -> None:
        self._provider = provider

    async def process_prompt(self, prompt: str) -> AsyncIterator[str]:
        async for token in self._provider.stream_completion(prompt):
            yield token
