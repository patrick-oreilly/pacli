from typing import Protocol


class Sandbox(Protocol):
    async def read_file(self, path: str) -> str: ...
