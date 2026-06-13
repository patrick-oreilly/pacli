import asyncio
import logging
from enum import StrEnum
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventType(StrEnum):
    STREAM_STARTED = "stream_started"
    TOKEN_RECEIVED = "token_received"
    STREAM_FINISHED = "stream_finished"
    TOOL_USED = "tool_used"
    TOOL_RESULT = "tool_result"
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_RESPONSE = "approval_response"
    PROMPT_SUBMITTED = "prompt_submitted"
    PROMPT_ERROR = "prompt_error"
    SYSTEM_EVENT = "system_event"
    SYSTEM_FAULT = "system_fault"
    SLASH_COMMAND = "slash_command"
    REFLECTION = "reflection"


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Any], Any]]] = {}

    def on(self, event_type: EventType | str, handler: Callable[[Any], Any]) -> None:
        key = str(event_type)
        self._handlers.setdefault(key, []).append(handler)

    def off(self, event_type: EventType | str, handler: Callable[[Any], Any]) -> None:
        key = str(event_type)
        handlers = self._handlers.get(key)
        if handlers:
            try:
                handlers.remove(handler)
            except ValueError:
                pass

    async def emit(
        self, event_type: EventType | str, data: Any = None, concurrent: bool = False
    ) -> None:
        key = str(event_type)
        handlers = list(self._handlers.get(key, []))
        if concurrent:
            await asyncio.gather(
                *[self._safe_call(h, data) for h in handlers]
            )
        else:
            for handler in handlers:
                await self._safe_call(handler, data)

    async def _safe_call(
        self, handler: Callable[[Any], Any], data: Any
    ) -> None:
        try:
            result = handler(data)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            logger.exception("Handler failed for event")
