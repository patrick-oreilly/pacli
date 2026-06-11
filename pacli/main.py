from pathlib import Path

from pacli.adapters.mock import MockAdapter
from pacli.console.app import Console
from pacli.events import EventBus
from pacli.local_sandbox import LocalSandbox
from pacli.orchestrator import Orchestrator
from pacli.policy import Policy
from pacli.tool_registry import ToolRegistry
from pacli.tools.execute_shell import ExecuteShellTool
from pacli.tools.read_file import ReadFileTool


def main():
    workspace_root = str(Path(__file__).resolve().parent.parent)

    bus = EventBus()
    sandbox = LocalSandbox(workspace_root=workspace_root)
    read_file_tool = ReadFileTool(sandbox=sandbox)
    shell_tool = ExecuteShellTool(sandbox=sandbox)
    policy = Policy()

    tool_registry = ToolRegistry()
    tool_registry.register_tool(read_file_tool)
    tool_registry.register_tool(shell_tool)
    orchestrator = Orchestrator(provider=MockAdapter(), event_bus=bus, tool_registry=tool_registry, policy=policy)

    bus.on("prompt_submitted", orchestrator.process_prompt)

    app = Console(event_bus=bus)
    app.run()
    orchestrator.cleanup()
