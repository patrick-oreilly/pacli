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
