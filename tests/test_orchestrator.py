from pathlib import Path

from pacli.adapters.mock import MockAdapter
from pacli.events import EventBus
from pacli.local_sandbox import LocalSandbox
from pacli.orchestrator import Orchestrator
from pacli.policy import Policy
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
        ("token_received", "Hello"),
        ("token_received", " from"),
        ("token_received", " MockAdapter!"),
        "stream_finished",
    ]


async def test_orchestrator_executes_tool_and_emits_result(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    test_file = workspace / "test.txt"
    test_file.write_text("file content")

    bus = EventBus()
    sandbox = LocalSandbox(workspace_root=str(workspace))
    policy = Policy(workspace_root=str(workspace))
    read_file_tool = ReadFileTool(sandbox=sandbox, policy=policy)

    results = []
    bus.on("tool_result", lambda d: results.append(d))

    orchestrator = Orchestrator(provider=MockAdapter(), event_bus=bus)
    orchestrator.register_tool(read_file_tool)
    await orchestrator.execute_tool("read_file", path="test.txt")

    assert results == [{"tool": "read_file", "result": "file content"}]
