import asyncio
from uuid import uuid4
from typing import Any

from pacli.chat_chunks import ChatChunks
from pacli.events import EventBus, EventType
from pacli.policy import Policy
from pacli.provider import Message, Provider, TextToken, ToolCall
from pacli.summarizer import Summarizer, estimate_tokens
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
        max_reflections: int = 3,
        system_prompt: str | None = None,
        provider_name: str = "mock",
        model_name: str = "mock",
        tools_enabled: bool = False,
        summary_provider: Provider | None = None,
        summary_model: str = "",
        max_chat_history_tokens: int = 64000,
    ) -> None:
        self._provider = provider
        self._event_bus = event_bus
        self._tool_registry = tool_registry or ToolRegistry()
        self._policy = policy or Policy()
        self._provider_factory = provider_factory or {}
        self._active_provider_name = provider_name
        self._active_model_name = model_name
        self._system_prompt = system_prompt
        self._tools_enabled = tools_enabled
        self._loop_max_iterations = loop_max_iterations
        self._max_reflections = max_reflections
        self._summary_provider = summary_provider
        self._summary_model = summary_model
        self._max_chat_history_tokens = max_chat_history_tokens
        self._pending_approvals: dict[str, asyncio.Future[bool]] = {}
        self._approval_handler = self._on_approval_response
        self._slash_handler = self._on_slash_command
        self._process_lock = asyncio.Lock()
        self._chunks = ChatChunks()
        if self._system_prompt:
            self._chunks.system.append(Message(role="system", content=self._system_prompt))
        self._event_bus.on(EventType.APPROVAL_RESPONSE, self._approval_handler)
        self._event_bus.on(EventType.SLASH_COMMAND, self._slash_handler)

    def cleanup(self) -> None:
        self._event_bus.off(EventType.APPROVAL_RESPONSE, self._approval_handler)
        self._event_bus.off(EventType.SLASH_COMMAND, self._slash_handler)

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
            await self._event_bus.emit(EventType.APPROVAL_REQUIRED, approval_data)
            try:
                approved = await asyncio.wait_for(future, timeout=APPROVAL_TIMEOUT)
            except asyncio.TimeoutError:
                approved = False
            if not approved:
                error = "Approval denied by user"
                await self._event_bus.emit(
                    EventType.TOOL_RESULT, {"tool": tool_name, "args": kwargs, "error": error}
                )
                return (error, True)
        try:
            result = await self._tool_registry.execute_tool(tool_name, **kwargs)
            await self._event_bus.emit(EventType.TOOL_RESULT, {"tool": tool_name, "args": kwargs, "result": result})
            return (result, False)
        except Exception as e:
            error = str(e)
            await self._event_bus.emit(EventType.TOOL_RESULT, {"tool": tool_name, "args": kwargs, "error": error})
            return (error, True)

    async def process_prompt(self, prompt: str) -> None:
        if self._process_lock.locked():
            await self._event_bus.emit(
                EventType.SYSTEM_EVENT,
                {"message": "·· runtime · already processing a prompt, please wait"},
            )
            return
        async with self._process_lock:
            await self._do_process_prompt(prompt)

    async def _do_process_prompt(self, prompt: str) -> None:
        try:
            await self._event_bus.emit(EventType.STREAM_STARTED)
            success = False
            try:
                self._chunks.conversation.append(Message(role="user", content=prompt))
                tool_schemas = self._tool_registry.tool_schemas if self._tools_enabled else None

                for reflection_round in range(self._max_reflections + 1):
                    if reflection_round > 0:
                        await self._event_bus.emit(EventType.REFLECTION, {"round": reflection_round})

                    round_errors: list[str] = []

                    for _ in range(self._loop_max_iterations):
                        text_chunks: list[str] = []
                        tool_calls: list[ToolCall] = []

                        async for event in self._provider.stream_completion(self._chunks.all_messages(), tool_schemas):
                            if isinstance(event, TextToken):
                                await self._event_bus.emit(EventType.TOKEN_RECEIVED, event)
                                text_chunks.append(event.text)
                            elif isinstance(event, ToolCall):
                                tool_calls.append(event)

                        if not tool_calls:
                            assistant_content = "".join(text_chunks) if text_chunks else None
                            self._chunks.conversation.append(Message(role="assistant", content=assistant_content))
                            break

                        assistant_content = "".join(text_chunks) if text_chunks else None
                        self._chunks.conversation.append(Message(role="assistant", content=assistant_content, tool_calls=tool_calls))

                        for tc in tool_calls:
                            await self._event_bus.emit(EventType.TOOL_USED, {"tool": tc.name, "args": tc.args, "id": tc.id})
                            result, is_error = await self.execute_tool(tc.name, **tc.args)
                            if is_error:
                                round_errors.append(f"Error: {tc.name}: {result}")
                            content = f"Error: {result}" if is_error else result
                            self._chunks.conversation.append(Message(role="tool", content=content, tool_call_id=tc.id))
                    else:
                        round_errors.append(f"Exceeded max iterations ({self._loop_max_iterations})")
                        await self._event_bus.emit(
                            EventType.TOOL_RESULT,
                            {"tool": "_loop", "args": {}, "error": f"Exceeded max iterations ({self._loop_max_iterations})"},
                        )

                    if not round_errors:
                        break

                    if reflection_round >= self._max_reflections:
                        break

                    error_list = "\n".join(f"- {e}" for e in round_errors)
                    reflection_prompt = f"The following errors occurred:\n{error_list}\nPlease fix these issues."
                    self._chunks.conversation.append(Message(role="user", content=reflection_prompt))
                success = True
            except Exception as e:
                await self._event_bus.emit(EventType.PROMPT_ERROR, {"error": str(e)})
            finally:
                if success:
                    await self._maybe_summarize()
                await self._event_bus.emit(EventType.STREAM_FINISHED)
        except Exception:
            import traceback
            tb = traceback.format_exc()
            await self._event_bus.emit(EventType.SYSTEM_FAULT, {"traceback": tb})

    async def _maybe_summarize(self) -> None:
        if self._summary_provider is None or not self._summary_model:
            return

        messages = self._chunks.all_messages()
        token_count = estimate_tokens(messages)
        if token_count <= self._max_chat_history_tokens:
            return

        await self._event_bus.emit(
            EventType.SYSTEM_EVENT,
            {"message": "·· runtime · summarizing conversation"},
        )

        try:
            summarizer = Summarizer(self._summary_provider, self._summary_model)
            summary = await summarizer.summarize(messages)

            summary_tokens = estimate_tokens(summary)
            if summary_tokens >= token_count:
                return

            self._chunks.history.extend(summary)
            self._chunks.conversation = []
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Summarization failed, preserving conversation"
            )

    async def _on_slash_command(self, data: str) -> None:
        parts = data.split(" ", 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/provider":
            if not arg:
                available = list(self._provider_factory.keys()) if self._provider_factory else ["mock"]
                message = f"·· runtime · usage: /provider <name> (available: {', '.join(available)})"
            else:
                entry = self._provider_factory.get(arg)
                if entry:
                    cls, *args = entry
                    self._provider = cls(*args)
                    self._active_provider_name = arg
                    message = f"·· runtime · provider switched to {arg}"
                else:
                    available = list(self._provider_factory.keys()) if self._provider_factory else ["mock"]
                    message = f"·· runtime · unknown provider: {arg} (available: {', '.join(available)})"
        elif cmd == "/model":
            if arg in ("list", "ls"):
                if hasattr(self._provider, "list_models"):
                    try:
                        models = await self._provider.list_models()
                        message = f"·· runtime · available models: {', '.join(models)}"
                    except Exception:
                        message = "·· runtime · could not fetch model list"
                else:
                    message = "·· runtime · model listing not supported by current provider"
            elif not arg:
                message = f"·· runtime · current model: {self._active_model_name} (usage: /model <name>, /model list)"
            else:
                self._active_model_name = arg
                if hasattr(self._provider, "_model"):
                    self._provider._model = arg
                message = f"·· runtime · model switched to {arg}"
        elif cmd in ("/clear", "/reset"):
            self._chunks.conversation = []
            message = "·· runtime · conversation history cleared"
        elif cmd == "/tools":
            if arg not in ("on", "off"):
                message = "·· runtime · usage: /tools on|off"
            else:
                self._tools_enabled = arg == "on"
                message = f"·· runtime · tools {'enabled' if self._tools_enabled else 'disabled'}"
        elif cmd == "/help":
            message = "·· runtime · available commands: /model <name|list>, /provider <name>, /tools on|off, /clear, /reset, /help"
        else:
            message = f"·· runtime · unknown command: {cmd}"

        await self._event_bus.emit(EventType.SYSTEM_EVENT, {"message": message})
