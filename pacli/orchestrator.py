from typing import Any

from pacli.events import EventBus
from pacli.provider import Provider
from pacli.tools import Tool


class Orchestrator:
    def __init__(self, provider: Provider, event_bus: EventBus) -> None:
        self._provider = provider
        self._event_bus = event_bus
        self._tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> None:
        handler = self._tools.get(tool_name)
        if handler is None:
            self._event_bus.emit("tool_result", {"tool": tool_name, "error": f"Unknown tool: {tool_name}"})
            return
        try:
            result = await handler(**kwargs)
            self._event_bus.emit("tool_result", {"tool": tool_name, "result": result})
        except Exception as e:
            self._event_bus.emit("tool_result", {"tool": tool_name, "error": str(e)})

    async def process_prompt(self, prompt: str) -> None:
        self._event_bus.emit("stream_started")
        try:
            async for token in self._provider.stream_completion(prompt):
                self._event_bus.emit("token_received", token)
        finally:
            self._event_bus.emit("stream_finished")
