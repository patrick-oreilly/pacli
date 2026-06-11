from collections.abc import Awaitable
from typing import Any, Protocol


class Tool(Protocol):
    name: str

    async def __call__(self, **kwargs: Any) -> Any: ...
