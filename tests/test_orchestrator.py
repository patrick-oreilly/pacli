import asyncio
from pathlib import Path

from pacli.adapters.mock import MockAdapter
from pacli.events import EventBus
from pacli.local_sandbox import LocalSandbox
from pacli.orchestrator import Orchestrator
from pacli.policy import Policy
from pacli.provider import Message, TextToken, ToolCall
from pacli.tool_registry import ToolRegistry
from pacli.tools.execute_shell import ExecuteShellTool
from pacli.tools.read_file import ReadFileTool


async def test_orchestrator_emits_event_sequence():
    bus = EventBus()
    events = []
    bus.on("stream_started", lambda d: events.append("stream_started"))
    bus.on("token_received", lambda d: events.append(("token_received", d)))
    bus.on("stream_finished", lambda d: events.append("stream_finished"))

    adapter = MockAdapter()
    orchestrator = Orchestrator(provider=adapter, event_bus=bus)
    await orchestrator.process_prompt("hello")
    assert events == [
        "stream_started",
        ("token_received", TextToken("Hello")),
        ("token_received", TextToken(" from")),
        ("token_received", TextToken(" MockAdapter!")),
        "stream_finished",
    ]


async def test_orchestrator_executes_tool_and_emits_result(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    test_file = workspace / "test.txt"
    test_file.write_text("file content")

    bus = EventBus()
    sandbox = LocalSandbox(workspace_root=str(workspace))
    read_file_tool = ReadFileTool(sandbox=sandbox)

    results = []
    bus.on("tool_result", lambda d: results.append(d))

    tool_registry = ToolRegistry()
    tool_registry.register_tool(read_file_tool)
    orchestrator = Orchestrator(provider=MockAdapter(), event_bus=bus, tool_registry=tool_registry)
    await orchestrator.execute_tool("read_file", path="test.txt")

    assert results == [{"tool": "read_file", "args": {"path": "test.txt"}, "result": "file content"}]


async def test_orchestrator_emits_approval_required_for_high_risk_tool():
    bus = EventBus()

    class _StubSandbox:
        async def read_file(self, path: str) -> str:
            return ""
        async def execute_command(self, command: str) -> str:
            return ""
    sandbox = _StubSandbox()
    shell_tool = ExecuteShellTool(sandbox=sandbox)

    events = []
    approval_emitted = asyncio.Event()
    bus.on("approval_required", lambda d: (events.append(d), approval_emitted.set()))

    tool_registry = ToolRegistry()
    tool_registry.register_tool(shell_tool)
    orchestrator = Orchestrator(
        provider=MockAdapter(), event_bus=bus, tool_registry=tool_registry, policy=Policy()
    )

    task = asyncio.create_task(orchestrator.execute_tool("execute_shell", command="echo hi"))
    await asyncio.sleep(0)
    await asyncio.wait_for(approval_emitted.wait(), timeout=2)

    assert len(events) == 1
    assert events[0]["tool"] == "execute_shell"
    assert events[0]["command"] == "echo hi"
    assert "id" in events[0]

    await bus.emit("approval_response", {"id": events[0]["id"], "approved": False})
    await task
    orchestrator.cleanup()


async def test_orchestrator_executes_high_risk_tool_after_approval():
    bus = EventBus()

    class _ApprovingSandbox:
        async def read_file(self, path: str) -> str:
            return ""
        async def execute_command(self, command: str) -> str:
            return f"executed: {command}"

    sandbox = _ApprovingSandbox()
    shell_tool = ExecuteShellTool(sandbox=sandbox)

    results = []
    bus.on("tool_result", lambda d: results.append(d))

    approval_events = []
    approval_emitted = asyncio.Event()
    bus.on("approval_required", lambda d: (approval_events.append(d), approval_emitted.set()))

    tool_registry = ToolRegistry()
    tool_registry.register_tool(shell_tool)
    orchestrator = Orchestrator(
        provider=MockAdapter(), event_bus=bus, tool_registry=tool_registry, policy=Policy()
    )

    task = asyncio.create_task(orchestrator.execute_tool("execute_shell", command="echo hi"))
    await asyncio.sleep(0)

    await asyncio.wait_for(approval_emitted.wait(), timeout=2)

    approval_id = approval_events[0]["id"]
    await bus.emit("approval_response", {"id": approval_id, "approved": True})

    await task

    assert len(results) == 1
    assert results[0]["tool"] == "execute_shell"
    assert results[0]["args"] == {"command": "echo hi"}
    assert results[0]["result"] == "executed: echo hi"
    orchestrator.cleanup()


async def test_orchestrator_skips_execution_when_approval_denied():
    bus = EventBus()
    sandbox = LocalSandbox(workspace_root=str(Path.cwd()))
    shell_tool = ExecuteShellTool(sandbox=sandbox)

    results = []
    bus.on("tool_result", lambda d: results.append(d))

    approval_events = []
    approval_emitted = asyncio.Event()
    bus.on("approval_required", lambda d: (approval_events.append(d), approval_emitted.set()))

    tool_registry = ToolRegistry()
    tool_registry.register_tool(shell_tool)
    orchestrator = Orchestrator(
        provider=MockAdapter(), event_bus=bus, tool_registry=tool_registry, policy=Policy()
    )

    task = asyncio.create_task(orchestrator.execute_tool("execute_shell", command="echo hi"))
    await asyncio.sleep(0)

    await asyncio.wait_for(approval_emitted.wait(), timeout=2)

    approval_id = approval_events[0]["id"]
    await bus.emit("approval_response", {"id": approval_id, "approved": False})

    await task

    assert len(results) == 1
    assert results[0]["tool"] == "execute_shell"
    assert "denied" in results[0]["error"].lower()
    orchestrator.cleanup()


async def test_slash_command_provider_switch():
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        provider_factory={"mock": (MockAdapter,), "ollama": (MockAdapter,)},
    )
    await orchestrator._on_slash_command("/provider ollama")

    assert len(system_events) == 1
    assert "provider switched to ollama" in system_events[0]["message"]
    orchestrator.cleanup()


async def test_slash_command_model_switch():
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
    )
    await orchestrator._on_slash_command("/model llama3.2")

    assert len(system_events) == 1
    assert "model switched to llama3.2" in system_events[0]["message"]
    orchestrator.cleanup()


async def test_slash_command_help():
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
    )
    await orchestrator._on_slash_command("/help")

    assert len(system_events) == 1
    assert "available commands" in system_events[0]["message"]
    orchestrator.cleanup()


async def test_slash_command_unknown():
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
    )
    await orchestrator._on_slash_command("/foobar")

    assert len(system_events) == 1
    assert "unknown command" in system_events[0]["message"]
    orchestrator.cleanup()


async def test_slash_command_unknown_provider():
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        provider_factory={"mock": (MockAdapter,)},
    )
    await orchestrator._on_slash_command("/provider none")

    assert len(system_events) == 1
    assert "unknown provider" in system_events[0]["message"]
    orchestrator.cleanup()


async def test_process_prompt_loops_with_tool_calls():
    bus = EventBus()

    class StubProvider:
        def __init__(self):
            self.call_count = 0

        async def stream_completion(self, messages, tool_schemas=None):
            self.call_count += 1
            if self.call_count == 1:
                yield ToolCall(id="tc1", name="read_file", args={"path": "test.txt"})
            else:
                yield TextToken(text="final response")

    tool_registry = ToolRegistry()

    class StubReadFile:
        name = "read_file"
        schema = {"type": "function", "function": {"name": "read_file"}}

        async def __call__(self, path: str) -> str:
            return "file content"

    tool_registry.register_tool(StubReadFile())

    events = []
    bus.on("stream_started", lambda d: events.append(("stream_started",)))
    bus.on("stream_finished", lambda d: events.append(("stream_finished",)))
    bus.on("tool_used", lambda d: events.append(("tool_used", d)))
    bus.on("tool_result", lambda d: events.append(("tool_result", d)))
    bus.on("token_received", lambda d: events.append(("token_received", d.text)))

    orchestrator = Orchestrator(provider=StubProvider(), event_bus=bus, tool_registry=tool_registry)
    await orchestrator.process_prompt("read test.txt")

    assert events[0] == ("stream_started",)
    assert events[1] == ("tool_used", {"tool": "read_file", "args": {"path": "test.txt"}, "id": "tc1"})
    assert events[2] == ("tool_result", {"tool": "read_file", "args": {"path": "test.txt"}, "result": "file content"})
    assert events[3] == ("token_received", "final response")
    assert events[4] == ("stream_finished",)
    assert len(events) == 5


async def test_process_prompt_max_iterations_guard():
    bus = EventBus()

    class StubProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            yield ToolCall(id="tc1", name="read_file", args={"path": "x"})

    tool_registry = ToolRegistry()

    class StubReadFile:
        name = "read_file"
        schema = {"type": "function", "function": {"name": "read_file"}}

        async def __call__(self, path: str) -> str:
            return "content"

    tool_registry.register_tool(StubReadFile())

    results = []
    bus.on("tool_result", lambda d: results.append(d))

    orchestrator = Orchestrator(provider=StubProvider(), event_bus=bus, tool_registry=tool_registry, loop_max_iterations=3)
    await orchestrator.process_prompt("test")

    max_events = [r for r in results if r.get("tool") == "_loop"]
    assert len(max_events) == 1
    assert "Exceeded max iterations" in max_events[0]["error"]


async def test_process_prompt_tool_exception_produces_tool_message():
    bus = EventBus()

    class StubProvider:
        def __init__(self):
            self.call_count = 0

        async def stream_completion(self, messages, tool_schemas=None):
            self.call_count += 1
            if self.call_count == 1:
                yield ToolCall(id="tc1", name="read_file", args={"path": "missing.txt"})
            else:
                if len(messages) >= 3:
                    tool_msg = messages[2]
                    assert tool_msg.role == "tool"
                    assert "Error:" in tool_msg.content or "error" in tool_msg.content.lower()
                yield TextToken(text="recovered")

    tool_registry = ToolRegistry()

    class StubReadFile:
        name = "read_file"
        schema = {"type": "function", "function": {"name": "read_file"}}

        async def __call__(self, path: str) -> str:
            raise RuntimeError("Boom!")

    tool_registry.register_tool(StubReadFile())

    events = []
    bus.on("stream_started", lambda d: events.append("stream_started"))
    bus.on("stream_finished", lambda d: events.append("stream_finished"))
    bus.on("token_received", lambda d: events.append(("token_received", d.text)))

    orchestrator = Orchestrator(provider=StubProvider(), event_bus=bus, tool_registry=tool_registry)
    await orchestrator.process_prompt("test")

    assert "stream_started" in events
    assert "stream_finished" in events
    assert ("token_received", "recovered") in events


async def test_process_prompt_stream_started_finished_span_entire_loop():
    bus = EventBus()

    class StubProvider:
        def __init__(self):
            self.call_count = 0

        async def stream_completion(self, messages, tool_schemas=None):
            self.call_count += 1
            if self.call_count == 1:
                yield ToolCall(id="tc1", name="read_file", args={"path": "a"})
            elif self.call_count == 2:
                yield ToolCall(id="tc2", name="read_file", args={"path": "b"})
            else:
                yield TextToken(text="done")

    tool_registry = ToolRegistry()

    class StubReadFile:
        name = "read_file"
        schema = {"type": "function", "function": {"name": "read_file"}}

        async def __call__(self, path: str) -> str:
            return f"content of {path}"

    tool_registry.register_tool(StubReadFile())

    events = []
    bus.on("stream_started", lambda d: events.append("stream_started"))
    bus.on("stream_finished", lambda d: events.append("stream_finished"))

    orchestrator = Orchestrator(provider=StubProvider(), event_bus=bus, tool_registry=tool_registry)
    await orchestrator.process_prompt("test")

    assert events.count("stream_started") == 1
    assert events.count("stream_finished") == 1
    assert events[0] == "stream_started"
    assert events[-1] == "stream_finished"


async def test_orchestrator_emits_system_fault_on_unexpected_exception():
    class _StreamFinishedExplodingBus(EventBus):
        async def emit(self, event_type, data=None, concurrent=False):
            if event_type == "stream_finished":
                raise RuntimeError("unexpected crash in stream_finished emit")
            return await super().emit(event_type, data=data, concurrent=concurrent)

    exploding_bus = _StreamFinishedExplodingBus()

    faults = []
    exploding_bus.on("system_fault", lambda d: faults.append(d))

    orchestrator = Orchestrator(provider=MockAdapter(), event_bus=exploding_bus)
    await orchestrator.process_prompt("hello")

    assert len(faults) == 1
    assert "RuntimeError" in faults[0]["traceback"]
    assert "unexpected crash in stream_finished emit" in faults[0]["traceback"]


async def test_system_prompt_is_prepended_to_messages():
    bus = EventBus()

    captured_messages: list[list[Message]] = []

    class StubProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            captured_messages.append(messages)
            yield TextToken(text="ok")

    orchestrator = Orchestrator(
        provider=StubProvider(),
        event_bus=bus,
        system_prompt="You are a helpful assistant.",
    )
    await orchestrator.process_prompt("hello")

    assert len(captured_messages) == 1
    msgs = captured_messages[0]
    assert msgs[0].role == "system"
    assert msgs[0].content == "You are a helpful assistant."
    assert msgs[1].role == "user"
    assert msgs[1].content == "hello"
    orchestrator.cleanup()


async def test_no_system_prompt_when_none():
    bus = EventBus()

    captured_messages: list[list[Message]] = []

    class StubProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            captured_messages.append(messages)
            yield TextToken(text="ok")

    orchestrator = Orchestrator(
        provider=StubProvider(),
        event_bus=bus,
    )
    await orchestrator.process_prompt("hello")

    assert len(captured_messages) == 1
    msgs = captured_messages[0]
    assert msgs[0].role == "user"
    assert msgs[0].content == "hello"
    orchestrator.cleanup()


async def test_model_slash_command_updates_provider_model():
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    class StubProviderWithModel:
        _model = "old-model"

        async def stream_completion(self, messages, tool_schemas=None):
            yield TextToken(text="ok")

    provider = StubProviderWithModel()
    orchestrator = Orchestrator(
        provider=provider,
        event_bus=bus,
    )
    await orchestrator._on_slash_command("/model new-model")

    assert provider._model == "new-model"
    assert "model switched to new-model" in system_events[0]["message"]
    orchestrator.cleanup()


async def test_provider_name_init():
    bus = EventBus()

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
        provider_name="ollama",
    )
    assert orchestrator._active_provider_name == "ollama"
    orchestrator.cleanup()


async def test_tools_disabled_does_not_send_schemas():
    bus = EventBus()

    captured_schemas: list = []

    class StubProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            captured_schemas.append(tool_schemas)
            yield TextToken(text="ok")

    orchestrator = Orchestrator(
        provider=StubProvider(),
        event_bus=bus,
        tools_enabled=False,
    )
    await orchestrator.process_prompt("hello")

    assert captured_schemas[0] is None
    orchestrator.cleanup()


async def test_tools_enabled_sends_schemas():
    bus = EventBus()

    captured_schemas: list = []

    class StubProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            captured_schemas.append(tool_schemas)
            yield TextToken(text="ok")

    tool_registry = ToolRegistry()
    tool_registry.register_tool(ReadFileTool(sandbox=LocalSandbox(workspace_root="/tmp")))

    orchestrator = Orchestrator(
        provider=StubProvider(),
        event_bus=bus,
        tool_registry=tool_registry,
        tools_enabled=True,
    )
    await orchestrator.process_prompt("hello")

    assert captured_schemas[0] is not None
    orchestrator.cleanup()


async def test_tools_slash_command():
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    orchestrator = Orchestrator(
        provider=MockAdapter(),
        event_bus=bus,
    )
    assert orchestrator._tools_enabled is False

    await orchestrator._on_slash_command("/tools on")
    assert orchestrator._tools_enabled is True
    assert "tools enabled" in system_events[0]["message"]

    system_events.clear()
    await orchestrator._on_slash_command("/tools off")
    assert orchestrator._tools_enabled is False
    assert "tools disabled" in system_events[0]["message"]

    orchestrator.cleanup()


async def test_orchestrator_multi_turn_history():
    bus = EventBus()
    captured_messages = []

    class StubProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            captured_messages.append(list(messages))
            yield TextToken(text="response")

    orchestrator = Orchestrator(
        provider=StubProvider(),
        event_bus=bus,
    )
    
    await orchestrator.process_prompt("first prompt")
    await orchestrator.process_prompt("second prompt")

    assert len(captured_messages) == 2
    msgs1 = captured_messages[0]
    assert len(msgs1) == 1
    assert msgs1[0].role == "user"
    assert msgs1[0].content == "first prompt"

    msgs2 = captured_messages[1]
    assert len(msgs2) == 3
    assert msgs2[0].role == "user"
    assert msgs2[0].content == "first prompt"
    assert msgs2[1].role == "assistant"
    assert msgs2[1].content == "response"
    assert msgs2[2].role == "user"
    assert msgs2[2].content == "second prompt"
    orchestrator.cleanup()


def test_chat_chunks_all_messages_ordering():
    from pacli.chat_chunks import ChatChunks
    from pacli.provider import Message

    chunks = ChatChunks()
    chunks.system.append(Message(role="system", content="sys"))
    chunks.context.append(Message(role="user", content="ctx1"))
    chunks.context.append(Message(role="assistant", content="ctx2"))
    chunks.history.append(Message(role="user", content="hist1"))
    chunks.conversation.append(Message(role="user", content="conv1"))
    chunks.reminder.append(Message(role="system", content="rem"))

    result = chunks.all_messages()
    assert len(result) == 6
    assert result[0] == chunks.system[0]
    assert result[1] == chunks.context[0]
    assert result[2] == chunks.context[1]
    assert result[3] == chunks.history[0]
    assert result[4] == chunks.conversation[0]
    assert result[5] == chunks.reminder[0]


def test_chat_chunks_empty_layers():
    from pacli.chat_chunks import ChatChunks
    from pacli.provider import Message

    chunks = ChatChunks()
    chunks.system.append(Message(role="system", content="sys"))
    chunks.conversation.append(Message(role="user", content="u"))

    result = chunks.all_messages()
    assert len(result) == 2
    assert result[0].role == "system"
    assert result[1].role == "user"


async def test_orchestrator_clear_preserves_system_and_history():
    bus = EventBus()
    system_events = []
    bus.on("system_event", lambda d: system_events.append(d))

    captured_messages = []

    class StubProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            captured_messages.append(list(messages))
            yield TextToken(text="ok")

    orchestrator = Orchestrator(
        provider=StubProvider(),
        event_bus=bus,
        system_prompt="system msg",
    )

    orchestrator._chunks.history.append(Message(role="user", content="history item"))

    await orchestrator.process_prompt("hello")
    await orchestrator._on_slash_command("/clear")

    assert orchestrator._chunks.system[0].content == "system msg"
    assert orchestrator._chunks.history[0].content == "history item"
    assert orchestrator._chunks.conversation == []

    await orchestrator.process_prompt("after clear")

    assert len(captured_messages) == 2
    msgs = captured_messages[1]
    roles = [m.role for m in msgs]
    contents = [m.content for m in msgs]
    assert roles == ["system", "user", "user"]
    assert contents == ["system msg", "history item", "after clear"]

    orchestrator.cleanup()


async def test_orchestrator_clear_command():

    bus = EventBus()
    captured_messages = []

    class StubProvider:
        async def stream_completion(self, messages, tool_schemas=None):
            captured_messages.append(list(messages))
            yield TextToken(text="response")

    orchestrator = Orchestrator(
        provider=StubProvider(),
        event_bus=bus,
    )
    
    await orchestrator.process_prompt("first prompt")
    await orchestrator._on_slash_command("/clear")
    await orchestrator.process_prompt("second prompt")

    assert len(captured_messages) == 2
    msgs2 = captured_messages[1]
    assert len(msgs2) == 1
    assert msgs2[0].role == "user"
    assert msgs2[0].content == "second prompt"
    orchestrator.cleanup()
