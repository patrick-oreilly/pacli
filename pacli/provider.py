from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict[str, Any]


@dataclass
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None


@dataclass
class TextToken:
    text: str


ProviderEvent = TextToken | ToolCall


class Provider(Protocol):
    async def stream_completion(
        self,
        messages: list[Message],
        tool_schemas: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[ProviderEvent]: ...

    async def list_models(self) -> list[str]: ...
