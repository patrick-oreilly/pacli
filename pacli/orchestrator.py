import asyncio
from uuid import uuid4
from typing import Any

from pacli.events import EventBus
from pacli.policy import Policy
from pacli.provider import Provider
from pacli.tool_registry import ToolRegistry

APPROVAL_TIMEOUT = 120


class Orchestrator:
    def __init__(
        self,
        provider: Provider,
        event_bus: EventBus,
        tool_registry: ToolRegistry | None = None,
        policy: Policy | None = None,
    ) -> None:
        self._provider = provider
        self._event_bus = event_bus
        self._tool_registry = tool_registry or ToolRegistry()
        self._policy = policy or Policy()
        self._pending_approvals: dict[str, asyncio.Future[bool]] = {}
        self._approval_handler = self._on_approval_response
        self._event_bus.on("approval_response", self._approval_handler)

    def cleanup(self) -> None:
        self._event_bus.off("approval_response", self._approval_handler)

    def _on_approval_response(self, data: Any) -> None:
        approval_id = data.get("id")
        future = self._pending_approvals.pop(approval_id, None)
        if future and not future.done():
            future.set_result(data.get("approved", False))

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> None:
        if self._policy.requires_approval(tool_name):
            approval_id = str(uuid4())
            future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
            self._pending_approvals[approval_id] = future
            approval_data = {"id": approval_id, "tool": tool_name}
            approval_data.update(
                (k, v) for k, v in kwargs.items() if k not in ("id", "tool")
            )
            await self._event_bus.emit("approval_required", approval_data)
            try:
                approved = await asyncio.wait_for(future, timeout=APPROVAL_TIMEOUT)
            except asyncio.TimeoutError:
                approved = False
            if not approved:
                await self._event_bus.emit(
                    "tool_result", {"tool": tool_name, "error": "Approval denied by user"}
                )
                return
        try:
            result = await self._tool_registry.execute_tool(tool_name, **kwargs)
            await self._event_bus.emit("tool_result", {"tool": tool_name, "result": result})
        except Exception as e:
            await self._event_bus.emit("tool_result", {"tool": tool_name, "error": str(e)})

    async def process_prompt(self, prompt: str) -> None:
        await self._event_bus.emit("stream_started")
        try:
            async for token in self._provider.stream_completion(prompt):
                await self._event_bus.emit("token_received", token)
        except Exception as e:
            await self._event_bus.emit("prompt_error", {"error": str(e)})
        finally:
            await self._event_bus.emit("stream_finished")
