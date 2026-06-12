import asyncio
from uuid import uuid4
from typing import Any

from pacli.events import EventBus
from pacli.policy import Policy
from pacli.provider import Message, Provider, TextToken, ToolCall
from pacli.tool_registry import ToolRegistry

APPROVAL_TIMEOUT = 120


class Orchestrator:
    def __init__(
        self,
        provider: Provider,
        event_bus: EventBus,
        tool_registry: ToolRegistry | None = None,
        policy: Policy | None = None,
        provider_factory: dict[str, tuple] | None = None,
        loop_max_iterations: int = 20,
    ) -> None:
        self._provider = provider
        self._event_bus = event_bus
        self._tool_registry = tool_registry or ToolRegistry()
        self._policy = policy or Policy()
        self._provider_factory = provider_factory or {}
        self._active_provider_name = "mock"
        self._active_model_name = "mock"
        self._loop_max_iterations = loop_max_iterations
        self._pending_approvals: dict[str, asyncio.Future[bool]] = {}
        self._approval_handler = self._on_approval_response
        self._slash_handler = self._on_slash_command
        self._event_bus.on("approval_response", self._approval_handler)
        self._event_bus.on("slash_command", self._slash_handler)

    def cleanup(self) -> None:
        self._event_bus.off("approval_response", self._approval_handler)
        self._event_bus.off("slash_command", self._slash_handler)

    def _on_approval_response(self, data: Any) -> None:
        approval_id = data.get("id")
        future = self._pending_approvals.pop(approval_id, None)
        if future and not future.done():
            future.set_result(data.get("approved", False))

    async def execute_tool(self, tool_name: str, **kwargs: Any) -> tuple[str, bool]:
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
                error = "Approval denied by user"
                await self._event_bus.emit(
                    "tool_result", {"tool": tool_name, "args": kwargs, "error": error}
                )
                return (error, True)
        try:
            result = await self._tool_registry.execute_tool(tool_name, **kwargs)
            await self._event_bus.emit("tool_result", {"tool": tool_name, "args": kwargs, "result": result})
            return (result, False)
        except Exception as e:
            error = str(e)
            await self._event_bus.emit("tool_result", {"tool": tool_name, "args": kwargs, "error": error})
            return (error, True)

    async def process_prompt(self, prompt: str) -> None:
        await self._event_bus.emit("stream_started")
        try:
            messages: list[Message] = [Message(role="user", content=prompt)]
            tool_schemas = self._tool_registry.tool_schemas
            for _ in range(self._loop_max_iterations):
                text_chunks: list[str] = []
                tool_calls: list[ToolCall] = []

                async for event in self._provider.stream_completion(messages, tool_schemas):
                    if isinstance(event, TextToken):
                        await self._event_bus.emit("token_received", event)
                        text_chunks.append(event.text)
                    elif isinstance(event, ToolCall):
                        tool_calls.append(event)

                if not tool_calls:
                    assistant_content = "".join(text_chunks) if text_chunks else None
                    messages.append(Message(role="assistant", content=assistant_content))
                    break

                assistant_content = "".join(text_chunks) if text_chunks else None
                messages.append(Message(role="assistant", content=assistant_content, tool_calls=tool_calls))

                for tc in tool_calls:
                    await self._event_bus.emit("tool_used", {"tool": tc.name, "args": tc.args, "id": tc.id})
                    result, is_error = await self.execute_tool(tc.name, **tc.args)
                    content = f"Error: {result}" if is_error else result
                    messages.append(Message(role="tool", content=content, tool_call_id=tc.id))
            else:
                await self._event_bus.emit(
                    "tool_result",
                    {"tool": "_loop", "args": {}, "error": f"Exceeded max iterations ({self._loop_max_iterations})"},
                )
        except Exception as e:
            await self._event_bus.emit("prompt_error", {"error": str(e)})
        finally:
            await self._event_bus.emit("stream_finished")

    async def _on_slash_command(self, data: str) -> None:
        parts = data.split(" ", 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/provider" and arg:
            entry = self._provider_factory.get(arg)
            if entry:
                cls, *args = entry
                self._provider = cls(*args)
                self._active_provider_name = arg
                message = f"·· runtime · provider switched to {arg}"
            else:
                available = list(self._provider_factory.keys()) if self._provider_factory else ["mock"]
                message = f"·· runtime · unknown provider: {arg} (available: {', '.join(available)})"
        elif cmd == "/model" and arg:
            self._active_model_name = arg
            message = f"·· runtime · model switched to {arg}"
        elif cmd == "/help":
            message = "·· runtime · available commands: /model <name>, /provider <name>, /help"
        else:
            message = f"·· runtime · unknown command: {cmd}"

        await self._event_bus.emit("system_event", {"message": message})
