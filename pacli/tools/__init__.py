from collections.abc import Awaitable
from typing import Any, Protocol


class Tool(Protocol):
    name: str
    schema: dict[str, Any]

    async def __call__(self, **kwargs: Any) -> Any: ...
