import asyncio
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[Callable[[Any], Any]]] = {}

    def on(self, event_type: str, handler: Callable[[Any], Any]) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    def off(self, event_type: str, handler: Callable[[Any], Any]) -> None:
        handlers = self._handlers.get(event_type)
        if handlers:
            try:
                handlers.remove(handler)
            except ValueError:
                pass

    async def emit(
        self, event_type: str, data: Any = None, concurrent: bool = False
    ) -> None:
        handlers = list(self._handlers.get(event_type, []))
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
                logger.warning(
                    "Handler %r returned a coroutine object; did you forget 'await'?",
                    handler,
                )
                await result
        except Exception:
            logger.exception("Handler failed for event")
